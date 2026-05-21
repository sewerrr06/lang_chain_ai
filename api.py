from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import subprocess
import os

app = FastAPI()

# --- ПАМ'ЯТЬ (Історія діалогів) ---
# Структура: { session_id: [messages] }
sessions = {}
MAX_TOOL_ITERATIONS = 10
MAX_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = (
    "Ти — технічний AI-агент на Linux-сервері. Тобі доступні інструменти:\n"
    "1. get_docker_status — список запущених Docker контейнерів.\n"
    "2. read_log_tool — останні N рядків лог-файлу (потрібен шлях).\n"
    "3. list_directory — файли й папки в директорії (path).\n"
    "4. execute_command — shell-команди (pwd, ls, mpstat, top тощо).\n"
    "Правила:\n"
    "- ЗАВЖДИ викликай інструмент, якщо потрібні факти з системи. Не вигадуй цифри, шляхи чи списки файлів.\n"
    "- Кожна execute_command запускається в НОВОМУ shell: `cd` не зберігається між викликами. "
    "Замість «зайти в папку» використовуй повний шлях: list_directory('/home/sewer/course') "
    "або execute_command('ls -la /home/sewer/course').\n"
    "- Для CPU/навантаження: execute_command('mpstat 1 1') або "
    "execute_command(\"grep 'cpu ' /proc/stat; cat /proc/loadavg\") і поясни РЕАЛЬНИЙ вивід. "
    "Load average (напр. 1.31) — це НЕ відсотки CPU.\n"
    "- Якщо інструмент повернув порожній рядок — спробуй іншу команду або шлях, не мовчи."
)

# --- ІНСТРУМЕНТИ ---

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

TOOLS = [get_docker_status, read_log_tool, list_directory, execute_command]
TOOL_BY_NAME = {t.name: t for t in TOOLS}

llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools(TOOLS)


def trim_session(session_id: str) -> None:
    history = sessions[session_id]
    if len(history) <= MAX_HISTORY_MESSAGES + 1:
        return
    sessions[session_id] = [history[0]] + history[-MAX_HISTORY_MESSAGES:]


class QueryRequest(BaseModel):
    session_id: str  # Додаємо ID сесії для пам'яті
    question: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    session_id = request.session_id
    user_q = request.question
    
    if session_id not in sessions:
        sessions[session_id] = [SystemMessage(content=SYSTEM_PROMPT)]

    sessions[session_id].append(HumanMessage(content=user_q))
    trim_session(session_id)

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
                output = "(команда виконана, вивід порожній — спробуй іншу команду або повний шлях)"
            sessions[session_id].append(
                ToolMessage(tool_call_id=tool_call["id"], content=str(output))
            )

        response = llm_with_tools.invoke(sessions[session_id])

    sessions[session_id].append(response)
    trim_session(session_id)

    answer = (response.content or "").strip()
    if not answer:
        answer = (
            "Агент не зміг сформулювати відповідь (модель не викликала інструменти "
            "або потрібен ще один крок). Спробуйте: «покажи вміст /home/sewer/course»."
        )

    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)