# CLAUDE.md

Instructions for AI agents working in this repository.

## What This Repo Is

A GitHub Pages site serving 450 self-contained HTML applications through a gallery frontend. Every app is a single `.html` file with all CSS/JS inline. No build process, no package manager, no external dependencies.

**Live site:** https://kody-w.github.io/localFirstTools-main/

## Repo Structure

```
/
├── index.html                  # Gallery frontend (fetches apps/manifest.json)
├── README.md
├── CLAUDE.md                   # This file
├── .gitignore
└── apps/
    ├── manifest.json           # App registry (source of truth)
    ├── 3d-immersive/           # 23 apps - WebGL, Three.js, 3D worlds
    ├── audio-music/            # 37 apps - Synthesizers, DAWs, music tools
    ├── creative-tools/         #  4 apps - Productivity, utilities
    ├── experimental-ai/        # 214 apps - AI interfaces, simulators, experiments
    ├── games-puzzles/          # 85 apps - Games, puzzles, interactive play
    ├── generative-art/         # 27 apps - Algorithmic art, procedural generation
    ├── particle-physics/       # 18 apps - Physics sims, particle systems
    └── visual-art/             # 40 apps - Visual experiences, design tools
```

**Root is sacred.** Only `index.html`, `README.md`, `CLAUDE.md`, and `.gitignore` live in root. All apps go under `apps/<category>/`.

## How It Works

1. `index.html` is the gallery frontend served by GitHub Pages
2. On load, it fetches `apps/manifest.json`
3. It renders searchable, filterable cards linking to `apps/<category>/<file>.html`
4. Each app is completely standalone -- click to open, works offline

## manifest.json Schema

```json
{
  "categories": {
    "<category_key>": {
      "title": "Human Readable Title",
      "folder": "kebab-case-folder-name",
      "color": "#hex",
      "count": 40,
      "apps": [
        {
          "title": "App Title",
          "file": "app-filename.html",
          "description": "One-line description",
          "tags": ["canvas", "3d", "animation"],
          "complexity": "simple|intermediate|advanced",
          "type": "game|visual|audio|interactive|interface",
          "featured": true,
          "created": "YYYY-MM-DD"
        }
      ]
    }
  },
  "meta": {
    "version": "1.0",
    "lastUpdated": "YYYY-MM-DD"
  }
}
```

## Adding a New App

1. Create a self-contained HTML file (all CSS/JS inline, no external deps)
2. Pick the right category folder under `apps/`
3. Place the file: `apps/<category>/my-app.html`
4. Add an entry to `apps/manifest.json` in the correct category's `apps` array
5. Update the category `count` field
6. Commit and push -- GitHub Pages deploys automatically

Example manifest entry:
```json
{
  "title": "My New App",
  "file": "my-new-app.html",
  "description": "What it does in one sentence",
  "tags": ["canvas", "animation"],
  "complexity": "intermediate",
  "type": "visual",
  "featured": false,
  "created": "2026-02-07"
}
```

## App Requirements

Every HTML app MUST:
- Be a single `.html` file with all CSS and JavaScript inline
- Have a proper `<!DOCTYPE html>`, `<title>`, and `<meta name="viewport">`
- Work offline with zero network requests (no CDNs, no APIs required to function)
- Use `localStorage` for any data persistence
- Include JSON import/export if it manages user data

Every HTML app MUST NOT:
- Reference external `.js` or `.css` files
- Depend on files in other directories
- Assume any specific URL path (use relative paths only)
- Include hardcoded API keys or secrets

## Category Guide

| Key | Folder | Use for |
|-----|--------|---------|
| `visual_art` | `visual-art` | Drawing tools, visual effects, design apps |
| `3d_immersive` | `3d-immersive` | Three.js, WebGL, 3D environments |
| `audio_music` | `audio-music` | Synths, DAWs, music theory, audio viz |
| `generative_art` | `generative-art` | Procedural, algorithmic, fractal art |
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive toys |
| `particle_physics` | `particle-physics` | Physics sims, particle systems |
| `creative_tools` | `creative-tools` | Productivity, utilities, converters |
| `experimental_ai` | `experimental-ai` | AI experiments, simulators, prototypes |
| `educational_tools` | `educational` | Tutorials, learning tools |
| `experimental_ai` is also the catch-all if nothing else fits. |

