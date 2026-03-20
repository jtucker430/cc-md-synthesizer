# server/

FastAPI server that enables in-page Claude responses from `synthesis/synthesis.html`.

## Quick start

**Prerequisite:** Claude Code must be installed and authenticated (`claude auth status` should show logged in). The server uses your CC session — no separate API key required.

```bash
uv run uvicorn server.main:app --reload
```

The server starts at `http://localhost:8000`.

## Endpoints

### `GET /health`

Returns server status.

```bash
curl http://localhost:8000/health
# {"status":"ok","backend":"claude-code-cli"}
```

### `POST /ask`

Accepts a JSON payload from the HTML page and returns a streaming SSE response.

**Request body:**
```json
{
  "selectedText": "text the user highlighted",
  "citations": [{"key": "AuthorYear", "title": "...", ...}],
  "synthesisTopic": "page title",
  "memoryDoc": "contents of synthesis-memory.md or null",
  "pdfPaths": ["file:///path/to/doc.pdf"],
  "summaryPaths": ["file:///path/to/summary.md"]
}
```

**Response:** `text/event-stream` — each event is `data: {"text": "..."}`, terminated by `data: [DONE]`. Errors are delivered as `data: {"error": "..."}` followed by `data: [DONE]`.

**Manual test:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"selectedText":"test","citations":[],"synthesisTopic":"testing","memoryDoc":null,"pdfPaths":[],"summaryPaths":[]}' \
  --no-buffer
```

## Troubleshooting

**Panel shows "Could not reach the local server"**
The server is not running. Start it with `uv run uvicorn server.main:app --reload`.

**Panel shows "claude CLI not found"**
Claude Code is not installed or not on PATH. Install it and ensure `claude auth status` shows logged in.

**Port 8000 already in use**
Run on a different port: `uv run uvicorn server.main:app --reload --port 8001`
Then update the fetch URL in `scripts/templates/script.js` to match.
