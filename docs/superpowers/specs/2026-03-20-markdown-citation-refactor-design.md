# Design: Markdown Library + Citation Store Consolidation

**Date:** 2026-03-20
**Status:** Approved

## Summary

Replace the hand-rolled markdown parser in `build_html.py` with `markdown-it-py`, change citation syntax from `[BibKey]` to `[@CitKey]`, and consolidate `references.bib` + `summaries/manifest.json` into a single `citations.json` at the repo root. The key naming convention (`AuthorYearKeyword`) is unchanged. No user-visible behavior changes.

---

## Motivation

The existing custom markdown parser in `build_html.py` only handles `#`, `##`, and `###` headings. Claude-generated synthesis files sometimes use `####` for sub-sections, causing an infinite loop (the `else` paragraph block exits immediately on any `#`-prefixed line without advancing the index). Beyond this bug, the hand-rolled parser is a maintenance liability for future contributors.

Additionally, the pipeline maintains two separate citation data stores (`references.bib` and `manifest.json`) that must be kept in sync and are merged at build time via a regex BibTeX parser — the most complex, brittle function in `build_html.py`.

---

## Architecture

### Current pipeline

```
PDFs
 └─ /summarize-documents
     ├─ writes: summaries/{BibKey}.md        (summary text)
     ├─ writes: references.bib               (BibTeX citation metadata)
     └─ writes: summaries/manifest.json      (BibKey → pdf + summary paths)
 └─ /create-synthesis
     ├─ reads:  summaries/*.md + references.bib
     └─ writes: synthesis/synthesis.md       ([BibKey] citation syntax)
 └─ build_html.py
     ├─ reads:  synthesis.md, references.bib, manifest.json
     ├─ parse_bib() + enrich_citations() merge the two stores
     └─ writes: synthesis/synthesis.html
```

### New pipeline

```
PDFs
 └─ /summarize-documents
     ├─ writes: summaries/{CitKey}.md        (unchanged)
     └─ writes: citations.json               (replaces references.bib + manifest.json)
 └─ /create-synthesis
     ├─ reads:  summaries/*.md + citations.json
     └─ writes: synthesis/synthesis.md       ([@CitKey] citation syntax)
 └─ build_html.py
     ├─ reads:  synthesis.md + citations.json
     ├─ markdown-it-py renders markdown; [@CitKey] plugin emits <cite> tokens
     └─ writes: synthesis/synthesis.html
```

---

## Component Designs

### 1. `citations.json` schema

**Location:** `{repo_root}/citations.json` (i.e., `root / "citations.json"` in `build_html.py` path resolution).

Replaces both `references.bib` and `summaries/manifest.json`. Written by `/summarize-documents`, read by `/create-synthesis` and `build_html.py`.

```json
{
  "Smith2023Finding": {
    "title": "A Study of Things",
    "authors": "Smith, John and Doe, Alice",
    "year": "2023",
    "venue": "Journal of Examples",
    "doi": "10.1234/example",
    "url": "https://doi.org/10.1234/example",
    "type": "article",
    "pdf": "/absolute/path/to/documents/smith.pdf",
    "summary": "/absolute/path/to/summaries/Smith2023Finding.md"
  }
}
```

Fields:
- `title`, `authors`, `year`, `venue`, `doi`, `url`, `type` — from BibTeX lookup (`fbib` remains the metadata source internally; relevant fields extracted and written as JSON)
- `pdf`, `summary` — absolute filesystem paths (previously in `manifest.json`)
- `venue` — first of: journal > booktitle > howpublished (same priority as current)
- `url`, `doi`, `type` — optional; use `""` if unavailable; `pdf` and `summary` default to `""` if not yet known

**Upsert semantics:** When `/summarize-documents` processes a PDF (i.e., it is not skipped), its entry in `citations.json` is written or overwritten. When a PDF is skipped because its summary already exists, its `citations.json` entry is left unchanged. This is a true upsert: on re-run, the entry for a reprocessed PDF is replaced in full.

Citation key naming convention is unchanged: `AuthorYearKeyword`.

### 2. Citation syntax change: `[BibKey]` → `[@CitKey]`