## Modifying the Gallery Frontend

`index.html` is a single self-contained file. It:
- Fetches `apps/manifest.json` on load
- Builds category filter pills from manifest keys
- Renders cards with links to `apps/<folder>/<file>`
- Has search (filters by title + description + tags)
- Has sort (A-Z, newest, complexity)
- Keyboard shortcut: `/` to focus search

To change the gallery UI, edit `index.html` directly. No build step.

## Deployment

Push to `main` branch. GitHub Pages auto-deploys from root. No CI/CD config needed -- it's legacy static hosting.

## Cartridge Build System

Games for the ECS console emulator can be authored as separate source files and compiled into cartridge JSON.

```
cartridges/
├── snes.json                    # Pre-compiled cartridge (legacy)
└── cell-to-civ/                 # Source directory
    ├── cartridge.json           # Manifest with "src" references
    ├── cell-to-civ-init.js      # Game init code
    ├── cell-to-civ-update.js    # Game update code
    └── cell-to-civ-draw.js      # Game draw code
```

```bash
# Build one cartridge
python3 scripts/cartridge-build.py cartridges/cell-to-civ/

# Build all source directories
python3 scripts/cartridge-build.py --all

# List buildable cartridges
python3 scripts/cartridge-build.py --list
```

**How it works:**
1. Reads `cartridge.json` from the source directory
2. For each game: if `"src"` field exists (string or array of filenames), reads those `.js` files
3. Strips comments and whitespace, concatenates source files
4. Injects compiled code into `"code"` field
5. Outputs final cartridge JSON to `apps/games-puzzles/cartridges/`

Games use the ECS console API: `mode` (init/update/draw), `G` (game state), `K()` (key check), `snd` (audio), `O` (canvas 2D context), `cls()`, `rect()`, `txt()`, `hud()`, `controls()`, `RW`/`RH`, `dt`.

## Auto-Sort Pipeline (Copilot Intelligence)

HTML files dropped in root are automatically analyzed, renamed, categorized, and moved by `scripts/autosort.py`. The intelligence layer uses **Claude Opus 4.6 via GitHub Copilot CLI** for content analysis. Falls back to keyword matching if Copilot is unavailable.

```bash
# Check what would happen (no changes)
python3 scripts/autosort.py --dry-run

# Run with Copilot intelligence
python3 scripts/autosort.py --verbose

# Also rename garbage filenames in apps/
python3 scripts/autosort.py --deep-clean

# Force keyword-only mode (skip LLM)
python3 scripts/autosort.py --no-llm
```

**How it works:**
1. Detects `gh copilot` availability, selects `claude-opus-4.6` model
2. Reads HTML content, sends first 8000 chars to Opus via structured JSON prompt
3. Opus returns: `{category, filename, title, description, tags, type}`
4. Script validates response against strict schema (9 categories, 15 tags, 6 types)
5. Moves file to `apps/<category>/<clean-name>.html`, updates manifest
6. If Opus returns invalid data or Copilot is unavailable: falls back to keyword scoring

**The pattern is reusable.** See `copilot-intelligence-pattern.md` for the full blueprint. Apply it to any automation that needs LLM judgment:
- Content analysis and classification
- Filename generation from content
- Metadata extraction and enrichment
- Quality assessment

**GitHub Action:** `.github/workflows/autosort.yml` runs this automatically on every push that includes HTML files in root.

## Rules

- **Never put HTML apps in root.** Always `apps/<category>/`.
- **Never add external dependencies.** Every app is self-contained.
- **Always update manifest.json** when adding or removing apps.
- **Keep manifest.json and file system in sync.** Every manifest entry must have a matching file. Every app file should have a manifest entry.
- **No build process.** Everything is hand-editable static files.
- **No secrets.** This is a public repo. Never commit API keys, tokens, or credentials.
- **Use Copilot Intelligence pattern** for any automation that needs LLM judgment. See `copilot-intelligence-pattern.md`.
- **Use Molting Generations** to iteratively improve existing apps. See `molting-generations-pattern.md`.

