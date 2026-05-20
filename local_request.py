import requests

url = "http://127.0.0.1:8000/ask"
question = {"question": input("Enter your question: ")}

response = requests.post(url, json=question, timeout=120)
if not response.ok:
    print(f"Помилка {response.status_code}: {response.text}")
else:
    print(response.json()["answer"])
