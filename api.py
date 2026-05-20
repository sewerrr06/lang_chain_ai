from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import subprocess

app = FastAPI()

# 1. Інструмент для взаємодії з Docker
@tool
def get_docker_status():
    """
    Повертає список запущених Docker контейнерів.
    Викликай цей інструмент, коли користувач запитує:
    - Що запущено в Docker
    - Статус контейнерів
    - Чи працює якийсь сервіс
    """
    try:
        # Повертаємо результат команди docker ps
        return subprocess.check_output(["docker", "ps"], text=True)
    except Exception as e:
        return f"Помилка при виконанні docker ps: {str(e)}"

# 2. Налаштування моделі
# temperature=0 робить модель максимально логічною та послідовною
llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools([get_docker_status])

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    # Створюємо історію повідомлень з чіткими інструкціями
    messages = [
        SystemMessage(content=(
            "Ти — технічний AI-агент. Твоє завдання — допомагати з керуванням системою. "
            "У тебе є доступ до інструменту 'get_docker_status'. "
            "Якщо запит користувача пов'язаний з Docker, контейнерами або статусом сервісів, "
            "ТИ МАЄШ викликати цей інструмент."
        )),
        HumanMessage(content=request.question)
    ]
    
    # Перший виклик моделі
    response = llm_with_tools.invoke(messages)
    
    # Якщо модель вирішила викликати інструмент
    if response.tool_calls:
        print(f"DEBUG: Модель вирішила викликати інструмент: {response.tool_calls}")
        
        # Обробляємо виклик
        for tool_call in response.tool_calls:
            if tool_call["name"] == "get_docker_status":
                # Виконуємо код
                tool_output = get_docker_status()
                
                # Додаємо в історію повідомлення моделі (AIMessage) та результат (ToolMessage)
                messages.append(response)
                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"], 
                    content=tool_output
                ))
        
        # Фінальний виклик моделі: тепер вона "бачить" результат і пише відповідь
        final_response = llm_with_tools.invoke(messages)
        return {"answer": final_response.content}
    
    # Якщо модель не захотіла викликати інструмент, відповідаємо текстом
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 відкриває доступ для інших пристроїв через Tailscale
    uvicorn.run(app, host="0.0.0.0", port=8000)