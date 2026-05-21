from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
import re
import subprocess
import os

app = FastAPI()
API_VERSION = "2.4"

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
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
    return subprocess.check_output(["docker", "ps"], text=True)


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

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)


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


def run_tool_loop(session_id: str) -> AIMessage:
    response = llm_with_tools.invoke(sessions[session_id])
    iterations = 0

    while getattr(response, "tool_calls", None) and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        sessions[session_id].append(response)

        for tool_call in response.tool_calls:
            tool = TOOL_BY_NAME.get(tool_call["name"])
            if tool is None:
                output = f"Невідомий інструмент: {tool_call['name']}"
            else:
                output = tool.invoke(tool_call["args"])
            if not str(output).strip():
                output = "(порожній вивід — спробуй інший інструмент або інший запит)"
            sessions[session_id].append(
                ToolMessage(tool_call_id=tool_call["id"], content=str(output))
            )

        response = llm_with_tools.invoke(sessions[session_id])

    return response


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
    if not answer:
        answer = answer_from_web_search(user_q)
    if not answer:
        return (
            "Агент не зміг сформулювати відповідь. Спробуйте /reset або "
            "переформулюйте питання."
        )
    return ensure_answer_language(user_q, answer)


class QueryRequest(BaseModel):
    session_id: str
    question: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "model": OLLAMA_MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
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

    response = run_tool_loop(session_id)
    answer = finalize_answer(session_id, user_q, response)

    sessions[session_id].append(AIMessage(content=answer))
    trim_session(session_id)

    return {"answer": answer}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
