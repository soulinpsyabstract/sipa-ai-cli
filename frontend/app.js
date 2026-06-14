/* ===== SIPA AI — app.js ===== */
'use strict';

// ── Config ──────────────────────────────────────────────────────────────────
const CFG = {
  api:      localStorage.getItem('sipa_api')      || 'http://localhost:5003',
  timeout:  parseInt(localStorage.getItem('sipa_timeout') || '90', 10),
  markdown: localStorage.getItem('sipa_markdown') !== 'false',
};

// ── Session ──────────────────────────────────────────────────────────────────
function getOrCreateSessionId() {
  let id = localStorage.getItem('sipa_session_id');
  if (!id) {
    id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
    localStorage.setItem('sipa_session_id', id);
  }
  return id;
}

let SESSION_ID = getOrCreateSessionId();
let selectedLayer = 'auto';
let isLoading = false;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const elMessages       = $('messages');
const elTyping         = $('typing-indicator');
const elInput          = $('user-input');
const elSend           = $('btn-send');
const elStatus         = $('status-indicator');
const elStatusLabel    = elStatus.querySelector('.status-label');
const elLayerInfo      = $('layer-info');
const elSessionLabel   = $('session-id-label');
const elSettingsModal  = $('settings-modal');
const elModalSessionId = $('modal-session-id');

// ── marked.js config ─────────────────────────────────────────────────────────
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
  });
}

function renderMarkdown(text) {
  if (!CFG.markdown || typeof marked === 'undefined') {
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
  }
  try { return marked.parse(text); }
  catch { return text; }
}

// ── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() {
  setStatus('checking', 'проверка…');
  try {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), 8000);
    const res = await fetch(`${CFG.api}/health`, { signal: ctrl.signal });
    clearTimeout(tid);
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      const label = data.status === 'ok' ? 'online' : (data.status || 'online');
      setStatus('online', label);
    } else {
      setStatus('offline', `${res.status}`);
    }
  } catch {
    setStatus('offline', 'offline');
  }
}

function setStatus(cls, label) {
  elStatus.className = `status ${cls}`;
  elStatusLabel.textContent = label;
}

// Poll health every 30s
checkHealth();
setInterval(checkHealth, 30000);

// ── Fetch models (optional) ───────────────────────────────────────────────────
async function fetchModels() {
  try {
    const res = await fetch(`${CFG.api}/models`);
    if (!res.ok) return;
    const data = await res.json();
    // data expected: { layers: { L01: { model: "...", desc: "..." }, ... } }
    if (data.layers) {
      populateLayerInfo(data.layers);
    }
  } catch { /* silently ignore */ }
}

function populateLayerInfo(layers) {
  // Store for tooltip/display on hover
  window._sipaLayers = layers;
}

fetchModels();

// ── Layer selector ────────────────────────────────────────────────────────────
document.querySelectorAll('.layer-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.layer-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedLayer = btn.dataset.layer;

    // Show layer info if available
    const layerData = window._sipaLayers?.[selectedLayer];
    if (layerData && selectedLayer !== 'auto') {
      elLayerInfo.textContent = layerData.model
        ? `${selectedLayer}: ${layerData.model}` + (layerData.desc ? ` — ${layerData.desc}` : '')
        : '';
      elLayerInfo.classList.toggle('hidden', !elLayerInfo.textContent);
    } else {
      elLayerInfo.classList.add('hidden');
    }
  });
});

// ── Chat history (for display only) ──────────────────────────────────────────
const chatHistory = [];

function appendMessage(role, content, meta = null) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (role === 'ai' || role === 'error') {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    // User: plain text, escape HTML
    const p = document.createElement('p');
    p.textContent = content;
    bubble.appendChild(p);
  }

  if (meta && (meta.layer || meta.model || meta.elapsed)) {
    const metaEl = document.createElement('div');
    metaEl.className = 'meta';
    if (meta.layer) {
      const span = document.createElement('span');
      span.className = 'layer-tag';
      span.textContent = meta.layer;
      metaEl.appendChild(span);
    }
    if (meta.model) {
      const span = document.createElement('span');
      span.className = 'model-tag';
      span.textContent = meta.model;
      metaEl.appendChild(span);
    }
    if (meta.elapsed != null) {
      const span = document.createElement('span');
      span.className = 'elapsed-tag';
      span.textContent = `${meta.elapsed}s`;
      metaEl.appendChild(span);
    }
    bubble.appendChild(metaEl);
  }

  wrapper.appendChild(bubble);
  elMessages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function scrollToBottom() {
  const win = document.getElementById('chat-window');
  win.scrollTop = win.scrollHeight;
}

function clearChat() {
  elMessages.innerHTML = '';
  chatHistory.length = 0;
  appendMessage('ai', 'Чат очищен. Новая сессия начата.', null);
}

