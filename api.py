import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
import os
import re
import subprocess
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

API_VERSION = "2.4"
OLLAMA_READY = False

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081",
    ).split(",")
    if o.strip()
]
_allow_credentials = "*" not in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "hermes3")

sessions = {}
MAX_TOOL_ITERATIONS = 10
MAX_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = (
    "Ти — технічний AI-агент. Твоє завдання — керувати сервером та перевіряти факти.\n"
    "Сам вибирай і викликай інструменти за змістом питання — не проси користувача їх викликати.\n"
    "Для актуальних фактів (погода, новини, курси тощо) — web_search.\n"
    "Для стану сервера, файлів, логів, Docker — відповідні серверні інструменти.\n"
    "Після отримання результатів інструментів обов'язково дай повну текстову відповідь.\n"
    "МОВА: відповідай тією ж мовою, що й останнє повідомлення користувача.\n"
    "Не копіюй сирий текст з web_search — переказуй своїми словами.\n"
    "Заборонено змішувати кілька мов в одній відповіді."
)

# --- ІНСТРУМЕНТИ ---


def _run_shell(command: str) -> str:
    try:
        return subprocess.check_output(
            command, shell=True, text=True, stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError as e:
        return f"Помилка: {e.output.strip()}"
    except Exception as e:
        return f"Помилка: {e}"


@tool
def get_system_load():
    """Повертає навантаження Linux: load average, uptime, mpstat (CPU), sar."""
    parts = [
        "=== load average ===",
        _run_shell("cat /proc/loadavg"),
        "=== uptime ===",
        _run_shell("uptime"),
        "=== mpstat (1 сек) ===",
        _run_shell("mpstat 1 1 2>/dev/null || echo 'mpstat не встановлено (apt install sysstat)'"),
        "=== sar (останні 2 хв, якщо є) ===",
        _run_shell(
            "sar -u 1 2 2>/dev/null | tail -5 || "
            "echo 'sar недоступний — історія за 2 хв недоступна, лише поточний знімок'"
        ),
    ]
    return "\n".join(parts)


@tool
def get_docker_status():
    """Повертає список запущених Docker контейнерів."""
    try:
        return subprocess.check_output(
            ["docker", "ps"], text=True, stderr=subprocess.STDOUT, timeout=30
        )
    except subprocess.TimeoutExpired:
        return "Помилка: docker ps перевищив час очікування."
    except subprocess.CalledProcessError as e:
        return f"Помилка docker ps: {e.output}"
    except Exception as e:
        return f"Помилка docker: {e}"


@tool
def read_log_tool(file_path: str, lines: int = 20):
    """Зчитує останні N рядків з файлу логів."""
    if not os.path.exists(file_path):
        return f"Файл {file_path} не знайдено."
    try:
        return subprocess.check_output(["tail", "-n", str(lines), file_path], text=True)
    except Exception as e:
        return f"Помилка читання файлу: {str(e)}"


@tool
def list_directory(path: str = "."):
    """Показує список файлів та папок у вказаній директорії."""
    try:
        return subprocess.check_output(["ls", "-F", path], text=True)
    except Exception as e:
        return f"Помилка доступу до папки: {str(e)}"


@tool
def execute_command(command: str):
    """Виконує shell-команду. Кожен виклик — окремий shell; cd не зберігається між викликами."""
    try:
        return subprocess.check_output(
            command, shell=True, text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        return f"Помилка при виконанні команди '{command}': {e.output}"
    except Exception as e:
        return f"Помилка: {str(e)}"


search_tool = DuckDuckGoSearchRun()
search_tool.name = "web_search"
search_tool.description = (
    "Пошук в інтернеті для актуальних фактів. "
    "У відповіді користувачу переказуй результат тією ж мовою, що й його питання."
)

TOOLS = [
    get_system_load,
    execute_command,
    list_directory,
    read_log_tool,
    get_docker_status,
    search_tool,
]
TOOL_BY_NAME = {t.name: t for t in TOOLS}

LLM_READ_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "600"))
LLM_CONNECT_TIMEOUT = float(os.environ.get("LLM_CONNECT_TIMEOUT", "120"))
_HTTPX_TIMEOUT = httpx.Timeout(LLM_READ_TIMEOUT, connect=LLM_CONNECT_TIMEOUT)

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    timeout=_HTTPX_TIMEOUT,
    num_ctx=4096,
)
llm_with_tools = llm.bind_tools(TOOLS)