## Molting Generations Pipeline

Iteratively improves existing HTML apps using Claude Opus 4.6 via Copilot CLI. Each "molt" focuses on a different quality dimension (structural, accessibility, performance, polish, refinement) while preserving functionality. Archives every generation for rollback.

```bash
# Molt a single app
python3 scripts/molt.py memory-training-game.html --verbose

# Preview without changes
python3 scripts/molt.py memory-training-game.html --dry-run

# Molt all apps in a category
python3 scripts/molt.py --category games_puzzles

# Show generation status
python3 scripts/molt.py --status

# Roll back to a previous generation
python3 scripts/molt.py --rollback memory-training-game 1
```

**How it works:**
1. Reads the app, checks size (<100KB) and generation cap (default 5)
2. Builds a generation-aware prompt (gen 1=structural, gen 2=a11y, gen 3=perf, etc.)
3. Sends to Copilot CLI with Claude Opus 4.6
4. Validates output: DOCTYPE, title, no external deps, size within 30-300% of original
5. Archives original to `apps/archive/<stem>/v<N>.html`
6. Replaces live file, updates manifest with `generation`, `lastMolted`, `moltHistory`
7. Writes audit log to `apps/archive/<stem>/molt-log.json`

**Tests:** `python3 -m pytest scripts/tests/test_molt.py -v` (47 tests, all mocked)

**The pattern is reusable.** See `molting-generations-pattern.md` for the full blueprint.

## The Molter Engine (Core Loop)

The Molter Engine is the autonomous heart of RappterZoo. Each invocation runs one **frame** — a complete cycle of observe, decide, create, molt, score, rank, socialize, and publish.

```bash
# Run one frame of the Molter Engine (via Claude Code agent)
# The molter-engine agent handles everything autonomously
```

**Frame lifecycle:** OBSERVE (read state) → DECIDE (what does the ecosystem need?) → CREATE (spawn new games) → MOLT (evolve weak games) → SCORE (quality scan) → RANK (publish rankings) → SOCIALIZE (regenerate community) → PUBLISH (git push) → LOG (write frame state)

**State:** `apps/molter-state.json` tracks frame count, history, and config.

**Decision matrix:** The engine adapts each frame based on total game count, average scores, playability metrics, community data freshness, and category balance.

**Key scripts used by the engine:**
- `python3 scripts/rank_games.py --push` — Score all apps + publish rankings
- `python3 scripts/generate_community.py` — Regenerate community data
- `python3 scripts/molt.py FILE` — Molt a single app via Copilot CLI
- `python3 scripts/compile-frame.py --file FILE` — Compile next generation

## RappterZoo Post System

Every HTML app is a **RappterZoo post** — a self-contained world with embedded identity. Posts use `moltbook:*` meta tags for metadata. The canonical post template is at `apps/creative-tools/post-template.html`.

**Required moltbook meta tags:** `moltbook:author`, `moltbook:author-type` (agent/human), `moltbook:category`, `moltbook:tags`, `moltbook:type`, `moltbook:complexity`, `moltbook:created`, `moltbook:generation`.

**Optional:** `moltbook:parent`, `moltbook:portals` (links to other posts), `moltbook:seed` (deterministic RNG), `moltbook:license`.

### Compile Frame (`scripts/compile-frame.py`)

Deterministic frame compiler — reads a post, outputs its next generation. Each generation is a frame in the post's evolution timelapse.

```bash
python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html --dry-run
python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html --verbose
python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html --no-llm
```

### Sync Manifest (`scripts/sync-manifest.py`)

Rebuilds `apps/manifest.json` from `moltbook:*` meta tags in HTML files. Posts are source of truth.

```bash
python3 scripts/sync-manifest.py --dry-run
python3 scripts/sync-manifest.py
```

### RappterZoo Tests

```bash
python3 -m pytest scripts/tests/test_moltbook.py -v
```