The `@` prefix makes citations unambiguous to any markdown parser (`[text]` is a potential link reference; `[@text]` is not standard markdown syntax). Aligns with the pandoc citation convention used in academic tooling.

Examples:
- Single: `[@Smith2023Finding]`
- Multiple: `[@Jones2022Debate, @Lee2024Review]`
- In bold (Reading Guide): `**[@Smith2023Finding]**`

### 3. `build_html.py` — markdown rendering

**Library:** `markdown-it-py` (CommonMark-compliant, pure Python, pip-installable, used by Jupyter).

**`render_markdown` is reimplemented, not renamed.** It retains the same function signature and return type:
```python
def render_markdown(text: str) -> tuple[str, str, list[tuple[int, str, str]], str]:
```
returning `(html_body, title, nav_headings, doc_count)` with identical semantics. This keeps all existing `test_render_*` tests valid with only input/assertion updates where needed.

**Custom inline plugin:** A small `markdown-it-py` inline rule (~20 lines) registered on the `MarkdownIt` instance with **high priority** (before link parsing) so that `[@Key]` is consumed before markdown-it-py attempts to interpret `[...]` as a link reference. The rule's `match` step checks whether the current position in the source starts with `[@`; if so, the `parse` step scans forward greedily to the next `]`, extracts the content between `[@` and `]`, splits on `,` to get individual `@Key` tokens, strips the leading `@` from each key, and emits HTML. Embedding `[@Key]` inside a link label (e.g., `[text [@Key]](url)`) is out of scope and not a supported usage. The `@` prefix is stripped from display text to preserve identical HTML output to the current system:

- Single `[@Smith2023Finding]` → `<cite data-key="Smith2023Finding">[Smith2023Finding]</cite>`
- Multi `[@Jones2022Debate, @Lee2024Review]` → `[<cite data-key="Jones2022Debate">Jones2022Debate</cite>, <cite data-key="Lee2024Review">Lee2024Review</cite>]`

The multi-citation format (outer brackets, comma-separated individual `<cite>` elements without inner brackets) matches the current output exactly. For multi-key citations, the plugin emits a literal `[` before the first `<cite>` and a literal `]` after the last `</cite>`; for single-key citations, no outer brackets are emitted. The `enrich_citations` regex pattern (`r'<cite data-key="([^"]+)">\[?[^\]<]+\]?</cite>'`) is **unchanged** and remains valid.

**What `markdown-it-py` handles natively:** all heading levels (`#` through `######`), bullet and ordered lists, tables (via the built-in table rule enabled with `"table"` option), bold, italic, HTML escaping. Table output is semantically equivalent to the current custom parser: `<table><thead><tr>...</tr></thead><tbody>...</tbody></table>` with `<th>` and `<td>` elements. Exact whitespace and attribute ordering need not be preserved; semantic equivalence is sufficient.

**Title extraction:** Walk the token stream after parsing to find the first `heading_open` token with `tag == "h1"`. Extract its inline content as `title` by reading the adjacent `inline` token's `content`. Remove the `heading_open`, `inline`, and `heading_close` triplet from the token list **before rendering** so the H1 never appears in the body HTML. This token-removal approach (rather than post-render string stripping) is required to avoid mishandling H1 headings that contain citations or other inline markup.

**Nav headings:** Walk the token stream to collect all `h2`, `h3`, and `h4` `heading_open` tokens. For each, read the adjacent `inline` token's `.content` attribute to get the raw markdown source text (e.g., `"Section One"` or `"**Bold** Section"`). Use that text and the heading level to build `nav_headings` entries. This matches the existing behavior: the current parser also stores raw content in `nav_headings` (before `_apply_inline` is called). Markdown syntax characters in heading display text (e.g., `**`) are passed through `html.escape()` in the sidebar template — this is an existing limitation, not a regression.

**Slug generation:** Retain the existing `_slugify` / `_unique_slug` helpers — they are correct and simple. Apply them to the adjacent `inline` token's `.content` (the raw markdown source string, not rendered HTML). The `_slugify` regex `[^a-z0-9-]` strips `*` and other non-alphanumeric characters, so `**Bold** Section` → `bold-section` correctly.

