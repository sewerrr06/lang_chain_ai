const API_BASE_KEY = "ai_agent_api_base";
const SESSION_KEY = "ai_agent_session_id";

function normalizeApiBase(url) {
  return (url || "").trim().replace(/\/+$/, "");
}

function getDefaultApiBase() {
  if (window.APP_CONFIG?.API_BASE) {
    return normalizeApiBase(window.APP_CONFIG.API_BASE);
  }
  // Якщо фронт у Docker/nginx з проксі /api
  if (window.location.pathname.startsWith("/api")) {
    return normalizeApiBase(window.location.origin + "/api");
  }
  return "http://127.0.0.1:8000";
}

function getApiBase() {
  const fromInput = document.getElementById("api-url")?.value;
  if (fromInput?.trim()) {
    return normalizeApiBase(fromInput);
  }
  return normalizeApiBase(localStorage.getItem(API_BASE_KEY) || getDefaultApiBase());
}

function saveApiBase(url) {
  const base = normalizeApiBase(url);
  localStorage.setItem(API_BASE_KEY, base);
  const input = document.getElementById("api-url");
  if (input) input.value = base;
  return base;
}

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("form");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("send");
const sessionInput = document.getElementById("session-id");
const apiUrlInput = document.getElementById("api-url");
const newSessionBtn = document.getElementById("new-session");
const resetSessionBtn = document.getElementById("reset-session");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");

function randomSessionId() {
  return "session_" + Math.random().toString(36).slice(2, 10);
}

function getSessionId() {
  let id = sessionInput.value.trim();
  if (!id) {
    id = localStorage.getItem(SESSION_KEY) || randomSessionId();
    sessionInput.value = id;
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function setLoading(on) {
  sendBtn.disabled = on;
  questionEl.disabled = on;
  let typing = document.getElementById("typing-indicator");
  if (on) {
    if (!typing) {
      typing = document.createElement("div");
      typing.id = "typing-indicator";
      typing.className = "typing";
      typing.textContent = "Агент думає…";
      chatEl.appendChild(typing);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
  } else if (typing) {
    typing.remove();
  }
}

async function checkHealth() {
  const base = getApiBase();
  try {
    const res = await fetch(base + "/health", { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    statusDot.className = "status-dot online";
    statusText.textContent = `OK · ${data.model} · v${data.api_version}`;
    return true;
  } catch (e) {
    statusDot.className = "status-dot offline";
    statusText.textContent = `API недоступний (${base})`;
    return false;
  }
}

async function apiPost(path, body) {
  const base = getApiBase();
  const res = await fetch(base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Помилка " + res.status);
  }
  return data;
}

async function resetSession() {
  const session_id = getSessionId();
  try {
    await apiPost("/reset", { session_id, question: "" });
    appendMessage("system", "Історію сесії скинуто.");
  } catch (e) {
    appendMessage("error", "Не вдалося скинути: " + e.message);
  }
}

async function ask(question) {
  const session_id = getSessionId();
  setLoading(true);
  try {
    const data = await apiPost("/ask", { session_id, question });
    appendMessage("agent", data.answer || "(порожня відповідь)");
  } catch (e) {
    const hint =
      e.message.includes("Failed to fetch") || e.message.includes("NetworkError")
        ? " Перевірте URL API, CORS на сервері (.env CORS_ORIGINS) і що порт 8000 відкритий."
        : "";
    appendMessage("error", "Помилка: " + e.message + hint);
  } finally {
    setLoading(false);
    questionEl.focus();
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = questionEl.value.trim();
  if (!q) return;
  saveApiBase(apiUrlInput.value);
  appendMessage("user", q);
  questionEl.value = "";
  ask(q);
});

questionEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

apiUrlInput.addEventListener("change", () => {
  saveApiBase(apiUrlInput.value);
  checkHealth();
});

newSessionBtn.addEventListener("click", () => {
  const id = randomSessionId();
  sessionInput.value = id;
  localStorage.setItem(SESSION_KEY, id);
  chatEl.innerHTML = "";
  appendMessage("system", "Нова сесія: " + id);
});

resetSessionBtn.addEventListener("click", resetSession);

sessionInput.addEventListener("change", () => {
  const id = sessionInput.value.trim() || randomSessionId();
  sessionInput.value = id;
  localStorage.setItem(SESSION_KEY, id);
});

apiUrlInput.value = localStorage.getItem(API_BASE_KEY) || getDefaultApiBase();
saveApiBase(apiUrlInput.value);

sessionInput.value = localStorage.getItem(SESSION_KEY) || randomSessionId();
localStorage.setItem(SESSION_KEY, sessionInput.value);

appendMessage(
  "system",
  "Локальний чат → API на сервері. Змініть URL зверху, якщо потрібно."
);
checkHealth();
setInterval(checkHealth, 30000);
