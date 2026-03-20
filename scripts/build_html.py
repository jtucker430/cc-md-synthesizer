#!/usr/bin/env python3
"""
build_html.py — Convert synthesis/synthesis.md to a self-contained interactive HTML page.

Usage:
    python scripts/build_html.py [--title "Optional Title"] [--root /path/to/repo]

Phase 2 note:
    The PHASE2_SERVER_HOOK block in the embedded JS isolates handleAskClaude.
    Phase 2 replaces only that function to POST to localhost:8000 and render
    streaming responses in a side panel. All other structure is unchanged.
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from markdown_it import MarkdownIt

# Use html.escape() for safe HTML escaping
escape = html.escape


def _slugify(text: str) -> str:
    """Convert heading text to a URL-safe id slug."""
    slug = re.sub(r"[^a-z0-9-]", "", text.lower().replace(" ", "-"))
    return slug if slug else "section"


def _unique_slug(text: str, used_slugs: dict[str, int]) -> str:
    """Return a deduplicated slug, appending -N on collision."""
    raw = _slugify(text)
    if raw not in used_slugs:
        used_slugs[raw] = 1
        return raw
    used_slugs[raw] += 1
    return f"{raw}-{used_slugs[raw]}"


def _citation_rule(state, silent: bool) -> bool:
    """markdown-it-py inline rule: convert [@CitKey] to <cite> placeholders."""
    pos = state.pos
    src = state.src

    # Must start with [@
    if src[pos : pos + 2] != "[@":
        return False

    # Find closing ]
    end = src.find("]", pos + 2)
    if end == -1:
        return False

    inner = src[pos + 2 : end]  # everything between [@ and ]
    keys = [k.strip().lstrip("@") for k in inner.split(",")]

    # Validate: every key must be non-empty and start with a letter
    if not all(k and k[0].isalpha() for k in keys):
        return False

    if silent:
        return True

    # Emit HTML
    if len(keys) == 1:
        k = escape(keys[0])
        html_out = f'<cite data-key="{k}">[{k}]</cite>'
    else:
        parts = ", ".join(
            f'<cite data-key="{escape(k)}">{escape(k)}</cite>' for k in keys
        )
        html_out = f"[{parts}]"

    token = state.push("html_inline", "", 0)
    token.content = html_out

    state.pos = end + 1
    return True


def _file_url(path: str) -> str:
    """Ensure path has a file:// prefix. Returns empty string if path is empty."""
    if not path:
        return ""
    if path.startswith("file://"):
        return path
    return "file://" + path


def enrich_citations(html: str, citations: dict) -> tuple:
    """Replace <cite data-key="K">[K]</cite> placeholders with full data-* attribute sets.

    Args:
        html:      HTML body from render_markdown (contains bare cite placeholders)
        citations: {key: {title, authors, year, venue, doi, pdf, summary, ...}} from citations.json

    Returns:
        (enriched_html, missing_keys)
        - enriched_html: HTML with fully-attributed <cite> elements
        - missing_keys:  list of keys found in html but absent from citations
    """
    missing: list[str] = []

    def replace_cite(m: re.Match) -> str:
        key = m.group(1)
        if key not in citations:
            if key not in missing:
                missing.append(key)
            return m.group(0)  # leave as-is
        meta = citations[key]
        pdf_url = escape(_file_url(meta.get("pdf", "")))
        summ_url = escape(_file_url(meta.get("summary", "")))
        attrs = " ".join(
            [
                f'data-key="{escape(key)}"',
                f'data-title="{escape(meta.get("title", ""))}"',
                f'data-authors="{escape(meta.get("authors", ""))}"',
                f'data-year="{escape(meta.get("year", ""))}"',
                f'data-venue="{escape(meta.get("venue", ""))}"',
                f'data-doi="{escape(meta.get("doi", ""))}"',
                f'data-pdf="{pdf_url}"',
                f'data-summary="{summ_url}"',
            ]
        )
        return f"<cite {attrs}>[{escape(key)}]</cite>"

    pattern = r'<cite data-key="([^"]+)">\[?[^\]<]+\]?</cite>'
    enriched = re.sub(pattern, replace_cite, html)
    return enriched, missing


def render_markdown(text: str) -> tuple[str, str, list[tuple[int, str, str]], str]:
    """Convert synthesis.md markdown subset to HTML using markdown-it-py.

    Returns:
        (html_body, title, nav_headings, doc_count)
        - html_body:    rendered HTML string (H1 suppressed)
        - title:        text of the first H1 (empty string if none)
        - nav_headings: list of (level, display_text, slug) for h2/h3/h4, in order
        - doc_count:    number of documents from metadata line (empty string if none)
    """
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    md.inline.ruler.before("link", "citation", _citation_rule)

    tokens = md.parse(text)

    # ── Extract and suppress the first H1 ───────────────────────────────────
    title = ""
    i = 0
    while i < len(tokens):
        if tokens[i].type == "heading_open" and tokens[i].tag == "h1":
            inline_tok = tokens[i + 1]  # always present after heading_open
            title = inline_tok.content
            # Remove the triplet: heading_open, inline, heading_close
            tokens.pop(i)  # heading_open
            tokens.pop(i)  # inline (shifted down)
            tokens.pop(i)  # heading_close (shifted down)
            break
        i += 1

    # ── Collect nav headings (h2, h3, h4) ───────────────────────────────────
    used_slugs: dict[str, int] = {}
    nav_headings: list[tuple[int, str, str]] = []
    for j, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag in ("h2", "h3", "h4"):
            level = int(tok.tag[1])
            inline_content = tokens[j + 1].content  # raw markdown source
            slug = _unique_slug(inline_content, used_slugs)
            nav_headings.append((level, inline_content, slug))
            # Inject id attribute on the heading_open token
            tok.attrSet("id", slug)

    # ── Render ───────────────────────────────────────────────────────────────
    body_html = md.renderer.render(tokens, md.options, {})

    # ── Extract and suppress doc-count metadata line ─────────────────────────
    doc_count = ""
    m = re.search(r"<p><em>Synthesis of (\d+) documents\.", body_html)
    if m:
        doc_count = m.group(1)
        body_html = re.sub(
            r"<p><em>Synthesis of \d+ documents\..*?</em></p>", "", body_html
        )

    return body_html, title, nav_headings, doc_count


