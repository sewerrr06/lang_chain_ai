from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import subprocess

app = FastAPI()

# --- ІНСТРУМЕНТИ ---

@tool
def get_docker_tool():
    """Повертає список запущених Docker контейнерів. Використовуй це для питань про докери."""
    try:
        return subprocess.check_output(["docker", "ps"], text=True)
    except Exception as e:
        return f"Помилка Docker: {str(e)}"

@tool
def get_system_stats():
    """Повертає завантаженість системи: RAM, CPU load (uptime). Використовуй це, коли питають про ресурси, навантаження, CPU або RAM."""
    try:
        mem = subprocess.check_output(["free", "-h"], text=True)
        load = subprocess.check_output(["uptime"], text=True)
        return f"Пам'ять (RAM):\n{mem}\nНавантаження (Load): {load}"
    except Exception as e:
        return f"Помилка системи: {str(e)}"

# --- НАЛАШТУВАННЯ ---

llm = ChatOllama(model="hermes3", temperature=0)
# Додаємо список інструментів
llm_with_tools = llm.bind_tools([get_docker_tool, get_system_stats])

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    # Явно перераховуємо інструменти в системному промпті для надійності
    system_prompt = (
        "Ти — системний AI-агент. Тобі доступні інструменти:\n"
        "1. get_docker_tool - для перевірки Docker контейнерів.\n"
        "2. get_system_stats - для перевірки навантаження CPU/RAM.\n"
        "Якщо користувач питає про це — ВИКОРИСТОВУЙ відповідний інструмент. НЕ вигадуй дані."
    )
    
    # Безпечне вилучення даних
    data = request.model_dump()
    user_q = data.get("question")
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_q)
    ]
    
    # Перший виклик моделі
    response = llm_with_tools.invoke(messages)
    
    # Цикл обробки інструментів (може викликати кілька)
    if response.tool_calls:
        print(f"DEBUG: Агент вирішив викликати: {response.tool_calls}")
        messages.append(response) # Додаємо запит моделі на інструмент
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_id = tool_call["id"]
            
            # Виконання
            if tool_name == "get_docker_tool":
                output = get_docker_tool.invoke({})
            elif tool_name == "get_system_stats":
                output = get_system_stats.invoke({})
            else:
                output = "Невідомий інструмент."
                
            messages.append(ToolMessage(tool_call_id=tool_id, content=output))
        
        # Фінальний виклик з результатами
        final_response = llm_with_tools.invoke(messages)
        return {"answer": final_response.content}
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)