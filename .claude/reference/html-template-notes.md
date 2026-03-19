# HTML Template Notes

Instructions for the `build-html` skill on generating `synthesis/synthesis.html`.

## Output Requirements

- Single self-contained file: all CSS and JS embedded inline
- No external CDN calls, no external fonts, no external scripts
- Must open correctly from `file://` (no server required)

## Page Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{H1 of synthesis.md}</title>  <!-- used as synthesisTopic in Phase 2 payload -->
  <style>/* all CSS inline */</style>
</head>
<body>
  <header>
    <h1>{synthesis title}</h1>
    <p class="meta">{date generated}</p>
  </header>
  <div class="layout">
    <nav class="sidebar"><!-- section links --></nav>
    <main class="content"><!-- synthesis body --></main>
  </div>
  <div id="tooltip" class="tooltip hidden"></div>
  <div id="ask-claude-btn" class="ask-btn hidden">Ask Claude</div>
  <div id="toast" class="toast hidden"></div>
  <script>/* all JS inline */</script>
</body>
</html>
```

## `<cite>` Element Requirements

Every `[BibKey]` in synthesis.md becomes a `<cite>` element. Required data attributes:

```html
<cite
  data-key="{BibTeX key}"
  data-title="{full title from references.bib}"
  data-authors="{authors from references.bib}"
  data-year="{year}"
  data-venue="{journal/conference/publisher — empty string if absent}"
  data-doi="{bare DOI string — empty string if absent}"
  data-pdf="{absolute file:// path to PDF from manifest.json}"
  data-summary="{absolute file:// path to summary .md from manifest.json}"
>
  [{BibKey}]
</cite>
```

Path resolution: paths in `data-pdf` and `data-summary` come from `manifest.json` and are already absolute. The `file://` prefix must be prepended if not already present.

If a BibKey has no entry in `references.bib`: render `<cite data-key="{key}">[{key}]</cite>` with no other attributes. List missing keys in a warning comment at the bottom of the HTML.

If a BibKey has a `references.bib` entry but no `manifest.json` entry: populate metadata attributes from `references.bib`; leave `data-pdf` and `data-summary` as empty strings.

## Citation Tooltip

Shown on `mouseenter` on any `<cite>` element. Structure:

```html
<div class="tooltip">
  <strong>{data-title}</strong>
  <p>{data-authors} ({data-year})</p>
  <p>{data-venue}</p>
  <div class="tooltip-links">
    <!-- "Open source": if data-doi non-empty, href = "https://doi.org/{data-doi}"
         else if data-pdf non-empty, href = data-pdf
         else omit link -->
    <a href="{source-url}" target="_blank">Open source</a>
    <!-- "View summary": only if data-summary non-empty -->
    <a href="{data-summary}" target="_blank">View summary</a>
  </div>
</div>
```

Tooltip must close on `mouseleave` and be positioned near the citation element.

## Text Highlight → Ask Claude Button

1. Listen for `selectionchange` or `mouseup` events
2. When text is selected (non-empty `window.getSelection()`):
   - Show the `#ask-claude-btn` button positioned near the selection
3. When button is clicked:
   - Collect citations: any `<cite>` element whose text range overlaps the selection range, PLUS any `<cite>` elements that are siblings within the same block-level parent (paragraph or list item) as the selection
   - Call `handleAskClaude(payload)` with the assembled payload

## Clipboard Prompt Format

Built by `buildPrompt(payload)`:

```
## Context
You are helping me understand a synthesis about {synthesisTopic}.

## Selected text
"{selectedText}"

## Relevant citations in this passage
{for each citation:}
- BibKey: {key}
  Title: {title}
  Authors: {authors}
  Summary: {summary path}
  PDF: {pdf path}

## Synthesis memory
{memoryDoc contents, or omit this section if memoryDoc is null}

## My question
[Fill in your question here]
```

## Phase 2 Hook

The `handleAskClaude` function must be isolated in a clearly-commented block:

```javascript
/* =========================================================
   PHASE2_SERVER_HOOK
   Phase 1: copies assembled prompt to clipboard.
   Phase 2: replace this function to POST to localhost:8000
   and render streaming response in the side panel.

   Payload contract:
   {
     selectedText:  string,
     citations:     Array<{ key, title, authors, year, venue, doi, pdf, summary }>,
     synthesisTopic: string,          // document.title (= synthesis.md H1)
     memoryDoc:      string | null,   // synthesis-memory.md contents or null
     pdfPaths:       string[],        // convenience alias from citations[*].pdf
     summaryPaths:   string[]         // convenience alias from citations[*].summary
   }
   ========================================================= */
function handleAskClaude(payload) {
  const prompt = buildPrompt(payload);
  navigator.clipboard.writeText(prompt);
  showToast('Prompt copied — paste into Claude Code.');
}
```

## Design Notes

- Clean, readable typography (system font stack is fine)
- Sidebar has section links generated from synthesis.md headings
- Mobile-friendly is a nice-to-have, not required
- No dark mode required