**Doc count extraction:** The metadata line format is `*Synthesis of N documents. Generated YYYY-MM-DD.*` (period after "documents" is required). `markdown-it-py` renders this as `<p><em>Synthesis of N documents. Generated YYYY-MM-DD.</em></p>`. After rendering the full body HTML, apply this regex to detect and suppress the doc-count paragraph:

```python
m = re.search(r"<p><em>Synthesis of (\d+) documents\.", body_html)
if m:
    doc_count = m.group(1)
    body_html = re.sub(r"<p><em>Synthesis of \d+ documents\..*?</em></p>", "", body_html)
```

The period is included in the regex to match the defined format exactly. The comma variant (`*Synthesis of N documents, Generated…*`) accepted by the old parser is intentionally dropped — users must regenerate synthesis files with `/create-synthesis` after this refactor (see Migration Notes).

**`enrich_citations` updated signature:** Changes from `enrich_citations(html, bib, manifest)` to `enrich_citations(html, citations)`, where `citations` is the flat dict loaded from `citations.json`. Internally, the `bib` parameter is renamed to `citations`; all references to `manifest` are removed. The `key not in bib` check becomes `key not in citations`. Inside the function, path fields are accessed safely:

```python
pdf_path  = meta.get("pdf", "")
summ_path = meta.get("summary", "")
```

The `url` and `type` fields from `citations.json` are **not** added as `data-*` attributes on `<cite>` — the attribute set remains unchanged: `data-key`, `data-title`, `data-authors`, `data-year`, `data-venue`, `data-doi`, `data-pdf`, `data-summary`. This avoids any JS/CSS changes. All field accesses inside `enrich_citations` use `.get("field", "")` for safety — including `title`, `authors`, `year`, `venue`, and `doi` — to handle partial or older `citations.json` entries without raising `KeyError`. A key that is present in `citations` but has missing fields produces an enriched `<cite>` element with empty attributes (e.g., `data-title=""`); it is **not** added to `missing_keys`. Only keys that are entirely absent from `citations` are reported as missing.

**Warning comment updated:** The HTML comment in `build_html_page` that says `"not found in references.bib"` is updated to `"not found in citations.json"`. The per-key formatting inside that comment changes from `[{k}]` to `[@{k}]` to match the new citation syntax.

**Citation count regex updated:** The regex in `main()` used to count citation references changes from `r"\[[A-Za-z][A-Za-z0-9]+\]"` to `r"@[A-Za-z][A-Za-z0-9]+"`. This counts individual citation keys (one per `@Key` token), correctly handling both single `[@Key]` and multi-citation `[@Key1, @Key2]` forms. The `resolved = total_refs - len(missing_keys)` calculation retains the existing behavior where `missing_keys` is deduplicated (a key missing N times is counted once) while `total_refs` counts each occurrence — this pre-existing mismatch is inherited unchanged and is intentional (it approximates coverage). The console report string `"missing from references.bib"` is updated to `"missing from citations.json"`. The per-key display in the missing keys loop changes from `f"  [{k}]"` to `f"  [@{k}]"` to match the new citation syntax.

**`citations.json` path in `main()`:**
```python
citations_json = root / "citations.json"
```
The prerequisite check (currently on `references_bib`) is replaced with a fatal check on `citations_json`. The `manifest_json` path variable and its optional-warning check are removed entirely.

**Functions removed:** `_apply_inline` (subsumed by the library), `parse_bib` (replaced by `json.load`).

**Functions retained (with changes noted above):** `render_markdown` (reimplemented), `enrich_citations` (new signature), `build_html_page`, `_slugify`, `_unique_slug`, `_file_url`.

**New dependency:** `markdown-it-py>=3.0` added to `pyproject.toml`.

### 4. Reference files updated

