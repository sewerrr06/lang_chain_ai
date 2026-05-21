from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
import subprocess

app = FastAPI()

def get_docker_status_logic():
    print("DEBUG: Спроба виконання docker ps...")
    try:
        # Виконуємо команду
        result = subprocess.check_output(["docker", "ps"], text=True)
        print(f"DEBUG: Результат docker ps: {result[:50]}...") # Лог перших 50 символів
        return result
    except Exception as e:
        error = f"Помилка виконання: {str(e)}"
        print(f"DEBUG: {error}")
        return error

@tool
def get_docker_tool():
    """Використовуй цей інструмент для отримання списку запущених Docker контейнерів."""
    return get_docker_status_logic()

llm = ChatOllama(model="hermes3", temperature=0)
llm_with_tools = llm.bind_tools([get_docker_tool])

@app.post("/ask")
async def ask_question(request: BaseModel):
    # ПРИВЕДЕННЯ ДО СТАНДАРТУ:
    # Явно кажемо моделі: "ТИ НЕ МАЄШ ПРАВА пояснювати як робити, ти маєш РОБИТИ"
    messages = [
        SystemMessage(content=(
            "Ти — системний адміністратор. Твоє завдання — виконувати команди. "
            "Коли користувач питає про докери, ти МАЄШ викликати get_docker_tool. "
            "НІКОЛИ не пояснюй, як користувачу самому ввести docker ps. Тільки результат інструменту."
        )),
        HumanMessage(content=request.question)
    ]
    
    response = llm_with_tools.invoke(messages)
    
    if response.tool_calls:
        print(f"DEBUG: Модель вирішила викликати інструмент: {response.tool_calls}")
        for tool_call in response.tool_calls:
            if tool_call["name"] == "get_docker_tool":
                tool_output = get_docker_status_logic()
                messages.append(response)
                messages.append(ToolMessage(tool_call_id=tool_call["id"], content=tool_output))
        
        final_response = llm_with_tools.invoke(messages)
        return {"answer": final_response.content}
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)