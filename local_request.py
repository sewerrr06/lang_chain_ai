import requests

# IP твого AI-ноутбука в мережі Tailscale
SERVER_IP = "100.113.28.5"
URL = f"http://{SERVER_IP}:8000/ask"

# Будь-який ідентифікатор сесії — однаковий ID = спільна історія діалогу
SESSION_ID = "my_session"

def ask_ai():
    question = input("Запитай щось: ")
    payload = {
        "session_id": SESSION_ID,
        "question": question,
    }
    try:
        response = requests.post(URL, json=payload)
        if response.status_code == 200:
            print(f"\nАгент: {response.json()['answer']}")
        else:
            print(f"Помилка сервера: {response.status_code}")
    except Exception as e:
        print(f"Не вдалося з'єднатися з сервером: {e}")

if __name__ == "__main__":
    ask_ai()