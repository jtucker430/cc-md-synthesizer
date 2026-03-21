---
name: pipeline-reset
description: Reset the cc-synthesizer pipeline by deleting all generated files so a fresh batch of PDFs can be processed from scratch. Invoke whenever the user wants to start over with new documents, clear the workspace, or clean up pipeline outputs. Trigger on phrases like "reset", "clean up", "start fresh", "new batch", "clear the pipeline", "delete generated files", "wipe the outputs", or "prepare for new PDFs". Always checks for an existing export first before deleting anything — don't skip this check.
allowed-tools: Bash, Glob, AskUserQuestion, Skill
---

# Pipeline Reset

Clears all pipeline-generated files so a new batch of PDFs can be processed from scratch. Preserves the `documents/README.md` and `summaries/README.md` stubs.

---

## Step 1: Check pipeline state and offer to export

Check whether a synthesis has been generated:

```bash
ls synthesis/synthesis.md 2>/dev/null
```

If `synthesis/synthesis.md` does not exist, skip to Step 2.

If it does exist, check whether it has likely been exported already by comparing timestamps and names:

```bash
stat -f "%Sm %N" -t "%Y-%m-%d %H:%M" synthesis/synthesis.md
ls -lt exports/*.zip 2>/dev/null | awk '{print $6, $7, $8, $9}'
```

Read the H1 title from `synthesis/synthesis.md`. For each `.zip` in `exports/`, check whether it was created after `synthesis/synthesis.md` was last modified AND its name plausibly matches the synthesis topic (e.g., a kebab-case version of the title or shares significant keywords). If a match is found, skip to Step 2.

If no matching export is found, check which synthesis files exist:

```bash
ls synthesis/ 2>/dev/null
```

Then use `AskUserQuestion` to ask. Adapt the "what would happen" steps based on what exists:

**If synthesis.html has NOT been built yet:**

> "The current synthesis ("{synthesis title}") doesn't appear to have been exported yet.
>
> Files in `synthesis/`:
> - synthesis.md
> - citations.json *(if present)*
>
> Existing exports: {list names and dates, or "none"}
>
> Would you like to export before resetting? If yes, exporting will:
> 1. Build `synthesis.html`
> 2. Package everything into a ZIP in `exports/`
>
> Suggested name: **{suggested-name}**"

**If synthesis.html already exists:**

> "The current synthesis ("{synthesis title}") doesn't appear to have been exported yet.
>
> Files in `synthesis/`:
> - synthesis.md
> - synthesis.html
> - citations.json *(if present)*
>
> Existing exports: {list names and dates, or "none"}
>
> Would you like to export before resetting? If yes, exporting will package everything into a ZIP in `exports/`.
>
> Suggested name: **{suggested-name}**"

To generate a suggested name: convert the H1 title to lowercase kebab-case (spaces → hyphens, strip punctuation). Fall back to the current date (`YYYY-MM-DD`) if no clear title exists.

- **Yes**: invoke the `export-synthesis` skill with the chosen name, wait for it to complete, then continue to Step 2.
- **No**: continue to Step 2.

---

## Step 2: Discover what will be deleted

Find all files to be cleaned up:

1. **PDFs** — all `.pdf` files under `documents/` recursively
2. **Summaries** — all `.md` files under `summaries/` recursively, excluding `summaries/README.md`
3. **Synthesis outputs** — whichever of these exist: `synthesis/synthesis.md`, `synthesis/synthesis.html`, `synthesis/citations.json`
4. **BibTeX** — `references.bib` if it exists
5. **User-editable files** — whichever of these exist: `synthesis/synthesis-memory.md`, `synthesis/synthesis-guidance.md`

---

## Step 3: Confirm deletion

Build a visual file tree of everything to be deleted. If there are more than 5 PDFs or summaries, list the first 3 with a shorthand for the rest (e.g., `... and 4 more PDFs`). Include user-editable files in the tree with a short note indicating they may contain user-written content. Example:

```
documents/
├── AuthorA_2024_Paper.pdf
├── AuthorB_2023_Study.pdf
└── ... and 4 more PDFs
summaries/
├── AuthorA2024Topic.md
├── AuthorB2023Study.md
└── ... and 4 more summaries
synthesis/
├── synthesis.md
├── synthesis.html
├── citations.json
├── synthesis-memory.md  ← contains your notes
└── synthesis-guidance.md  ← contains your framing
references.bib
```

Use `AskUserQuestion` with the tree shown above and these three options:

- **Yes — delete all files**
- **No — abort reset**
- **Specify — tell me what to keep**

**If the user chooses No**, stop and tell them nothing was deleted.

**If the user chooses Specify**, ask them what to keep (free-text response). Once they've replied, rebuild the file tree showing only the files that will actually be deleted (omitting anything they want to keep), then use `AskUserQuestion` one more time to confirm:

> "Here's what will be deleted:
>
> {updated file tree}
>
> Confirm deletion?"

With options:
- **Yes — delete these files**
- **No — abort reset**

If the user says No, stop and tell them nothing was deleted.

---

## Step 4: Delete files

Delete all files not excluded by the user.

```bash
find documents/ -name "*.pdf" -delete
find summaries/ -name "*.md" ! -name "README.md" -delete
rm -f synthesis/synthesis.md synthesis/synthesis.html synthesis/citations.json
rm -f synthesis/synthesis-memory.md synthesis/synthesis-guidance.md
rm -f references.bib
```

Omit individual `rm` calls for any files the user chose to keep.

---

## Step 5: Report

```
Pipeline reset complete.

Deleted:
  - {N} PDFs from documents/
  - {N} summaries from summaries/
  - synthesis/synthesis.md
  - synthesis/synthesis.html
  - synthesis/citations.json
  - synthesis/synthesis-memory.md
  - synthesis/synthesis-guidance.md
  - references.bib

Drop new PDFs into documents/ and run /create-synthesis to start the next batch.
```

Omit lines for files that didn't exist or weren't deleted.