def build_html_page(
    title: str,
    body_html: str,
    nav_headings: list[tuple[int, str, str]],
    memory_doc: Optional[str],
    generated_date: str,
    missing_keys: list[str],
    doc_count: str = "",
) -> str:
    """Generate the synthesis HTML page.

    Links to scripts/templates/style.css and scripts/templates/script.js
    via relative paths from synthesis/synthesis.html.
    Injects SYNTHESIS_MEMORY and SYNTHESIS_TOPIC as an inline script block.
    """
    sidebar_links = "\n".join(
        f'      <li class="nav-h{level}"><a href="#{slug}">{escape(text)}</a></li>'
        for level, text, slug in nav_headings
    )

    memory_js = json.dumps(memory_doc)  # "null" if None, else a JSON string
    meta_prefix = f"Synthesis of {doc_count} documents &middot; " if doc_count else ""

    warning_comment = ""
    if missing_keys:
        keys_str = ", ".join(f"[@{k}]" for k in missing_keys)
        warning_comment = (
            f"\n<!-- WARNING: The following citation keys were not found in citations.json:\n"
            f"     {keys_str}\n"
            f"     These <cite> elements have no metadata. "
            f"Re-run /summarize-documents if needed. -->"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="../scripts/templates/style.css">
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="meta">{meta_prefix}Generated {generated_date}</p>
  </header>
  <div class="layout">
    <nav class="sidebar">
      <ul>
{sidebar_links}
      </ul>
    </nav>
    <main class="content">
{body_html}
    </main>
  </div>
  <div id="tooltip" class="tooltip hidden"></div>
  <div id="ask-claude-btn" class="ask-btn hidden">Ask Claude</div>
  <div id="toast" class="toast hidden"></div>
  <div id="response-panel">
    <div class="response-panel-header">
      <h2>Ask Claude</h2>
      <button class="response-panel-close" id="response-panel-close" aria-label="Close">&times;</button>
    </div>
    <div id="chat-thread"></div>
    <div class="chat-input-area">
      <textarea id="chat-input" placeholder="Ask a question… (Shift+Enter for newline)"></textarea>
      <button id="chat-send-btn">Send</button>
    </div>
  </div>
  <script>
    const SYNTHESIS_MEMORY = {memory_js};
    const SYNTHESIS_TOPIC  = {json.dumps(title)};
  </script>
  <script src="../scripts/templates/script.js"></script>
</body>
</html>{warning_comment}"""


def main():
    parser = argparse.ArgumentParser(
        description="Build interactive HTML synthesis page from synthesis/synthesis.md"
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Override page title (default: H1 of synthesis.md)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repo root directory (default: current working directory)",
    )
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path.cwd()
    synthesis_md = root / "synthesis" / "synthesis.md"
    citations_json = root / "citations.json"
    memory_md = root / "synthesis" / "synthesis-memory.md"
    output_html = root / "synthesis" / "synthesis.html"

    # Prerequisite checks
    if not synthesis_md.exists():
        print(
            "ERROR: synthesis/synthesis.md not found. Run /create-synthesis first.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not citations_json.exists():
        print(
            "ERROR: citations.json not found. Run /summarize-documents first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read inputs
    md_text = synthesis_md.read_text(encoding="utf-8")
    citations = json.loads(citations_json.read_text(encoding="utf-8"))
    memory_doc = memory_md.read_text(encoding="utf-8") if memory_md.exists() else None

    # Parse and render
    body_html, detected_title, nav_headings, doc_count = render_markdown(md_text)
    title = args.title or detected_title or "Synthesis"
    body_html, missing_keys = enrich_citations(body_html, citations)

    # Count citations in source (for report)
    total_refs = len(re.findall(r"@[A-Za-z][A-Za-z0-9]+", md_text))
    resolved = total_refs - len(missing_keys)

    # Assemble and write
    page = build_html_page(
        title=title,
        body_html=body_html,
        nav_headings=nav_headings,
        memory_doc=memory_doc,
        generated_date=date.today().isoformat(),
        missing_keys=missing_keys,
        doc_count=doc_count,
    )
    output_html.write_text(page, encoding="utf-8")

    # Report
    print(
        f"Build HTML — Results\n"
        f"=====================\n"
        f"Input:      synthesis/synthesis.md\n"
        f"Output:     synthesis/synthesis.html\n"
        f"Citations:  {resolved} / {total_refs} "
        f"({len(missing_keys)} missing from citations.json)\n\n"
        f"Open synthesis/synthesis.html in your browser to view the interactive synthesis."
    )
    if missing_keys:
        print("\nMissing citation keys:")
        for k in missing_keys:
            print(f"  [@{k}]")


if __name__ == "__main__":
    main()
