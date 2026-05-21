import requests

# IP твого AI-ноутбука в мережі Tailscale
SERVER_IP = "100.113.28.5"
URL = f"http://{SERVER_IP}:8000/ask"

# Будь-який ідентифікатор сесії — однаковий ID = спільна історія діалогу
SESSION_ID = "my_session"

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
    except Exception as e:
        print(f"Не вдалося з'єднатися з сервером: {e}\n")


def main() -> None:
    print("Інтерактивний чат з AI-агентом. Введіть 'exit' або 'quit' для виходу.\n")
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
