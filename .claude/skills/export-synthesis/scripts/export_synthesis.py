#!/usr/bin/env python3
"""
export_synthesis.py — Package the synthesis into a shareable, self-contained directory + ZIP.

Creates a new directory (default: synthesis-export/) containing:
  synthesis.html      — HTML with fixed asset paths and Ask Claude button hidden
  assets/style.css    — CSS with Ask Claude button hidden via display:none
  assets/script.js    — JS (copied as-is; button hidden by CSS so it never fires)
  documents/          — All source PDFs (preserving subdirectory structure)
  summaries/          — All summary .md files (preserving subdirectory structure)
  citations.json      — Citation metadata (for reference)

Then zips the directory into <name>.zip.

Usage:
    uv run python .claude/skills/export-synthesis/scripts/export_synthesis.py [--root DIR] [--name NAME]
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

HIDE_ASK_CLAUDE_CSS = """
/* Export package: Ask Claude functionality is not available without the local server. */
.ask-btn { display: none !important; }
#response-panel { display: none !important; }
"""


def main():
    parser = argparse.ArgumentParser(
        description="Export synthesis package as a self-contained directory + ZIP"
    )
    parser.add_argument(
        "--root", default=None, help="Repo root directory (default: cwd)"
    )
    parser.add_argument(
        "--name",
        default="synthesis-export",
        help="Output directory/ZIP name (default: synthesis-export)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    name = args.name

    # Input paths
    synthesis_html = root / "synthesis" / "synthesis.html"
    style_css = root / "scripts" / "templates" / "style.css"
    script_js = root / "scripts" / "templates" / "script.js"
    documents_dir = root / "documents"
    summaries_dir = root / "summaries"

    # citations.json — check synthesis/ first (post-refactor location), then root
    citations_json = root / "synthesis" / "citations.json"
    if not citations_json.exists():
        alt = root / "citations.json"
        if alt.exists():
            citations_json = alt

    # Output paths
    exports_root = root / "exports"
    exports_root.mkdir(parents=True, exist_ok=True)
    export_dir = exports_root / name
    output_zip = exports_root / f"{name}.zip"

    # ── Validation ────────────────────────────────────────────────────────────
    errors = []
    if not synthesis_html.exists():
        errors.append(
            "synthesis/synthesis.html not found — run `uv run python scripts/build_html.py` first"
        )
    if not style_css.exists():
        errors.append("scripts/templates/style.css not found")
    if not script_js.exists():
        errors.append("scripts/templates/script.js not found")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Clean up any previous export directory ────────────────────────────────
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True)

    # ── 1. synthesis.html — fix asset paths ──────────────────────────────────
    html = synthesis_html.read_text(encoding="utf-8")
    html = html.replace(
        'href="../scripts/templates/style.css"',
        'href="assets/style.css"',
    )
    html = html.replace(
        'src="../scripts/templates/script.js"',
        'src="assets/script.js"',
    )
    (export_dir / "synthesis.html").write_text(html, encoding="utf-8")

    # ── 2. assets/style.css — append hide-button rule ────────────────────────
    assets_dir = export_dir / "assets"
    assets_dir.mkdir()
    css = style_css.read_text(encoding="utf-8")
    css += HIDE_ASK_CLAUDE_CSS
    (assets_dir / "style.css").write_text(css, encoding="utf-8")

    # ── 3. assets/script.js — copy as-is ─────────────────────────────────────
    shutil.copy2(script_js, assets_dir / "script.js")

    # ── 4. citations.json — copy if available ─────────────────────────────────
    if citations_json.exists():
        shutil.copy2(citations_json, export_dir / "citations.json")

    # ── 5. documents/**/*.pdf ─────────────────────────────────────────────────
    pdf_count = 0
    if documents_dir.exists():
        for pdf in sorted(documents_dir.rglob("*.pdf")):
            rel = pdf.relative_to(documents_dir)
            dest = export_dir / "documents" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, dest)
            pdf_count += 1

    # ── 6. summaries/**/*.md ──────────────────────────────────────────────────
    md_count = 0
    if summaries_dir.exists():
        for md in sorted(summaries_dir.rglob("*.md")):
            rel = md.relative_to(summaries_dir)
            dest = export_dir / "summaries" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md, dest)
            md_count += 1

    # ── 7. Create ZIP ─────────────────────────────────────────────────────────
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(export_dir.rglob("*")):
            if file.is_file():
                arcname = file.relative_to(root)
                zf.write(file, arcname)

    size_mb = output_zip.stat().st_size / (1024 * 1024)

    # ── Report ────────────────────────────────────────────────────────────────
    print("Export complete!")
    print(f"  Directory: {export_dir}")
    print(f"  ZIP:       {output_zip}  ({size_mb:.1f} MB)")
    print(f"  PDFs:      {pdf_count}")
    print(f"  Summaries: {md_count}")
    print()
    print("Recipients can unzip and open synthesis.html in any browser.")
    print("No server or software installation required.")


if __name__ == "__main__":
    main()
