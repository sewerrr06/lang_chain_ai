from fastapi import FastAPI
from pydantic import BaseModel
from langchain_ollama import ChatOllama
import subprocess

app = FastAPI()

# Модель для відповідей
llm = ChatOllama(model="llama3:8b")

class QueryRequest(BaseModel):
    question: str

def get_docker_ps():
    """Функція для отримання реального списку контейнерів"""
    try:
        # Виконуємо команду docker ps
        return subprocess.check_output(["docker", "ps"], text=True)
    except Exception as e:
        return f"Помилка при отриманні докерів: {str(e)}"

@app.post("/ask")
async def ask_question(request: QueryRequest):
    user_question = request.question.lower()
    
    # Логіка ручного визначення інструменту
    if any(keyword in user_question for keyword in ["докер", "docker", "контейнер"]):
        docker_data = get_docker_ps()
        
        # Формуємо промпт, куди вставляємо реальний вивід команди
        final_prompt = (
            f"Ось список запущених контейнерів Docker:\n{docker_data}\n\n"
            f"Користувач запитав: '{request.question}'. "
            "На основі наданого списку, дай зрозумілу відповідь користувачу. "
            "Якщо список порожній, скажи, що контейнери не запущені."
        )
    else:
        # Звичайний чат, якщо це не про Docker
        final_prompt = request.question

    # Отримуємо відповідь від LLM
    response = llm.invoke(final_prompt)
    
    return {"answer": response.content}

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 робить API доступним для мережі (Tailscale)
    uvicorn.run(app, host="0.0.0.0", port=8000)