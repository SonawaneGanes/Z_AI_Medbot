// frontend/app.js
// AI MedBot - Pro frontend script
// Configured for: API_BASE = http://127.0.0.1:5000, endpoints: /chat and /upload
// Uses browser SpeechRecognition (if available) and SpeechSynthesis (prefers a natural female voice)

// ------------------------- Configuration -------------------------
const API_BASE = "http://127.0.0.1:5000";
const CHAT_URL = `${API_BASE}/chat`;
const UPLOAD_URL = `${API_BASE}/upload`;

// ------------------------- DOM elements -------------------------
const messagesEl = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const speakBtn = document.getElementById('speakBtn');
const uploadBtn = document.getElementById('uploadBtn');
const reportFile = document.getElementById('reportFile');
const typingIndicator = document.getElementById('typingIndicator');
const themeToggle = document.getElementById('themeToggle');
const appRoot = document.getElementById('app');

// ------------------------- Session & state -------------------------
const sessionId = "session-" + Math.random().toString(36).slice(2, 12);
let lastBotReply = "";
let currentAbortController = null;

// ------------------------- Utilities -------------------------
function escapeHtml(unsafe = "") {
  return String(unsafe).replace(/[&<"']/g, function (m) {
    return ({ '&': '&amp;', '<': '&lt;', '"': '&quot;', "'": '&#039;' }[m]);
  });
}

function addMessage(text, who = "bot", html = false) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg ${who}`;
  wrapper.innerHTML = html ? text : `<div class="content">${escapeHtml(text).replace(/\n/g,'<br>')}</div>`;
  const ts = document.createElement('div');
  ts.className = 'timestamp';
  ts.innerText = new Date().toLocaleTimeString();
  wrapper.appendChild(ts);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrapper;
}

function updateMessageElement(el, text) {
  const content = el.querySelector('.content');
  if (!content) return;
  content.innerHTML = escapeHtml(text).replace(/\n/g,'<br>');
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function progressiveType(el, text, charDelay = 8) {
  const content = el.querySelector('.content');
  if (!content) return;
  content.innerHTML = "";
  for (let i = 0; i < text.length; i++) {
    content.innerHTML += escapeHtml(text[i]).replace(/\n/g,'<br>');
    messagesEl.scrollTop = messagesEl.scrollHeight;
    await new Promise(r => setTimeout(r, charDelay));
  }
}

// ------------------------- Chat (streaming-friendly) -------------------------
async function sendMessageWithStreaming() {
  const text = messageInput.value.trim();
  if (!text) return;

  addMessage(text, "user");
  messageInput.value = "";
  const botEl = addMessage("", "bot"); // placeholder
  typingIndicator.classList.remove('hidden');

  const payload = { session_id: sessionId, message: text };

  // Abort previous request if any
  if (currentAbortController) {
    try { currentAbortController.abort(); } catch (e) {}
  }
  const controller = new AbortController();
  currentAbortController = controller;

  const maxRetries = 3;
  let attempt = 0;
  let success = false;
  let lastErr = null;

  while (attempt < maxRetries && !success) {
    attempt++;
    try {
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Server error ${res.status}: ${txt}`);
      }

      // If streaming body is available, read chunks; otherwise parse JSON
      if (res.body && typeof res.body.getReader === 'function') {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let acc = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          acc += chunk;
          // show incremental text (fast) for UX
          updateMessageElement(botEl, acc);
        }
        // Try parse JSON if server returned structured JSON
        let finalReply = acc;
        try {
          const parsed = JSON.parse(acc);
          if (parsed && parsed.reply) finalReply = parsed.reply;
        } catch (e) { /* fallback to raw text */ }
        lastBotReply = finalReply;
        await progressiveType(botEl, finalReply, 6);
        success = true;
      } else {
        const data = await res.json();
        const reply = data.reply || data.message || JSON.stringify(data);
        lastBotReply = reply;
        await progressiveType(botEl, reply, 8);
        success = true;
      }

    } catch (err) {
      lastErr = err;
      console.warn(`Attempt ${attempt} failed:`, err);

      if (err.name === 'AbortError') {
        updateMessageElement(botEl, "[Request cancelled]");
        typingIndicator.classList.add('hidden');
        currentAbortController = null;
        return;
      }

      const m = (err && err.message) ? err.message.toLowerCase() : "";
      if (m.includes("failed to fetch") || m.includes("refused") || m.includes("networkerror")) {
        updateMessageElement(botEl, `Network error (attempt ${attempt}/${maxRetries}). Retrying...`);
      } else {
        updateMessageElement(botEl, `Error: ${err.message || err}`);
      }
      await new Promise(r => setTimeout(r, 800 * attempt));
    }
  }

  if (!success) {
    const msg = lastErr && lastErr.message ? lastErr.message : "Unknown error";
    updateMessageElement(botEl, `Failed after ${maxRetries} attempts. ${msg}\nCheck backend at ${CHAT_URL}`);
  }

  typingIndicator.classList.add('hidden');
  currentAbortController = null;
}

// UI hooks for send
sendBtn.addEventListener('click', sendMessageWithStreaming);
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessageWithStreaming();
  }
});

