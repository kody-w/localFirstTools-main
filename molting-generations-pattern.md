# Molting Generations Pattern

A reusable pattern for iteratively improving self-contained HTML applications using LLM intelligence. Each "molt" sheds the old skin and replaces it with a refined version, while archiving every prior generation.

---

## What Molting Is

Static HTML apps are written once and never improve. Molting changes that. Like a snake shedding skin, each generation strips away technical debt, accessibility gaps, and performance issues -- without changing what the app does.

**Key principle:** Improve the code, never the features. Each molt makes the app better at being what it already is.

---

## The Archive/Versioning Scheme

Every molt archives the previous version before replacing it:

```
apps/archive/
  <app-stem>/
    v1.html              # Original (generation 0 -> 1)
    v2.html              # After first molt (generation 1 -> 2)
    v3.html              # After second molt
    molt-log.json        # Audit trail
```

The live app stays in its category folder (`apps/<category>/<file>.html`). Archives are append-only -- you can always roll back.

### molt-log.json Schema

```json
[
  {
    "generation": 1,
    "date": "2026-02-07",
    "previousSize": 18500,
    "newSize": 17200,
    "previousSha256": "abc123...",
    "newSha256": "def456...",
    "focus": "structural"
  }
]
```

---

## Generation-Aware Prompts

Each generation focuses on different improvement areas. This prevents "over-polishing" the same things and ensures broad coverage across molts.

| Generation | Focus | What Gets Improved |
|------------|-------|--------------------|
| 1 | Structural | DOCTYPE, charset, viewport, semantic HTML, var->const/let, dead code removal |
| 2 | Accessibility | ARIA labels, keyboard navigation, color contrast, focus management, screen reader support |
| 3 | Performance | requestAnimationFrame, CSS transforms vs top/left, responsive design, efficient selectors |
| 4 | Polish | Error handling, edge cases, code organization, consistent naming, DRY violations |
| 5+ | Refinement | Final micro-optimizations, comments cleanup, overall coherence |

### Prompt Template

```
You are an expert HTML developer performing generation {N} improvements on a self-contained HTML application.

GENERATION {N} FOCUS: {focus_area}
{focus_specific_instructions}

HARD RULES:
1. Return ONLY the complete rewritten HTML file
2. Do NOT add new features or change functionality
3. Must remain a single self-contained .html file
4. No external dependencies (no CDN links, no external JS/CSS)
5. Must have <!DOCTYPE html>, <title>, <meta name="viewport">
6. Preserve all existing user-facing behavior exactly

HTML content:
---
{full_html_content}
---

Return ONLY the complete rewritten HTML.
```

---

## Validation Rules

Every molted output must pass these checks before replacing the original:

1. **Has DOCTYPE** -- `<!doctype html>` present (case-insensitive)
2. **Has title** -- `<title>` tag with non-empty content
3. **No external deps** -- No `<script src=`, `<link rel="stylesheet" href=` pointing to external URLs
4. **Size ratio** -- New file is between 30% and 300% of the original size
5. **File size cap** -- Input must be under 100KB (LLM context limits)

If any check fails, the original is preserved untouched and the molt is rejected.

---

## Manifest Integration

Molting adds optional fields to app entries in `manifest.json`. The gallery frontend ignores unknown keys, so this is backward-compatible.

```json
{
  "title": "Memory Training Game",
  "file": "memory-training-game.html",
  "generation": 2,
  "lastMolted": "2026-02-07",
  "moltHistory": [
    {"gen": 1, "date": "2025-12-27", "size": 21762},
    {"gen": 2, "date": "2026-02-07", "size": 19450}
  ]
}
```

---

## CLI Usage

```bash
# Molt a single app (resolves filename across all categories)
python3 scripts/molt.py memory-training-game.html

# Molt all apps in a category
python3 scripts/molt.py --category games_puzzles

# Preview without changes
python3 scripts/molt.py memory-training-game.html --dry-run

# Show generation status for all apps
python3 scripts/molt.py --status

# Roll back to a specific generation
python3 scripts/molt.py --rollback memory-training-game 1

# Set max generations (default 5)
python3 scripts/molt.py memory-training-game.html --max-gen 3
```

---

## Safeguards

- **Max generations cap** (default 5) prevents infinite molting
- **Dry-run mode** previews all changes without writing
- **Archive-before-replace** ensures no data loss
- **SHA-256 hashing** in the audit log proves provenance
- **Size ratio checks** catch truncated or bloated outputs
- **Rollback** restores any previous generation instantly

---

## Applying This Pattern to Other Projects

The molting pattern works for any file that can be:
1. Read as text
2. Sent to an LLM with improvement instructions
3. Validated programmatically
4. Archived and versioned

**Examples beyond HTML apps:**
- CSS stylesheets (focus: specificity, modern syntax, responsive)
- Python scripts (focus: type hints, docstrings, error handling)
- Markdown docs (focus: structure, clarity, completeness)
- Configuration files (focus: security, best practices, comments)

**To adapt:**
1. Change the prompt template for your file type
2. Change the validation rules for your format
3. Keep the archive/versioning scheme as-is
4. Keep the generation-aware focus rotation
