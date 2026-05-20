import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama

# 1. Завантаження даних
loader = TextLoader("data.txt", encoding="utf-8")
documents = loader.load()

# 2. Розбиття на шматки (Chunking)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
docs = text_splitter.split_documents(documents)

# 3. Ініціалізація моделей
# Використовуємо твою модель для ембеддінгів
embeddings = OllamaEmbeddings(model="nomic-embed-text")
# Використовуємо твою LLM для відповідей
llm = ChatOllama(model="llama3:8b")

# 4. Створення векторної БД (Chroma)
# Ми зберігаємо вектори в папці ./chroma_db
vectorstore = Chroma.from_documents(
    documents=docs, 
    embedding=embeddings,
    persist_directory="./chroma_db"
)

# 5. Пошук та відповідь
query = "Які технології використовуються в TeleNote?"
retriever = vectorstore.as_retriever(search_kwargs={"k": 2}) # Знайти 2 найбільш схожі шматки
context_docs = retriever.invoke(query)

# Формуємо промпт
context_text = "\n\n".join([doc.page_content for doc in context_docs])
prompt = f"Використовуючи цей контекст: {context_text}, дай відповідь на питання: {query}"

# Отримуємо відповідь
response = llm.invoke(prompt)
print(f"Відповідь агента: {response.content}")