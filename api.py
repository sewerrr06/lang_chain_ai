from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import subprocess

app = FastAPI()

# 1. Ця функція виконує реальну команду (проста Python-функція)
def get_docker_status_logic():
    try:
        return subprocess.check_output(["docker", "ps"], text=True)
    except Exception as e:
        return f"Помилка при виконанні docker ps: {str(e)}"

# 2. Це інструмент для AI (обгортка над нашою функцією)
@tool
def get_docker_tool():
    """
    Використовуй цей інструмент, щоб отримати список запущених Docker контейнерів.
    Викликай його, якщо запит стосується Docker або статусу контейнерів.
    """
    return get_docker_status_logic()

# 3. Налаштування моделі
llm = ChatOllama(model="hermes3", temperature=0)
# Прив'язуємо інструмент до моделі
llm_with_tools = llm.bind_tools([get_docker_tool])

class QueryRequest(BaseModel):
    question: str

@app.get("/health")
async def health_check():
    return {"status": "ok", "model": "hermes3"}

@app.post("/ask")
async def ask_question(request: QueryRequest):
    messages = [
        SystemMessage(content=(
            "Ти — технічний AI-агент. У тебе є інструмент 'get_docker_tool'. "
            "Якщо користувач питає про Docker або контейнери, ТИ МАЄШ викликати цей інструмент."
        )),
        HumanMessage(content=request.question)
    ]
    
    # Виклик моделі
    response = llm_with_tools.invoke(messages)
    
    # Перевіряємо чи модель хоче використати інструмент
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # Перевіряємо ім'я інструменту
            if tool_call["name"] == "get_docker_tool":
                # ВИКЛИКАЄМО ЧИСТУ ФУНКЦІЮ (не інструмент!)
                tool_output = get_docker_status_logic()
                
                # Додаємо історію
                messages.append(response)
                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"], 
                    content=tool_output
                ))
        
        # Отримуємо фінальну відповідь на основі даних
        final_response = llm_with_tools.invoke(messages)
        return {"answer": final_response.content}
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)