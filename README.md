# cc-synthesizer

A Claude Code skill pipeline that turns a folder of PDFs into an interactive synthesis.
Drop in documents about any topic, run one command, and get a citable, cross-cutting synthesis
with an interactive HTML page that lets you query Claude about specific passages.

## Quick Start

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [`pdftotext`](https://poppler.freedesktop.org/) (`brew install poppler`), [`fbib`](https://github.com/mr-devs/fetchbib) (`uv tool install fetchbib`)

```bash
# 1. Clone the repo
git clone https://github.com/your-username/cc-synthesizer
cd cc-synthesizer

# 2. Drop PDFs into documents/
cp ~/papers/*.pdf documents/

# 3. Open Claude Code and run:
# /create-synthesis
# /build-html

# 4. Open synthesis/synthesis.html in your browser
```

See [`docs/getting-started.md`](docs/getting-started.md) for full instructions.

## Contents

- [`.claude/`](.claude/) — Claude Code skills and reference files
- [`documents/`](documents/) — Drop your PDFs here
- [`summaries/`](summaries/) — Auto-generated per-document summaries
- [`synthesis/`](synthesis/) — Auto-generated synthesis and HTML
- [`server/`](server/) — Phase 2: local server for in-page Claude interaction
- [`docs/`](docs/) — Documentation
