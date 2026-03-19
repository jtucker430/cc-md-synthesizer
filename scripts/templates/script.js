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
    if (range.compareBoundaryPoints(Range.END_TO_START, cr) < 0 &&
        range.compareBoundaryPoints(Range.START_TO_END, cr) > 0) {
      addCite(cite);
    }
  });

  let node = range.commonAncestorContainer;
  while (node && !['P','LI','BLOCKQUOTE','DIV','SECTION','ARTICLE','MAIN']
                    .includes(node.nodeName)) {
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
  const pdfPaths     = citations.map(c => c.pdf).filter(Boolean);
  const summaryPaths = citations.map(c => c.summary).filter(Boolean);

  handleAskClaude({
    selectedText,
    citations,
    synthesisTopic: SYNTHESIS_TOPIC,
    memoryDoc: SYNTHESIS_MEMORY,
    pdfPaths,
    summaryPaths,
  });
  askBtn.classList.add('hidden');
});

/* ── Prompt builder ───────────────────────────────────────────────────────── */
function buildPrompt(payload) {
  const citLines = payload.citations.map(c => [
    `- BibKey: ${c.key}`,
    `  Title: ${c.title || ''}`,
    `  Authors: ${c.authors || ''}`,
    `  Summary: ${c.summary || ''}`,
    `  PDF: ${c.pdf || ''}`,
  ].join('\n')).join('\n');

  const memSection = payload.memoryDoc
    ? `\n## Synthesis memory\n${payload.memoryDoc}\n`
    : '';

  return [
    `## Context`,
    `You are helping me understand a synthesis about ${payload.synthesisTopic}.`,
    ``,
    `## Selected text`,
    `"${payload.selectedText}"`,
    ``,
    `## Relevant citations in this passage`,
    citLines || '(none)',
    memSection,
    `## My question`,
    `[Fill in your question here]`,
  ].join('\n');
}

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

/* =========================================================
   PHASE2_SERVER_HOOK
   Phase 1: copies assembled prompt to clipboard.
   Phase 2: replace this function to POST to localhost:8000
   and render streaming response in the side panel.

   Payload contract:
   {
     selectedText:   string,
     citations:      Array<{ key, title, authors, year, venue, doi, pdf, summary }>,
     synthesisTopic: string,
     memoryDoc:      string | null,
     pdfPaths:       string[],
     summaryPaths:   string[]
   }
   ========================================================= */
function handleAskClaude(payload) {
  const prompt = buildPrompt(payload);
  navigator.clipboard.writeText(prompt);
  showToast('Prompt copied — paste into Claude Code.');
}
