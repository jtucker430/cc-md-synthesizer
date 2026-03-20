/* ── Citation tooltip ─────────────────────────────────────────────────────── */
const tooltip = document.getElementById('tooltip');
let hideTimer = null;

function escapeHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showTooltip(cite) {
  const d = cite.dataset;
  const sourceHref = d.doi  ? 'https://doi.org/' + encodeURIComponent(d.doi)
                    : d.pdf ? d.pdf
                    : null;
  const summaryHref = d.summary || null;

  tooltip.innerHTML = `
    <strong>${escapeHtml(d.title || d.key)}</strong>
    <p>${escapeHtml(d.authors || '')} ${d.year ? '(' + escapeHtml(d.year) + ')' : ''}</p>
    ${d.venue ? '<p>' + escapeHtml(d.venue) + '</p>' : ''}
    <div class="tooltip-links">
      ${sourceHref  ? '<a href="' + escapeHtml(sourceHref)  + '" target="_blank">Open source</a>'  : ''}
      ${summaryHref ? '<a href="' + escapeHtml(summaryHref) + '" target="_blank">View summary</a>' : ''}
    </div>`;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const rect = cite.getBoundingClientRect();
  let left = rect.left;
  let top  = rect.bottom + 6;

  tooltip.classList.remove('hidden');
  const tw = tooltip.offsetWidth;
  const th = tooltip.offsetHeight;
  if (left + tw > vw - 8) left = vw - tw - 8;
  if (top  + th > vh - 8) top  = rect.top - th - 6;
  tooltip.style.left = left + 'px';
  tooltip.style.top  = top  + 'px';
}

function scheduleHide() {
  hideTimer = setTimeout(() => tooltip.classList.add('hidden'), 200);
}
function cancelHide() {
  clearTimeout(hideTimer);
}

document.querySelectorAll('cite').forEach(cite => {
  cite.addEventListener('mouseenter', () => { cancelHide(); showTooltip(cite); });
  cite.addEventListener('mouseleave', scheduleHide);
});
tooltip.addEventListener('mouseenter', cancelHide);
tooltip.addEventListener('mouseleave', scheduleHide);

/* ── Text selection → Ask Claude ──────────────────────────────────────────── */
const askBtn = document.getElementById('ask-claude-btn');

// Leaf/paragraph-level block elements — walk stops here, not at structural containers
const BLOCK_STOP_ELEMENTS = new Set(['P','LI','BLOCKQUOTE','TD','TH','H1','H2','H3','H4','H5','H6']);

function getCitationsNearSelection(selection) {
  const range = selection.getRangeAt(0);
  const seen  = new Set();
  const cites = [];

  function addCite(cite) {
    if (!seen.has(cite)) {
      seen.add(cite);
      const d = cite.dataset;
      cites.push({
        key: d.key, title: d.title, authors: d.authors,
        year: d.year, venue: d.venue, doi: d.doi,
        pdf: d.pdf, summary: d.summary,
      });
    }
  }

  document.querySelectorAll('cite').forEach(cite => {
    const cr = document.createRange();
    cr.selectNodeContents(cite);
    if (range.compareBoundaryPoints(Range.END_TO_START, cr) > 0 &&
        range.compareBoundaryPoints(Range.START_TO_END, cr) < 0) {
      addCite(cite);
    }
  });

  let node = range.commonAncestorContainer;
  while (node && !BLOCK_STOP_ELEMENTS.has(node.nodeName)) {
    node = node.parentNode;
  }
  if (node) {
    node.querySelectorAll('cite').forEach(addCite);
  }

  return cites;
}

document.addEventListener('mouseup', () => {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) {
    askBtn.classList.add('hidden');
    return;
  }
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  askBtn.classList.remove('hidden');
  askBtn.style.left = Math.min(rect.left, window.innerWidth - 130) + 'px';
  askBtn.style.top  = (rect.top - 36) + 'px';
});

document.addEventListener('selectionchange', () => {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) {
    askBtn.classList.add('hidden');
  }
});

askBtn.addEventListener('mousedown', e => {
  e.preventDefault();
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return;

  const selectedText = selection.toString().trim();
  const citations    = getCitationsNearSelection(selection);

  handleAskClaude({ selectedText, citations });
  askBtn.classList.add('hidden');
});

/* ── Toast ────────────────────────────────────────────────────────────────── */
const toastEl = document.getElementById('toast');
let toastTimer = null;
function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.remove('hidden');
  toastEl.style.opacity = '1';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.style.opacity = '0';
    setTimeout(() => toastEl.classList.add('hidden'), 300);
  }, 2500);
}