| File | Change |
|---|---|
| `.claude/reference/bibtex-format.md` | Replaced by `.claude/reference/citations-format.md` — describes the `citations.json` JSON schema and the `AuthorYearKeyword` key naming convention |
| `.claude/reference/summary-format.md` | `- **BibTeX Key:**` → `- **Citation Key:**` in the metadata block template |
| `.claude/reference/synthesis-format.md` | Replace **all** occurrences of `[BibKey]` / `[Author2024Keyword]` / `**[BibKey]**` / `[Jones2022Debate, Lee2024Review]` in prose and examples → `[@BibKey]` / `[@Author2024Keyword]` / `**[@BibKey]**` / `[@Jones2022Debate, @Lee2024Review]`. The line "Keys must match entries in `references.bib`" → "Keys must match entries in `citations.json`". The Citation Index table header `\| BibTeX Key \|` → `\| Citation Key \|`. The Citation Index table body cells use bare keys (no brackets, no `@`) — those remain unchanged. |

### 5. Skills updated

**`summarize-documents/SKILL.md`:**
- Replace all three occurrences of `@.claude/reference/bibtex-format.md` (the `## Reference` block at the top, the inline reference in step 4a, and the inline reference in the edge cases section) with `@.claude/reference/citations-format.md`
- Step 3 (Load Existing State): read `citations.json` instead of `references.bib` and `manifest.json`; extract existing citation keys for duplicate-PDF checking
- Step 4a (Fetch Citation Entry): use `fbib` as before to get BibTeX metadata; extract the needed fields (`title`, `authors`, `year`, `venue`, `doi`, `url`, `type`) and include them in the agent result block as a JSON object rather than raw BibTeX. Remove sub-step 5 of step 4a ("Append new entry to `references.bib` (create file if absent); verify no duplicate key") entirely — there is no longer a `references.bib` write
- The `---BEGIN_AGENT_RESULT---` block schema is updated: `BIBTEX_ENTRY:` and `MANIFEST_ENTRY:` fields are replaced by a single `CITATION_ENTRY:` field. The full updated schema:
  ```
  ---BEGIN_AGENT_RESULT---
  STATUS: success | error
  PDF: {pdf_path}
  BIBKEY: {final_cit_key}
  CITATION_METHOD: doi|title|manual
  SUMMARY_PATH: {absolute_path}
  CITATION_ENTRY:
  ```json
  { "Smith2023Finding": { "title": "...", "authors": "...", "year": "...", "venue": "...", "doi": "...", "url": "...", "type": "...", "pdf": "/abs/path/documents/subdir/Smith_-_2023_-_Title.pdf", "summary": "/abs/path/summaries/subdir/Smith2023Finding.md" } }
  ```
  WARNINGS: {any warnings, or "none"}
  ---END_AGENT_RESULT---
  ```
  Note: `summary` paths include subdirectory segments when the source PDF was in a subdirectory of `documents/`. Step 5 (parallel consolidation) parses each `CITATION_ENTRY:` block as JSON and merges all entries into `citations.json`.
- Step 4e (sequential mode): upsert entry into `citations.json` instead of separate `manifest.json` write; no `references.bib` write. Writes are atomic: write full JSON to a temp file in the same directory, then rename to `citations.json`
- Step 5 (Consolidate, parallel mode): read the current `citations.json` from disk first. Two distinct collision cases: (a) **same-batch collision** — two agents returned the same `CitKey` for different PDFs → apply rename-with-letter-suffix to the second key; (b) **reprocess collision** — a batch key matches a pre-existing on-disk key for the same PDF → overwrite (true upsert, per Section 1 upsert semantics). A batch key that collides with a pre-existing on-disk key for a *different* PDF is treated as case (a) and renamed. Write the final merged result atomically (temp file + rename)
- Remove all remaining references to `references.bib` and `manifest.json`

**`create-synthesis/SKILL.md`:**
- Replace `@.claude/reference/bibtex-format.md` in the `## Reference` block at the top with `@.claude/reference/citations-format.md`
- Step 2 (Check Pipeline State): prerequisite check verifies `citations.json` exists instead of `references.bib`
- Step 3 (Load All Summaries): "Read `references.bib`" → "Read `citations.json`" (single `json.load()`)
- Step 4 (Generate Synthesis): all citations in the generated `synthesis.md` use `[@CitKey]` syntax; the instruction "Keys must match entries in `references.bib`" → "Keys must match entries in `citations.json`"
- Step 6 (Report Results): update any reference to `references.bib` in the report template

### 6. Tests

`tests/test_build_html.py` is updated:

- `BIB_SAMPLE` constant removed; replaced with a `CITATIONS_SAMPLE` dict matching the `citations.json` schema (all metadata fields plus `pdf`, `summary`, and `type`)
- `test_parse_bib_*` tests (3 tests) removed — `parse_bib` is deleted
- `test_render_headings`: update input to include a `####` heading (e.g., `"# My Title\n\n## Section One\n\n### Sub-section\n\n#### Deep\n"`); add assertions that `'id="deep"'` appears in the HTML and that `nav_headings` contains `(4, "Deep", "deep")` in addition to the existing `(2, ...)` and `(3, ...)` entries (regression test for the original infinite-loop bug)
- `test_render_citation_placeholder`: the input markdown line changes to `"Found X [@Smith2023Finding] and Y [@Lee2024Review].\n"` (only the input changes); all assertion lines — including `'<cite data-key="Smith2023Finding">[Smith2023Finding]</cite>'` — are **unchanged** (the plugin strips `@` from display text)
- `test_render_doc_count_extraction`: input markdown unchanged; `doc_count == "42"` assertion unchanged; the existing assertion `assert "Synthesis of 42" not in html` is **retained** (it remains correct and is more robust than checking for a specific HTML form)
- `test_enrich_citations_*` tests (all four: `test_enrich_citations_full`, `test_enrich_citations_missing_from_bib`, `test_enrich_citations_in_bib_not_in_manifest`, `test_enrich_citations_already_file_url`): function call changes from `mod.enrich_citations(html, bib, manifest)` to `mod.enrich_citations(html, citations)` where `citations` is a single flat dict. For `test_enrich_citations_missing_from_bib`, the call becomes `mod.enrich_citations(html, {})` (one empty dict). For `test_enrich_citations_in_bib_not_in_manifest`, the entry has `"pdf": ""` and `"summary": ""` at the top level — e.g., `{"Known2021Y": {"title": "T", "authors": "A", "year": "2021", "venue": "V", "doi": "", "url": "", "type": "", "pdf": "", "summary": ""}}`. For `test_enrich_citations_already_file_url`, the `citations` dict for key `"K"` merges the former `bib` and `manifest` entries — e.g., `{"K": {"title": "T", "authors": "A", "year": "2020", "venue": "V", "doi": "", "url": "", "type": "", "pdf": "file:///already/prefixed.pdf", "summary": ""}}`. Assertions on `data-*` attributes are unchanged throughout.
- `test_end_to_end`: writes `tmp_path / "citations.json"` (a single file at repo root) instead of `references.bib` + `summaries/manifest.json`; the `(tmp_path / "summaries").mkdir()` line and all manifest writes are removed (no longer needed by `build_html.py`); synthesis.md fixture uses `[@Smith2023Finding]` syntax; all HTML assertions on `data-*` attributes are unchanged

---

## What Does Not Change

- Citation key naming convention (`AuthorYearKeyword`)
- Summary markdown format and directory structure
- `<cite>` element attribute set (`data-key`, `data-title`, `data-authors`, `data-year`, `data-venue`, `data-doi`, `data-pdf`, `data-summary`)
- HTML output structure (sidebar, nav, tooltips, Ask Claude panel)
- `build_html_page` function signature and behavior
- `render_markdown` function signature and return type
- `launch-synthesis` skill
- `cleanup-pdf-names` skill
- `pdf-extraction` skill
- The `fbib` tool (still used internally by `/summarize-documents` to fetch metadata)

---

## Error Handling

- `citations.json` missing at build time: fatal error with clear message (same behavior as current `references.bib` missing check)
- Key in `[@CitKey]` not found in `citations.json`: `enrich_citations` reports missing keys as warnings in the HTML comment (unchanged behavior, message updated to reference `citations.json`)
- Malformed `citations.json`: `json.load()` raises `JSONDecodeError`; script exits with traceback

---

## Migration Notes

Since `summaries/`, `synthesis/`, `references.bib`, and `manifest.json` are all gitignored, there are no existing artifacts to migrate. Users re-run `/summarize-documents` to regenerate `citations.json`. Existing synthesis files using `[BibKey]` syntax will need to be regenerated via `/create-synthesis`.