def _warmup_ollama() -> None:
    global OLLAMA_READY
    logger.info(
        "Прогрів Ollama: %s @ %s (перший запуск може зайняти 1–3 хв)",
        OLLAMA_MODEL,
        OLLAMA_BASE_URL,
    )
    try:
        llm.invoke([HumanMessage(content="ok")])
        OLLAMA_READY = True
        logger.info("Ollama готова до запитів")
    except Exception as e:
        OLLAMA_READY = False
        logger.warning("Прогрів Ollama не вдався: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(_warmup_ollama)
    yield


app = FastAPI(lifespan=lifespan)

WEB_SEARCH_HINTS = (
    "погод", "новин", "курс", "ціна", "сьогодні", "зараз", "актуальн",
    "weather", "news", "price", "today", "current",
)


def _letter_counts(text: str) -> tuple[int, int]:
    cyrillic = len(re.findall(r"[а-яА-ЯіїєґІЇЄҐёЁ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    return cyrillic, latin


def needs_language_fix(user_q: str, answer: str) -> bool:
    if not answer.strip():
        return False
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", answer):
        return True
    q_cyr, q_lat = _letter_counts(user_q)
    a_cyr, a_lat = _letter_counts(answer)
    q_cyrillic = q_cyr >= q_lat
    a_cyrillic = a_cyr >= a_lat
    if (q_cyr + q_lat) > 3 and q_cyrillic != a_cyrillic:
        return True
    if q_cyrillic and a_lat > 80 and a_cyr < 40:
        return True
    if not q_cyrillic and q_lat > 3 and a_cyr > 80:
        return True
    return False


def ensure_answer_language(user_q: str, answer: str) -> str:
    if not needs_language_fix(user_q, answer):
        return answer
    prompt = (
        f"Питання користувача:\n{user_q}\n\n"
        f"Чернетка відповіді:\n{answer}\n\n"
        "Перепиши однією відповіддю тією ж мовою, що й питання. "
        "Збережи факти, прибери дублікати та фрагменти іншими мовами. "
        "Не згадуй інструменти."
    )
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )
    return (response.content or "").strip() or answer


def trim_session(session_id: str) -> None:
    history = sessions[session_id]
    if len(history) <= MAX_HISTORY_MESSAGES + 1:
        return
    sessions[session_id] = [history[0]] + history[-MAX_HISTORY_MESSAGES:]


def reset_session(session_id: str) -> None:
    sessions[session_id] = [SystemMessage(content=SYSTEM_PROMPT)]


def run_web_search(query: str) -> str:
    try:
        result = search_tool.invoke(query)
        return str(result).strip() if result else ""
    except Exception as e:
        return f"Помилка пошуку: {e}"


def _invoke_tool(tool_call: dict) -> str:
    tool = TOOL_BY_NAME.get(tool_call["name"])
    if tool is None:
        return f"Невідомий інструмент: {tool_call['name']}"
    try:
        output = tool.invoke(tool_call["args"])
    except Exception as e:
        logger.exception("tool %s failed", tool_call.get("name"))
        return f"Помилка інструменту {tool_call['name']}: {e}"
    if not str(output).strip():
        return "(порожній вивід — спробуй інший інструмент або інший запит)"
    return str(output)


def _invoke_llm_with_retry(messages):
    last_err = None
    for attempt in range(2):
        try:
            return llm_with_tools.invoke(messages)
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if attempt == 0 and ("timeout" in err or "timed out" in err):
                logger.warning("Таймаут Ollama, повтор через 15 с: %s", e)
                time.sleep(15)
                continue
            raise
    raise last_err


def run_tool_loop(session_id: str) -> AIMessage:
    response = _invoke_llm_with_retry(sessions[session_id])
    iterations = 0

    while getattr(response, "tool_calls", None) and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        sessions[session_id].append(response)

        for tool_call in response.tool_calls:
            output = _invoke_tool(tool_call)
            sessions[session_id].append(
                ToolMessage(tool_call_id=tool_call["id"], content=output)
            )

        response = _invoke_llm_with_retry(sessions[session_id])

    return response


def _had_tool_messages(session_id: str) -> bool:
    return any(
        isinstance(msg, ToolMessage) for msg in sessions.get(session_id, [])
    )


def should_try_web_search(user_q: str, session_id: str) -> bool:
    if _had_tool_messages(session_id):
        return False
    q = user_q.lower()
    return any(h in q for h in WEB_SEARCH_HINTS)


def simple_chat_fallback(user_q: str) -> str:
    q = user_q.lower().strip()
    if q in ("привіт", "привет", "hello", "hi", "hey", "вітаю"):
        return (
            "Привіт! Я технічний агент. Можу перевірити навантаження CPU, "
            "Docker-контейнери, файли та логи на сервері. Задайте конкретне питання."
        )
    return (
        "Не вдалося отримати відповідь від моделі (можливо, не вистачає RAM для hermes3). "
        "Спробуйте /reset або простіше питання, наприклад: «покажи docker ps»."
    )


def _summarize_context(user_q: str, context: str, context_title: str) -> str:
    prompt = (
        f"Питання користувача:\n{user_q}\n\n"
        f"{context_title}:\n{context}\n\n"
        "Дай повну відповідь на основі цих даних тією ж мовою, що й питання. "
        "Якщо даних недостатньо — скажи чесно. Не згадуй інструменти."
    )
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )
    raw = (response.content or "").strip()
    return ensure_answer_language(user_q, raw)


def answer_from_tool_context(session_id: str, user_q: str) -> str:
    outputs = [
        msg.content
        for msg in sessions[session_id]
        if isinstance(msg, ToolMessage) and str(msg.content).strip()
    ]
    if not outputs:
        return ""
    combined = "\n\n---\n\n".join(outputs[-5:])
    return _summarize_context(user_q, combined, "Дані з інструментів")


def answer_from_web_search(user_q: str) -> str:
    search_data = run_web_search(user_q)
    if not search_data:
        return ""
    return _summarize_context(user_q, search_data, "Результати веб-пошуку")


def finalize_answer(session_id: str, user_q: str, response: AIMessage) -> str:
    answer = (response.content or "").strip()
    if not answer:
        answer = answer_from_tool_context(session_id, user_q)
    if not answer and should_try_web_search(user_q, session_id):
        answer = answer_from_web_search(user_q)
    if not answer:
        return simple_chat_fallback(user_q)
    return ensure_answer_language(user_q, answer)


class QueryRequest(BaseModel):
    session_id: str
    question: str


@app.get("/health")
async def health():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok" if ollama_ok else "degraded",
        "api_version": API_VERSION,
        "model": OLLAMA_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_reachable": ollama_ok,
        "ollama_model_warmed": OLLAMA_READY,
    }


@app.post("/reset")
async def reset(request: QueryRequest):
    reset_session(request.session_id)
    return {"status": "session reset", "session_id": request.session_id}


@app.post("/ask")
async def ask_question(request: QueryRequest):
    session_id = request.session_id
    user_q = request.question.strip()

    if not user_q:
        return {"answer": "Порожнє питання."}

    if user_q.lower().startswith("/reset"):
        reset_session(session_id)
        return {"answer": "Сесію скинуто. Можете ставити нові питання."}

    if session_id not in sessions:
        reset_session(session_id)

    sessions[session_id].append(HumanMessage(content=user_q))
    trim_session(session_id)

    try:
        response = run_tool_loop(session_id)
        answer = finalize_answer(session_id, user_q, response)
        sessions[session_id].append(AIMessage(content=answer))
        trim_session(session_id)
        return {"answer": answer}
    except Exception as e:
        logger.exception("ask failed session=%s", session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Помилка агента: {e}. Перевірте логи: docker compose logs api ollama",
        ) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
