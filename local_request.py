import os
import requests

# IP Linux-сервера в Tailscale (sewers-hp). Перевизначення: SERVER_IP=127.0.0.1 python local_request.py
SERVER_IP = os.environ.get("SERVER_IP", "100.113.28.5")
BASE_URL = f"http://{SERVER_IP}:8000"
URL = f"{BASE_URL}/ask"
HEALTH_URL = f"{BASE_URL}/health"

# Однаковий ID = спільна історія. Після оновлення api.py — новий ID або команда /reset
SESSION_ID = "session_v3"

EXIT_COMMANDS = {"exit", "quit", "q", "вихід"}


def ask_ai(question: str) -> None:
    payload = {
        "session_id": SESSION_ID,
        "question": question,
    }
    try:
        response = requests.post(URL, json=payload)
        if response.status_code == 200:
            print(f"\nАгент: {response.json()['answer']}\n")
        else:
            print(f"Помилка сервера: {response.status_code}\n")
    except requests.exceptions.ConnectionError:
        print(
            f"Не вдалося з'єднатися з {BASE_URL}.\n"
            "На Linux-сервері (sewers-hp) у папці проєкту запустіть API:\n"
            "  source venv/bin/activate && python api.py\n"
            "Перевірка: curl http://100.113.28.5:8000/health\n\n"
        )
    except Exception as e:
        print(f"Не вдалося з'єднатися з сервером: {e}\n")


def check_server() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"Сервер OK: {SERVER_IP} (api {data.get('api_version', '?')}, model {data.get('model', '?')})\n")
            return True
        print(f"Сервер відповів, але /health повернув {r.status_code}\n")
        return False
    except requests.exceptions.ConnectionError:
        print(
            f"API на {BASE_URL} не запущено (connection refused).\n"
            "Зайдіть на sewers-hp по SSH і виконайте:\n"
            "  cd <шлях до AI_langchain> && source venv/bin/activate && python api.py\n\n"
        )
        return False
    except Exception as e:
        print(f"Перевірка сервера не вдалася: {e}\n")
        return False


def main() -> None:
    print("Інтерактивний чат з AI-агентом. Введіть 'exit' або 'quit' для виходу.")
    print("Скинути історію на сервері: /reset\n")
    if not check_server():
        print("Можна продовжити — після запуску api.py на сервері запити запрацюють.\n")
    while True:
        try:
            question = input("Запитай щось: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо побачення!")
            break

        if not question:
            continue

        if question.lower() in EXIT_COMMANDS:
            print("До побачення!")
            break

        ask_ai(question)


if __name__ == "__main__":
    main()
