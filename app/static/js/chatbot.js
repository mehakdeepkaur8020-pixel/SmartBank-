/**
 * SmartBank Hybrid AI Chatbot Client
 * Handles conversational queries, quick-replies, and secure session interaction.
 */

document.addEventListener("DOMContentLoaded", () => {
  const toggler = document.getElementById("chatbot-toggle");
  const windowEl = document.getElementById("chatbot-window");
  const closeBtn = document.getElementById("chat-close-btn");
  const clearBtn = document.getElementById("chat-clear-btn");
  const sendBtn = document.getElementById("chat-send-btn");
  const inputEl = document.getElementById("chat-input");
  const bodyEl = document.getElementById("chat-body");
  const suggestionsEl = document.getElementById("chat-suggestions");
  const modeBadge = document.getElementById("chat-mode-badge");

  if (!toggler || !windowEl) return;

  let conversationId = sessionStorage.getItem("smartbank_chat_conv_id") || null;

  function toggleChat() {
    windowEl.classList.toggle("active");
    if (windowEl.classList.contains("active")) {
      inputEl.focus();
      scrollToBottom();
    }
  }

  toggler.addEventListener("click", toggleChat);
  if (closeBtn) closeBtn.addEventListener("click", toggleChat);

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      sessionStorage.removeItem("smartbank_chat_conv_id");
      conversationId = null;
      bodyEl.innerHTML = "";
      renderBotMessage(
        "Conversation reset. Hello! I'm the SmartBank Assistant. How can I help you today?",
        "FAQ",
        ["Check My Balance", "Recent Transactions", "Check Loan Status", "How to Transfer Money"]
      );
    });
  }

  function scrollToBottom() {
    bodyEl.scrollTop = bodyEl.scrollHeight;
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMessageText(text) {
    let clean = escapeHtml(text);
    // Format bold **text**
    clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Format links [text](url) safely
    clean = clean.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary fw-bold text-decoration-underline">$1</a>');
    return clean;
  }

  function renderUserMessage(text) {
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble user";
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    bubble.innerHTML = `<div>${escapeHtml(text)}</div><div class="chat-time">${timeStr}</div>`;
    bodyEl.appendChild(bubble);
    scrollToBottom();
  }

  function renderBotMessage(text, mode, suggestions = []) {
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot";
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    bubble.innerHTML = `<div>${formatMessageText(text)}</div><div class="chat-time">${timeStr} • ${mode || 'Assistant'}</div>`;
    bodyEl.appendChild(bubble);

    if (modeBadge && mode) {
      modeBadge.textContent = mode === "AI" ? "AI Mode" : (mode === "TOOL_ASSISTED" ? "Secure Tool" : "FAQ Mode");
    }

    renderSuggestions(suggestions);
    scrollToBottom();
  }

  function renderSuggestions(suggestions) {
    if (!suggestionsEl) return;
    suggestionsEl.innerHTML = "";
    if (suggestions && suggestions.length > 0) {
      suggestions.forEach(s => {
        const pill = document.createElement("span");
        pill.className = "suggestion-pill";
        pill.textContent = s;
        suggestionsEl.appendChild(pill);
      });
      suggestionsEl.style.display = "flex";
    } else {
      suggestionsEl.style.display = "none";
    }
  }

  // Event delegation on suggestions container handles BOTH static and dynamic pills immediately
  if (suggestionsEl) {
    suggestionsEl.addEventListener("click", (e) => {
      const pill = e.target.closest(".suggestion-pill");
      if (pill) {
        const query = pill.textContent.trim();
        if (query) {
          submitMessage(query);
        }
      }
    });
  }

  function showTypingIndicator() {
    const dots = document.createElement("div");
    dots.id = "typing-indicator";
    dots.className = "typing-dots";
    dots.innerHTML = "<span></span><span></span><span></span>";
    bodyEl.appendChild(dots);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    const dots = document.getElementById("typing-indicator");
    if (dots) dots.remove();
  }

  async function submitMessage(overrideText = null) {
    const text = (overrideText !== null ? overrideText : inputEl.value).trim();
    if (!text) return;

    renderUserMessage(text);
    inputEl.value = "";
    inputEl.disabled = true;
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId
        })
      });

      hideTypingIndicator();
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.focus();

      if (!response.ok) {
        throw new Error("Server returned an error");
      }

      const data = await response.json();
      conversationId = data.conversation_id;
      sessionStorage.setItem("smartbank_chat_conv_id", conversationId);

      renderBotMessage(data.reply, data.mode, data.suggestions);
    } catch (err) {
      hideTypingIndicator();
      inputEl.disabled = false;
      sendBtn.disabled = false;
      renderBotMessage(
        "I'm sorry, an issue occurred communicating with the server. Please check your connection or contact bank support.",
        "FALLBACK",
        ["Check My Balance", "Track Application", "Contact support"]
      );
    }
  }

  if (sendBtn) sendBtn.addEventListener("click", () => submitMessage());

  if (inputEl) {
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitMessage();
      }
    });
  }
});
