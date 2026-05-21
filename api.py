from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import subprocess

app = FastAPI()

# 1. Функція виконання команди (чиста логіка)
def get_docker_status_logic():
    try:
        return subprocess.check_output(["docker", "ps"], text=True)
    except Exception as e:
        return f"Помилка при виконанні docker ps: {str(e)}"

# 2. Інструмент для моделі
@tool
def get_docker_tool():
    """Використовуй цей інструмент для отримання списку запущених Docker контейнерів."""
    return get_docker_status_logic()

# 3. Налаштування моделі
llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools([get_docker_tool])

class QueryRequest(BaseModel):
    question: str

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/ask")
async def ask_question(request: QueryRequest):
    # БЕЗПЕЧНИЙ ПІДХІД: Перетворюємо об'єкт Pydantic на словник
    # Це обходить конфлікт версій Pydantic V1/V2
    request_data = request.model_dump() 
    question_text = request_data.get("question")
    
    messages = [
        SystemMessage(content=(
            "Ти — технічний AI-агент. Твоє завдання — допомагати з керуванням системою. "
            "У тебе є інструмент 'get_docker_tool'. "
            "Якщо запит стосується Docker або контейнерів, ТИ МАЄШ викликати get_docker_tool."
        )),
        HumanMessage(content=question_text)
    ]
    
    # Виклик моделі
    response = llm_with_tools.invoke(messages)
    
    # Перевірка на tool_calls
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "get_docker_tool":
                tool_output = get_docker_status_logic()
                
                messages.append(response)
                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"], 
                    content=tool_output
                ))
        
        # Фінальна відповідь
        final_response = llm_with_tools.invoke(messages)
        return {"answer": final_response.content}
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)