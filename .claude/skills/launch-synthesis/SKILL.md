---
name: launch-synthesis
description: Use when the user wants to view or interact with synthesis.html after running /create-synthesis — builds the HTML, verifies Claude Code auth, starts the local server, and opens the page in the browser
disable-model-invocation: true
allowed-tools: Bash
---

# Launch Synthesis

Builds `synthesis/synthesis.html`, starts the local FastAPI server, and opens the page in the browser so the "Ask Claude" side panel works immediately.

## Instructions

Run the following steps in order. Stop and report clearly if any step fails.

### Step 1 — Build the HTML

```bash
uv run python scripts/build_html.py
```

If this fails, report the error and stop.

### Step 2 — Check Claude Code auth

```bash
claude auth status
```

If the output does not indicate the user is logged in, tell them to run `claude auth login` and stop.

### Step 3 — Open the HTML page

```bash
open "$(pwd)/synthesis/synthesis.html"
```

On Linux, use `xdg-open` instead of `open`.

### Step 4 — Report to the user

Tell the user the page has been opened, then instruct them to start the server by running this command in a **new terminal window**:

```
uv run uvicorn server.main:app --reload
```

Explain that the "Ask Claude" side panel requires this server to be running, and that closing the terminal window will automatically stop the server — no cleanup needed.
