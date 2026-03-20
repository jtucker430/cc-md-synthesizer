# Getting Started

## What this is

`cc-synthesizer` is a Claude Code skill pipeline. You drop PDF documents into `documents/`, run a few slash commands, and get:

1. A structured markdown summary of each document (`summaries/`)
2. A cross-cutting synthesis of the whole corpus (`synthesis/synthesis.md`)
3. An interactive HTML page with citation hover and "Ask Claude" integration (`synthesis/synthesis.html`)

It works with any document type — academic papers, industry reports, white papers, technical docs.

## Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Runs all skills | See Anthropic docs |
| `pdftotext` | Extract text from PDFs | `brew install poppler` |
| `fbib` | Fetch BibTeX from DOI or title | `uv tool install fetchbib` |

Verify your setup:
```bash
pdftotext -v
fbib --help
claude auth status   # must show logged in
```

No API key needed — the "Ask Claude" feature uses your Claude Code subscription.

## Workflow

### Option A: Single command

Drop PDFs into `documents/`, then in Claude Code:

```
/create-synthesis
```

Claude will confirm, then run cleanup → summarize → synthesize automatically. Afterwards:

```
/launch-synthesis
```

This builds the HTML, starts the local server, and opens the page in your browser with "Ask Claude" ready to use.

### Option B: Step by step

```
/cleanup-pdf-names documents/
/summarize-documents documents/
/create-synthesis
/launch-synthesis
```

### Providing context

Most skills accept optional context to orient their output:

```
/summarize-documents documents/ "these are industry reports, focus on policy recommendations"
/create-synthesis "I'm trying to understand the debate about X — organize themes around competing positions"
```

### Using synthesis-guidance.md

For detailed framing, edit `synthesis/synthesis-guidance.md`. `/create-synthesis` reads it automatically. See the template already in this repo for structure.

## Using the HTML page

After `/launch-synthesis` opens the page:

- **Hover a citation** → see title, authors, year, and links to the source PDF and summary
- **Select text → "Ask Claude"** → a side panel slides in with a live Claude response streamed from your local server

The local server runs in the background. `/launch-synthesis` reports its PID so you can stop it when done:

```bash
kill <PID>
# or
pkill -f "uvicorn server.main:app"
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Could not reach the local server" | Server not running | Run `/launch-synthesis` or `uv run uvicorn server.main:app --reload` |
| "claude CLI not found" | CC not installed or not on PATH | Install Claude Code; verify `claude auth status` shows logged in |
| Port 8000 already in use | Another process using the port | Run `uv run uvicorn server.main:app --reload --port 8001` and update the fetch URL in `scripts/templates/script.js` |

## Persistent context across sessions

`/create-synthesis` automatically creates `synthesis/synthesis-memory.md` as a stub. Edit it to record conclusions you've reached and framing notes. This file is automatically included in every "Ask Claude" request, so Claude has running context without re-explanation.

## Updating the synthesis

After adding new PDFs or editing summaries, re-run:

```
/summarize-documents documents/    # only processes new PDFs
/create-synthesis                  # regenerates synthesis.md
/launch-synthesis                  # rebuilds HTML and reopens the page
```