// ------------------------- Speech-to-Text (mic) -------------------------
let recognition = null;
let micListening = false;
let noSpeechRetries = 0;
const MAX_NO_SPEECH_RETRIES = 2;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.continuous = false;

  recognition.onstart = () => {
    micListening = true;
    micBtn.classList.add('listening');
  };

  recognition.onend = () => {
    micListening = false;
    micBtn.classList.remove('listening');
  };

  recognition.onresult = (event) => {
    noSpeechRetries = 0;
    const transcript = event.results[0][0].transcript;
    messageInput.value = messageInput.value ? messageInput.value + " " + transcript : transcript;
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error", event);
    // handle 'no-speech' by retrying a few times, then notify
    if (event && event.error === "no-speech") {
      noSpeechRetries++;
      if (noSpeechRetries <= MAX_NO_SPEECH_RETRIES) {
        console.warn("No speech detected — retrying...", noSpeechRetries);
        try { recognition.stop(); } catch (e) {}
        setTimeout(() => {
          try { recognition.start(); } catch (e) { console.error(e); }
        }, 500 + noSpeechRetries * 200);
      } else {
        alert("I couldn't hear anything. Please check your microphone and try again.");
        noSpeechRetries = 0;
      }
    } else if (event && event.error === "not-allowed") {
      alert("Microphone access denied. Allow microphone permission and try again.");
    } else {
      // non-fatal: notify once
      console.warn("Speech recognition error:", event.error || event.message || event);
    }
  };

} else {
  micBtn.disabled = true;
  micBtn.title = "Speech-to-text not supported in this browser";
}

micBtn.addEventListener('click', () => {
  if (!recognition) return alert("Speech recognition not available in this browser.");
  try {
    if (!micListening) {
      noSpeechRetries = 0;
      recognition.start();
    } else {
      recognition.stop();
    }
  } catch (e) {
    console.error("Mic start/stop error", e);
  }
});

// ------------------------- Text-to-Speech (browser) -------------------------
// Choose a preferred female voice (F1: natural female) if available.
// Browser voices load asynchronously, so we query available voices and pick best-match.
let selectedVoice = null;
function pickFemaleVoice() {
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  // preference order: female with 'Female', 'FEMALE', 'Woman', 'en-US' natural vendor names
  const femaleKeywords = ["female", "woman", "zira", "samantha", "alloy", "voice", "serena", "native", "anna", "victoria", "google"];
  // Try to pick a voice that seems female and english
  let best = voices.find(v => /en(-|_)?/i.test(v.lang) && femaleKeywords.some(k => v.name.toLowerCase().includes(k)));
  if (!best) {
    // fallback: any voice where the name looks female-like
    best = voices.find(v => femaleKeywords.some(k => v.name.toLowerCase().includes(k)));
  }
  if (!best) {
    // fallback: first English voice
    best = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en'));
  }
  return best || voices[0];
}

// On some browsers voices aren't ready immediately; handle onvoiceschanged
function ensureSelectedVoice() {
  if (!selectedVoice) {
    selectedVoice = pickFemaleVoice();
  }
}
window.speechSynthesis.onvoiceschanged = () => {
  selectedVoice = pickFemaleVoice();
};

// speak text using selected voice
function speakText(text) {
  if (!('speechSynthesis' in window)) return;
  ensureSelectedVoice();
  const u = new SpeechSynthesisUtterance(text);
  if (selectedVoice) u.voice = selectedVoice;
  u.lang = 'en-US';
  u.rate = 1.0;
  u.pitch = 1.0;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

// Hook speak button to speak last reply
speakBtn.addEventListener('click', () => {
  if (!lastBotReply) {
    // try to find the last bot bubble
    const bots = Array.from(document.querySelectorAll('.msg.bot .content'));
    if (bots.length) lastBotReply = bots[bots.length - 1].innerText;
  }
  if (lastBotReply) speakText(lastBotReply);
  else alert("No bot reply to speak yet.");
});

// ------------------------- OCR Upload -------------------------
uploadBtn.addEventListener('click', async () => {
  const f = reportFile.files[0];
  if (!f) { alert("Choose a file first"); return; }
  addMessage(`Uploading "${f.name}" for OCR...`, "user");
  typingIndicator.classList.remove('hidden');

  try {
    const fd = new FormData();
    fd.append('file', f);
    const res = await fetch(UPLOAD_URL, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`Upload failed ${res.status}`);
    const data = await res.json();
    addMessage("OCR extracted text:\n\n" + (data.extracted_text || data.text || "[no text]"), "bot");
  } catch (err) {
    console.error("Upload error:", err);
    addMessage("Upload/OCR failed: " + (err.message || err), "bot");
  } finally {
    typingIndicator.classList.add('hidden');
  }
});

// ------------------------- Theme toggle -------------------------
themeToggle.addEventListener('click', () => {
  if (appRoot.classList.contains('dark')) {
    appRoot.classList.remove('dark'); appRoot.classList.add('light'); themeToggle.innerText = 'Dark';
  } else {
    appRoot.classList.remove('light'); appRoot.classList.add('dark'); themeToggle.innerText = 'Light';
  }
});

// ------------------------- Startup message -------------------------
addMessage("Hello! I'm AI MedBot — educational only. Describe symptoms, upload a report, or train me with QA pairs. I cannot provide diagnoses or prescriptions. A medical disclaimer is always included.", "bot");

// ------------------------- Helpful debug log -------------------------
console.log(`MedBot frontend ready. Chat endpoint: ${CHAT_URL}  Upload endpoint: ${UPLOAD_URL}`);
/* End of frontend/app.js */