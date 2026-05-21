from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
import subprocess
import os

app = FastAPI()
API_VERSION = "2.1"

# --- ПАМ'ЯТЬ (Історія діалогів) ---
# Структура: { session_id: [messages] }
sessions = {}
MAX_TOOL_ITERATIONS = 10
MAX_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = (
    "Ти — технічний AI-асистент на Linux-сервері. Ти САМ викликаєш інструменти.\n"
    "НІКОЛИ не кажи користувачу «виклич функцію» — це робиш ти.\n"
    "НІКОЛИ не згадуй Docker, якщо питання не про Docker.\n"
    "Інструменти:\n"
    "1. get_system_load — CPU, load average, uptime (навантаження системи).\n"
    "2. execute_command — shell-команди.\n"
    "3. list_directory — файли й папки.\n"
    "4. read_log_tool — логи.\n"
    "5. get_docker_status — лише для питань про Docker.\n"
    "Правила: не вигадуй цифри; load average — це НЕ % CPU."
)

METRICS_KEYWORDS = (
    "навантаж", "cpu", "статист", "mpstat", "load", "процесор",
    "операційн", "систем", "ram", "пам'ят", "uptime", "максимальн",
)
DOCKER_KEYWORDS = ("docker", "контейнер", "докер")
BAD_RESPONSE_MARKERS = (
    "не викликали функцію",
    "get_docker",
    "використайте наступний код",
    "спочатку використайте",
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
    """
    Повертає навантаження Linux: load average, uptime, mpstat (CPU).
    Використовуй для питань про CPU, RAM, навантаження — НЕ для Docker.
    """
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
    """
    Зчитує останні N рядків з файлу логів.
    Використовуй, коли користувач просить проаналізувати логи або помилки.
    """
    if not os.path.exists(file_path):
        return f"Файл {file_path} не знайдено."
    try:
        # Використовуємо tail для отримання останніх N рядків
        return subprocess.check_output(["tail", "-n", str(lines), file_path], text=True)
    except Exception as e:
        return f"Помилка читання файлу: {str(e)}"

@tool
def list_directory(path: str = "."):
    """
    Показує список файлів та папок у вказаній директорії.
    Використовуй це, щоб орієнтуватися у файловій системі.
    """
    try:
        return subprocess.check_output(["ls", "-F", path], text=True)
    except Exception as e:
        return f"Помилка доступу до папки: {str(e)}"

@tool
def execute_command(command: str):
    """
    Виконує команду в терміналі (наприклад: 'pwd', 'ls -la /home/user/course', 'mpstat 1 1').
    Кожен виклик — окремий shell; `cd` не діє між викликами — використовуй абсолютні шляхи.
    """
    try:
        result = subprocess.check_output(
            command, shell=True, text=True, stderr=subprocess.STDOUT
        )
        return result
    except subprocess.CalledProcessError as e:
        return f"Помилка при виконанні команди '{command}': {e.output}"
    except Exception as e:
        return f"Помилка: {str(e)}"

# --- НАЛАШТУВАННЯ ---

TOOLS = [get_system_load, execute_command, list_directory, read_log_tool, get_docker_status]
TOOL_BY_NAME = {t.name: t for t in TOOLS}

llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)


def is_metrics_question(text: str) -> bool:
    q = text.lower()
    return any(k in q for k in METRICS_KEYWORDS)


def is_docker_question(text: str) -> bool:
    q = text.lower()
    return any(k in q for k in DOCKER_KEYWORDS)


def is_bad_meta_response(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in BAD_RESPONSE_MARKERS)


def trim_session(session_id: str) -> None:
    history = sessions[session_id]
    if len(history) <= MAX_HISTORY_MESSAGES + 1:
        return
    sessions[session_id] = [history[0]] + history[-MAX_HISTORY_MESSAGES:]


def reset_session(session_id: str) -> None:
    sessions[session_id] = [SystemMessage(content=SYSTEM_PROMPT)]


def run_tool_loop(session_id: str):
    """Цикл tool_calls; повертає фінальну AIMessage."""
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
                output = "(порожній вивід — спробуй інший інструмент або повний шлях)"
            sessions[session_id].append(
                ToolMessage(tool_call_id=tool_call["id"], content=str(output))
            )

        response = llm_with_tools.invoke(sessions[session_id])

    return response


def answer_from_prefetched_data(user_q: str, tool_output: str) -> str:
    """Обхід: hermes3 часто не робить tool_calls — підсумовуємо реальні дані без них."""
    prompt = (
        f"Питання користувача: {user_q}\n\n"
        f"Фактичні дані з сервера (get_system_load):\n{tool_output}\n\n"
        "Дай чітку відповідь українською. Поясни цифри з виводу. "
        "Не згадуй Docker. Не кажи користувачу викликати інструменти."
    )
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )
    return (response.content or "").strip()


class QueryRequest(BaseModel):
    session_id: str
    question: str


@app.get("/health")
async def health():
    return {"status": "ok", "api_version": API_VERSION, "model": "hermes3"}


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

    if user_q.lower() in ("/reset", "reset", "скинути", "скидання"):
        reset_session(session_id)
        return {"answer": "Сесію скинуто. Можете ставити нові питання."}

    if session_id not in sessions:
        reset_session(session_id)

    # Питання про навантаження: спочатку збираємо дані на сервері (надійно)
    if is_metrics_question(user_q) and not is_docker_question(user_q):
        metrics = get_system_load.invoke({})
        answer = answer_from_prefetched_data(user_q, metrics)
        sessions[session_id].append(HumanMessage(content=user_q))
        sessions[session_id].append(AIMessage(content=answer))
        trim_session(session_id)
        return {"answer": answer}

    sessions[session_id].append(HumanMessage(content=user_q))
    trim_session(session_id)

    response = run_tool_loop(session_id)

    # hermes3 інколи відповідає текстом «виклич docker» замість tool_calls
    if not getattr(response, "tool_calls", None) and is_bad_meta_response(response.content or ""):
        reset_session(session_id)
        sessions[session_id].append(HumanMessage(content=user_q))
        if is_metrics_question(user_q):
            metrics = get_system_load.invoke({})
            answer = answer_from_prefetched_data(user_q, metrics)
            sessions[session_id].append(AIMessage(content=answer))
            return {"answer": answer}
        response = run_tool_loop(session_id)

    sessions[session_id].append(response)
    trim_session(session_id)

    answer = (response.content or "").strip()
    if not answer:
        answer = (
            "Агент не зміг сформулювати відповідь. Спробуйте /reset або "
            "«покажи навантаження CPU»."
        )

    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)