/* ── Chat panel ───────────────────────────────────────────────────────────── */
const chatPanel     = document.getElementById('response-panel');
const chatThread    = document.getElementById('chat-thread');
const chatInput     = document.getElementById('chat-input');
const chatSendBtn   = document.getElementById('chat-send-btn');
const chatCloseBtn  = document.getElementById('response-panel-close');

// In-memory conversation state
let messages = [];
// Only tracks the dynamic selection data; static globals added at request time
let currentContext = {
  selectedText: '',
  citations: [],
};

chatCloseBtn.addEventListener('click', () => chatPanel.classList.remove('open'));

// Open panel and pre-populate input with context block from selected text
function handleAskClaude(selectionCtx) {
  messages = [];
  chatThread.innerHTML = '';

  currentContext = {
    selectedText:  selectionCtx.selectedText  || '',
    citations:     selectionCtx.citations     || [],
  };

  // Pre-populate input with a context block; user fills in their question
  chatInput.value = buildContextBlock(selectionCtx);

  chatPanel.classList.add('open');
  chatInput.focus();
  // Place cursor at end
  chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
}

function buildContextBlock(ctx) {
  const citLine = (ctx.citations || [])
    .map(c => `[${c.key}] ${c.title || '(no title)'}`)
    .join('; ');
  let block = `<context>\nSelected: "${ctx.selectedText}"`;
  if (citLine) block += `\nCitations: ${citLine}`;
  block += `\n</context>\n\nMy question: `;
  return block;
}

/* ── Message rendering ────────────────────────────────────────────────────── */
function _appendBubble(type) {
  const div = document.createElement('div');
  div.className = `chat-message chat-message-${type}`;
  chatThread.appendChild(div);
  chatThread.scrollTop = chatThread.scrollHeight;
  return div;
}

function appendUserBubble(text) {
  _appendBubble('user').textContent = text;
}

function appendAssistantBubble() {
  const div = _appendBubble('assistant');
  div.innerHTML = '<div class="chat-loading"><span></span><span></span><span></span></div>';
  return div;
}

function appendErrorBubble(msg) {
  const div = _appendBubble('error');
  div.innerHTML = escapeHtml(msg) +
    '<br><code>uv run uvicorn server.main:app --reload</code>';
}

/* ── Send message ─────────────────────────────────────────────────────────── */
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = '';
  chatInput.style.height = '';
  chatSendBtn.disabled = true;

  messages.push({ role: 'user', content: text });
  appendUserBubble(text);

  const assistantEl = appendAssistantBubble();
  await streamChatResponse(assistantEl);

  chatSendBtn.disabled = false;
  chatInput.focus();
}

chatSendBtn.addEventListener('click', sendMessage);

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
});

/* ── Sidebar active-section tracking ─────────────────────────────────────── */
(function () {
  const headings = Array.from(document.querySelectorAll('.content h2, .content h3'));
  const navLinks = {};
  headings.forEach(h => {
    if (h.id) {
      const link = document.querySelector(`.sidebar a[href="#${h.id}"]`);
      if (link) navLinks[h.id] = link;
    }
  });

  function updateActive() {
    let active = null;
    for (const h of headings) {
      if (h.getBoundingClientRect().top <= 80) active = h;
      else break;
    }
    Object.values(navLinks).forEach(l => l.classList.remove('active'));
    if (active && navLinks[active.id]) navLinks[active.id].classList.add('active');
  }

  window.addEventListener('scroll', updateActive, { passive: true });
  updateActive();
})();

/* ── SSE streaming ────────────────────────────────────────────────────────── */
async function streamChatResponse(assistantEl) {
  let response;
  try {
    response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        context: { ...currentContext, synthesisTopic: SYNTHESIS_TOPIC, memoryDoc: SYNTHESIS_MEMORY },
      }),
    });
  } catch (_) {
    assistantEl.innerHTML = '';
    appendErrorBubble('Could not reach the local server. Start it with:');
    messages.pop(); // remove the user message we just added
    return;
  }

  if (!response.ok) {
    assistantEl.innerHTML = '';
    appendErrorBubble('Server error ' + response.status + '. Check the server terminal.');
    messages.pop();
    return;
  }

  // Clear loading indicator
  assistantEl.innerHTML = '';
  let fullText = '';

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') break;
      try {
        const parsed = JSON.parse(data);
        if (parsed.error) {
          assistantEl.innerHTML = '';
          appendErrorBubble(parsed.error);
          messages.pop();
          return;
        }
        if (parsed.reload) {
          window.location.reload();
          return;
        }
        if (parsed.text) {
          fullText += parsed.text;
          assistantEl.textContent = fullText;
          chatThread.scrollTop = chatThread.scrollHeight;
        }
      } catch (_) { /* malformed chunk — ignore */ }
    }
  }

  // Add assistant reply to history
  if (fullText) {
    messages.push({ role: 'assistant', content: fullText });
  }
}
