const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const welcomeEl = document.getElementById("welcome");
const chatScroll = document.getElementById("chatScroll");
const toast = document.getElementById("toast");
const newChatBtn = document.getElementById("newChatBtn");
const menuBtn = document.getElementById("menuBtn");
const sidebar = document.getElementById("sidebar");

let conversation = [];
let busy = false;
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function scrollToBottom() {
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: "smooth" });
}

function addMessage(role, content = "") {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "Y" : "A";

  const body = document.createElement("div");
  body.className = "message-body";

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "YOU" : "APEX · F1 ANALYST";

  const text = document.createElement("div");
  text.className = "message-text";
  text.textContent = content;

  body.append(label, text);
  wrapper.append(avatar, body);
  messagesEl.append(wrapper);
  scrollToBottom();
  return text;
}

// Render model output as text with lightweight Markdown support.
// All model text is escaped before formatting, preventing HTML injection.
function escapeHTML(value) {
  return value.replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

function renderMarkdown(raw) {
  const safe = escapeHTML(raw);
  const codeBlocks = [];
  let out = safe.replace(/```([\s\S]*?)```/g, (_, code) => {
    codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return `%%CODEBLOCK${codeBlocks.length - 1}%%`;
  });
  out = out
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^### (.+)$/gm, "<strong>$1</strong>")
    .replace(/^## (.+)$/gm, "<strong>$1</strong>")
    .replace(/^# (.+)$/gm, "<strong>$1</strong>")
    .replace(/^\s*[-*] (.+)$/gm, "• $1")
    .replace(/\n/g, "<br>");
  out = out.replace(/%%CODEBLOCK(\d+)%%/g, (_, i) => codeBlocks[Number(i)]);
  return out;
}

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
  sendBtn.querySelector("span:first-child").textContent = value ? "THINKING" : "SEND";
  inputEl.disabled = value;
}

function fitTextarea() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 150)}px`;
}

async function sendMessage(prefill = null) {
  if (busy) return;
  const content = (prefill ?? inputEl.value).trim();
  if (!content) return;
  if (content.length > 4000) {
    showToast("Please keep your message under 4,000 characters.");
    return;
  }

  welcomeEl.hidden = true;
  addMessage("user", content);
  conversation.push({ role: "user", content });
  inputEl.value = "";
  fitTextarea();
  setBusy(true);

  const answerEl = addMessage("assistant", "");
  const cursor = document.createElement("span");
  cursor.className = "typing-cursor";
  answerEl.append(cursor);

  try {
    // Send only recent context to keep requests bounded.
    const context = conversation.slice(-20);
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: context })
    });

    if (!response.ok) {
      let detail = "The request failed. Please try again.";
      try {
        const errorData = await response.json();
        detail = errorData.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    if (!response.body) throw new Error("Streaming is not supported by this browser.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullAnswer = "";
    let finished = false;

    while (!finished) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        const line = frame.split("\n").find(row => row.startsWith("data: "));
        if (!line) continue;
        let data;
        try { data = JSON.parse(line.slice(6)); } catch (_) { continue; }
        if (data.token) {
          fullAnswer += data.token;
          answerEl.innerHTML = renderMarkdown(fullAnswer);
          answerEl.append(cursor);
          scrollToBottom();
        }
        if (data.error) {
          throw new Error(data.error);
        }
        if (data.done) finished = true;
      }
    }

    cursor.remove();
    if (!fullAnswer.trim()) {
      answerEl.textContent = "I couldn't generate a response. Please try again.";
    } else {
      answerEl.innerHTML = renderMarkdown(fullAnswer);
      conversation.push({ role: "assistant", content: fullAnswer });
    }
  } catch (error) {
    cursor.remove();
    answerEl.textContent = error.message || "Something went wrong. Please try again.";
    answerEl.style.color = "#ff7785";
    // Remove the unanswered user message from retained context if the call failed.
    conversation.pop();
    showToast("Could not complete the response.");
  } finally {
    setBusy(false);
    inputEl.focus();
    scrollToBottom();
  }
}

sendBtn.addEventListener("click", () => sendMessage());
inputEl.addEventListener("input", fitTextarea);
inputEl.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

document.querySelectorAll("[data-prompt]").forEach(button => {
  button.addEventListener("click", () => {
    if (busy) return;
    sendMessage(button.dataset.prompt);
    sidebar.classList.remove("open");
  });
});

newChatBtn.addEventListener("click", () => {
  if (busy) return;
  conversation = [];
  messagesEl.replaceChildren();
  welcomeEl.hidden = false;
  inputEl.value = "";
  fitTextarea();
  sidebar.classList.remove("open");
  inputEl.focus();
});

menuBtn?.addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("click", event => {
  if (window.innerWidth <= 760 &&
      sidebar.classList.contains("open") &&
      !sidebar.contains(event.target) &&
      !menuBtn.contains(event.target)) {
    sidebar.classList.remove("open");
  }
});
