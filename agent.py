import ollama

def chat_with_agent(user_input):
    # System prompt задає роль та обмеження для моделі
    system_prompt = """
    Ти — професійний Cybersecurity Assistant. 
    Твоє завдання — аналізувати код та логи на наявність вразливостей.
    Будь стислим, технічним та давай рекомендації згідно з кращими практиками.
    """
    
    response = ollama.chat(model='llama3:8b', messages=[
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_input},
    ])
    
    return response['message']['content']

# Тест
if __name__ == "__main__":
    test_query = "Як захистити FastAPI ендпоінт від SQL-ін'єкцій?"
    result = chat_with_agent(test_query)
    print(f"Агент: {result}")