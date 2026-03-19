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
import sys
from pathlib import Path


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
    references_bib = root / "references.bib"
    manifest_json = root / "summaries" / "manifest.json"
    memory_md = root / "synthesis" / "synthesis-memory.md"
    output_html = root / "synthesis" / "synthesis.html"

    # Prerequisite checks
    if not synthesis_md.exists():
        print(
            "ERROR: synthesis/synthesis.md not found. Run /create-synthesis first.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not references_bib.exists():
        print(
            "ERROR: references.bib not found. Run /summarize-documents first.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not manifest_json.exists():
        print(
            "WARNING: summaries/manifest.json not found; "
            "citation file paths will be empty. "
            "Re-running /summarize-documents will fix this.",
            file=sys.stderr,
        )

    print("Build complete (placeholder)")  # replaced in Task 6


if __name__ == "__main__":
    main()