// ── Send message ──────────────────────────────────────────────────────────────
async function sendMessage(text) {
  text = text.trim();
  if (!text || isLoading) return;

  // /clear command
  if (text === '/clear') {
    clearChat();
    elInput.value = '';
    autoResize();
    return;
  }

  // Append user bubble
  appendMessage('user', text);
  chatHistory.push({ role: 'user', content: text });
  elInput.value = '';
  autoResize();

  // Show typing
  setLoading(true);

  const t0 = Date.now();

  try {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), (CFG.timeout + 10) * 1000);

    const payload = {
      text,
      session_id: SESSION_ID,
      timeout: CFG.timeout,
    };

    // Only add layer if not AUTO
    if (selectedLayer !== 'auto') {
      payload.layer = selectedLayer;
    }

    const res = await fetch(`${CFG.api}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    clearTimeout(tid);

    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);

    if (!res.ok) {
      let errText = `HTTP ${res.status}`;
      try {
        const errData = await res.json();
        errText = errData.detail || errData.error || errData.message || errText;
      } catch { /* ignore */ }
      setLoading(false);
      appendMessage('error', `Ошибка: ${errText}`, null);
      return;
    }

    const data = await res.json();

    // Extract response fields — handle different API response shapes
    const reply   = data.response || data.text || data.answer || data.content || '(пустой ответ)';
    const layer   = data.layer   || data.mll_layer || selectedLayer || null;
    const model   = data.model   || data.model_name || null;
    const elapsedFinal = data.elapsed != null
      ? parseFloat(data.elapsed).toFixed(1)
      : elapsed;

    setLoading(false);
    appendMessage('ai', reply, { layer, model, elapsed: elapsedFinal });
    chatHistory.push({ role: 'assistant', content: reply });

    // Update status if we successfully got a response
    setStatus('online', 'online');

  } catch (err) {
    setLoading(false);
    if (err.name === 'AbortError') {
      appendMessage('error', `Таймаут ${CFG.timeout}s — сервер не ответил.`, null);
    } else {
      appendMessage('error', `Сеть: ${err.message}`, null);
    }
  }
}

function setLoading(state) {
  isLoading = state;
  elSend.disabled = state;
  elInput.disabled = state;
  elTyping.classList.toggle('hidden', !state);
  if (state) scrollToBottom();
}

// ── Input: auto-resize textarea ───────────────────────────────────────────────
function autoResize() {
  elInput.style.height = 'auto';
  elInput.style.height = Math.min(elInput.scrollHeight, 160) + 'px';
}

elInput.addEventListener('input', autoResize);

elInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) {
    e.preventDefault();
    sendMessage(elInput.value);
  }
});

elSend.addEventListener('click', () => sendMessage(elInput.value));

// ── Clear button ──────────────────────────────────────────────────────────────
$('btn-clear').addEventListener('click', clearChat);

// ── Settings ──────────────────────────────────────────────────────────────────
$('btn-settings').addEventListener('click', () => {
  $('setting-api').value       = CFG.api;
  $('setting-timeout').value   = CFG.timeout;
  $('setting-markdown').checked = CFG.markdown;
  elModalSessionId.textContent = SESSION_ID;
  elSettingsModal.classList.remove('hidden');
});

$('btn-close-settings').addEventListener('click', () => {
  elSettingsModal.classList.add('hidden');
});

elSettingsModal.querySelector('.modal-backdrop').addEventListener('click', () => {
  elSettingsModal.classList.add('hidden');
});

$('btn-save-settings').addEventListener('click', () => {
  CFG.api      = $('setting-api').value.replace(/\/$/, '');
  CFG.timeout  = parseInt($('setting-timeout').value, 10) || 90;
  CFG.markdown = $('setting-markdown').checked;
  localStorage.setItem('sipa_api',      CFG.api);
  localStorage.setItem('sipa_timeout',  CFG.timeout);
  localStorage.setItem('sipa_markdown', CFG.markdown);
  elSettingsModal.classList.add('hidden');
  checkHealth();
});

$('btn-new-session').addEventListener('click', () => {
  localStorage.removeItem('sipa_session_id');
  SESSION_ID = getOrCreateSessionId();
  elSessionLabel.textContent = SESSION_ID.slice(0, 8) + '…';
  elModalSessionId.textContent = SESSION_ID;
  elSettingsModal.classList.add('hidden');
  clearChat();
});

// ── Session label ─────────────────────────────────────────────────────────────
elSessionLabel.textContent = SESSION_ID.slice(0, 8) + '…';
elModalSessionId.textContent = SESSION_ID;

// ── URL: ?new=1 → new session ─────────────────────────────────────────────────
if (new URLSearchParams(location.search).get('new') === '1') {
  localStorage.removeItem('sipa_session_id');
  SESSION_ID = getOrCreateSessionId();
  history.replaceState({}, '', '/');
}

// ── Service Worker registration ───────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('[SW] registered', reg.scope))
      .catch(err => console.warn('[SW] registration failed', err));
  });
}

// ── Focus input on load ───────────────────────────────────────────────────────
window.addEventListener('load', () => {
  elInput.focus();
  scrollToBottom();
});
