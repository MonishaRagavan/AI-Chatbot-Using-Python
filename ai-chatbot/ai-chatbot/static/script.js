// Page elements (IDs match templates/index.html)
const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");

const WELCOME_MESSAGE = "Hi! 👋 I'm your AI assistant. Ask me a question, or try one of these:";
const EXAMPLE_PROMPTS = [
  "Explain Python in simple words",
  "Give me 3 tips for studying",
  "What is Flask used for?",
];
const MAX_HISTORY = 20;

let history = [];      // conversation so far, sent to the server each time
let isLoading = false; // true while waiting for the AI (blocks double-sending)

function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

// textContent (not innerHTML) keeps the page safe from injected HTML (XSS).
function addMessage(role, text, isError = false) {
  const row = document.createElement("div");
  row.className = "message " + role + (isError ? " error" : "");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function showWelcome() {
  addMessage("bot", WELCOME_MESSAGE);
  const box = document.createElement("div");
  box.className = "suggestions";
  box.id = "suggestions";
  EXAMPLE_PROMPTS.forEach((prompt) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = prompt;
    chip.addEventListener("click", () => sendMessage(prompt));
    box.appendChild(chip);
  });
  chatWindow.appendChild(box);
}

function removeSuggestions() {
  const box = document.getElementById("suggestions");
  if (box) box.remove();
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "message bot";
  row.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function setLoading(state) {
  isLoading = state;
  userInput.disabled = state;
  sendBtn.disabled = state;
  sendBtn.textContent = state ? "..." : "Send";
  if (!state) userInput.focus();
}

function autoResize() {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || isLoading) return; // ignore empty or repeated submissions

  removeSuggestions();
  addMessage("user", text);
  userInput.value = "";
  autoResize();
  setLoading(true);
  const typingRow = showTyping();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: history }),
    });

    let data = {};
    try { data = await response.json(); } catch (e) { /* reply was not JSON */ }

    if (!response.ok) {
      throw new Error(data.error || "Something went wrong (error " + response.status + ").");
    }

    addMessage("bot", data.reply);
    history.push({ role: "user", content: text });
    history.push({ role: "assistant", content: data.reply });
    history = history.slice(-MAX_HISTORY);
  } catch (err) {
    // A TypeError from fetch means the server could not be reached.
    const message = err instanceof TypeError
      ? "Cannot reach the server. Check your connection and try again."
      : err.message;
    addMessage("bot", message, true);
  } finally {
    typingRow.remove();
    setLoading(false);
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(userInput.value);
});

userInput.addEventListener("keydown", (event) => {
  // Enter sends. Shift+Enter adds a new line.
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
userInput.addEventListener("input", autoResize);

clearBtn.addEventListener("click", () => {
  if (isLoading) return;
  history = [];
  chatWindow.innerHTML = "";
  showWelcome();
});

showWelcome();
userInput.focus();
