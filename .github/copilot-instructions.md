# Copilot Instructions

## What This Repo Is

A GitHub Pages gallery serving ~450 self-contained HTML apps at `https://kody-w.github.io/localFirstTools-main/`. The brand is **RappterZoo**. No build process, no package manager, no external dependencies. Every app is a single `.html` file with all CSS/JS inline.

## Architecture

- `index.html` — Gallery frontend. Fetches `apps/manifest.json` on load, renders searchable/filterable cards linking to `apps/<category>/<file>.html`.
- `apps/manifest.json` — Source of truth for the gallery. Every app must have a matching entry here with correct `count` in its category.
- `apps/<category>/` — 9 category folders (`3d-immersive`, `audio-music`, `creative-tools`, `educational`, `experimental-ai`, `games-puzzles`, `generative-art`, `particle-physics`, `visual-art`). `experimental-ai` is the catch-all.
- `scripts/` — Python automation (no virtualenv, no requirements.txt — uses only stdlib + pytest for tests).
- `scripts/copilot_utils.py` — Shared LLM integration layer. All scripts that call Copilot CLI use `claude-opus-4.6` via `gh copilot --model claude-opus-4.6`.
- `cartridges/` — Source directories for ECS console game cartridges, compiled by `scripts/cartridge-build.py`.
- Root is sacred: only `index.html`, `README.md`, `CLAUDE.md`, and `.gitignore` live in root. HTML apps dropped in root get auto-sorted by CI.

## Key Commands

```bash
# Tests (pytest, all mocked, no network)
python3 -m pytest scripts/tests/ -v                    # all tests
python3 -m pytest scripts/tests/test_molt.py -v        # single test file
python3 -m pytest scripts/tests/test_molt.py::test_name -v  # single test

# Auto-sort misplaced root HTML files into categories
python3 scripts/autosort.py --dry-run
python3 scripts/autosort.py --verbose

# Molt (iteratively improve) an app via Copilot CLI
python3 scripts/molt.py <filename>.html --verbose
python3 scripts/molt.py --category games_puzzles

# Build cartridge JSON from source dirs
python3 scripts/cartridge-build.py --all

# Sync manifest from rappterzoo:* meta tags
python3 scripts/sync-manifest.py --dry-run

# Score all apps and publish rankings
python3 scripts/rank_games.py --verbose

# Compile next generation of a post
python3 scripts/compile-frame.py --file apps/<category>/<file>.html --dry-run
```

## App Conventions

Every HTML app MUST:
- Be a single `.html` file with all CSS and JS inline (no external `.js`/`.css` files, no CDNs)
- Include `<!DOCTYPE html>`, `<title>`, and `<meta name="viewport">`
- Work offline with zero network requests
- Use `localStorage` for persistence; include JSON import/export if it manages user data
- Use `rappterzoo:*` meta tags for embedded metadata (`rappterzoo:author`, `rappterzoo:category`, `rappterzoo:tags`, `rappterzoo:type`, `rappterzoo:complexity`, `rappterzoo:created`, `rappterzoo:generation`)

## Adding a New App

1. Create the self-contained HTML file
2. Place it in `apps/<category>/`
3. Add an entry to `apps/manifest.json` in the correct category's `apps` array:
   ```json
   {
     "title": "App Title",
     "file": "app-filename.html",
     "description": "One-line description",
     "tags": ["canvas", "animation"],
     "complexity": "simple|intermediate|advanced",
     "type": "game|visual|audio|interactive|interface",
     "featured": false,
     "created": "YYYY-MM-DD"
   }
   ```
4. Update the category's `count` field

## Category Keys → Folder Names

| Key | Folder |
|-----|--------|
| `visual_art` | `visual-art` |
| `3d_immersive` | `3d-immersive` |
| `audio_music` | `audio-music` |
| `generative_art` | `generative-art` |
| `games_puzzles` | `games-puzzles` |
| `particle_physics` | `particle-physics` |
| `creative_tools` | `creative-tools` |
| `educational_tools` | `educational` |
| `experimental_ai` | `experimental-ai` |

## Copilot Intelligence Pattern

All automation that needs LLM judgment uses `scripts/copilot_utils.py`:
- `detect_backend()` checks for `gh copilot` availability
- `copilot_call(prompt)` sends to Claude Opus 4.6; uses temp files for prompts >100KB
- `parse_llm_json()` / `parse_llm_html()` extract structured output from Copilot CLI responses (handles ANSI codes, code fences, wrapper text)
- Scripts fall back to keyword matching when Copilot is unavailable

## Molting Generations

Apps evolve through up to 5 generations, each focusing on a quality dimension (structural → accessibility → performance → polish → refinement). Archives go to `apps/archive/<stem>/v<N>.html`. Manifest entries gain `generation`, `lastMolted`, and `moltHistory` fields.

## Deployment

Push to `main`. GitHub Pages auto-deploys from root. The `.github/workflows/autosort.yml` action auto-sorts any HTML files accidentally committed to root.
