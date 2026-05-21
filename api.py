from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import subprocess
import os

app = FastAPI()

# --- ПАМ'ЯТЬ (Історія діалогів) ---
# Структура: { session_id: [messages] }
sessions = {}

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
        return subprocess.check_output(["tail", f"-n {lines}", file_path], text=True)
    except Exception as e:
        return f"Помилка читання файлу: {str(e)}"

# --- НАЛАШТУВАННЯ ---

llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools([get_docker_status, read_log_tool])

class QueryRequest(BaseModel):
    session_id: str  # Додаємо ID сесії для пам'яті
    question: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    session_id = request.session_id
    user_q = request.question
    
    # Ініціалізація історії для нової сесії
    if session_id not in sessions:
        sessions[session_id] = [
            SystemMessage(content=(
                "Ти — технічний AI-агент. Тобі доступні інструменти:\n"
                "1. get_docker_status - для Docker.\n"
                "2. read_log_tool - для читання логів (потрібен шлях до файлу).\n"
                "Пам'ятай контекст попередніх повідомлень. Якщо помилка в логах - аналізуй її."
            ))
        ]
    
    # Додаємо питання користувача в історію
    sessions[session_id].append(HumanMessage(content=user_q))
    
    # Виклик моделі з повною історією
    response = llm_with_tools.invoke(sessions[session_id])
    
    # Якщо модель викликає інструменти
    if response.tool_calls:
        sessions[session_id].append(response) # Додаємо запит моделі
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Виконання
            if tool_name == "get_docker_status":
                output = get_docker_status.invoke({})
            elif tool_name == "read_log_tool":
                output = read_log_tool.invoke(tool_args)
            else:
                output = "Невідомий інструмент."
                
            sessions[session_id].append(ToolMessage(tool_call_id=tool_call["id"], content=output))
        
        # Фінальний виклик
        response = llm_with_tools.invoke(sessions[session_id])
    
    # Додаємо фінальну відповідь моделі в історію
    sessions[session_id].append(response)
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)