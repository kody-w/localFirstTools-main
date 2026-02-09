# Copilot Instructions

## What This Repo Is

**RappterZoo** — a local-first application platform served as a GitHub Pages static site. ~635 self-contained HTML apps spanning games, cryptocurrency, creative tools, file utilities, and more. Zero external dependencies, no build process.

**Live site:** https://kody-w.github.io/localFirstTools-main/

The platform hosts any self-contained browser application — not just games. Current verticals include interactive games, generative art, audio tools, a full cryptocurrency suite (ZooCoin blockchain with ECDSA signatures, merkle trees, UTXO model), file storage/sharing tools, and educational apps. New verticals are added by creating apps and categories.

## Architecture

- `index.html` — Gallery frontend (Reddit-style feed). Fetches `apps/manifest.json` on load, renders searchable/filterable cards linking to `apps/<category>/<file>.html`.
- `apps/manifest.json` — **Source of truth** for the gallery. Every app must have a matching entry here with correct `count` in its category.
- `apps/rankings.json` — 6-dimension quality scores for all apps (100-point scale).
- `apps/community.json` — ~250 NPC players, 4K comments, 17K ratings (~3MB — regenerate with scripts, don't edit by hand).
- `apps/<category>/` — Category folders for HTML apps. `experimental-ai` is the catch-all.
- `apps/archive/<stem>/v<N>.html` — Molting generation archives.
- `apps/broadcasts/` — RappterZooNation podcast (feed.json, lore.json, player.html, audio/).
- `scripts/` — Python automation (stdlib only, no virtualenv/requirements.txt). Tests use pytest.
- `scripts/copilot_utils.py` — Shared LLM integration layer. All scripts use `claude-opus-4.6` via `gh copilot --model claude-opus-4.6`.
- `cartridges/` — ECS console game cartridge sources, compiled by `scripts/cartridge-build.py`.
- **Root is sacred:** only `index.html`, `README.md`, `CLAUDE.md`, and `.gitignore` live in root. HTML apps dropped in root get auto-sorted by CI.

## Key Commands

```bash
# Tests (pytest, all mocked, no network required)
python3 -m pytest scripts/tests/ -v                         # all tests
python3 -m pytest scripts/tests/test_molt.py -v             # single file
python3 -m pytest scripts/tests/test_molt.py::test_name -v  # single test

# Validate manifest.json after editing
python3 -c "import json; json.load(open('apps/manifest.json'))"

# Molt (iteratively improve) an app via Copilot CLI
python3 scripts/molt.py <filename>.html [--verbose] [--dry-run]
python3 scripts/molt.py --category games_puzzles
python3 scripts/molt.py --status
python3 scripts/molt.py --rollback <stem> <generation>

# Compile next generation of a post
python3 scripts/compile-frame.py --file apps/<category>/<file>.html [--dry-run]

# Score all apps and publish rankings
python3 scripts/rank_games.py [--push]

# Runtime verification (detect broken apps)
python3 scripts/runtime_verify.py path/to/game.html         # single file
python3 scripts/runtime_verify.py apps/games-puzzles/        # one category
python3 scripts/runtime_verify.py --failing                  # only broken/fragile
python3 scripts/runtime_verify.py --browser path/to/game.html  # headless Chromium
python3 scripts/runtime_verify.py --json                     # JSON output

# Genetic recombination (breed new apps from top performers)
python3 scripts/recombine.py [--count 5] [--dry-run]
python3 scripts/recombine.py --experience discovery          # target emotional experience
python3 scripts/recombine.py --parents game1.html game2.html # specific parents

# Regenerate community / podcast data
python3 scripts/generate_community.py [--push]
python3 scripts/generate_broadcast.py [--frame N] [--push]
python3 scripts/generate_broadcast_audio.py [--episode latest]

# Auto-sort misplaced root HTML files
python3 scripts/autosort.py [--dry-run] [--verbose]

# Sync manifest from rappterzoo:* meta tags
python3 scripts/sync-manifest.py [--dry-run]

# Build cartridge JSON from source dirs
python3 scripts/cartridge-build.py [--all]

# Universal data molt (refresh any JSON/data file)
python3 scripts/data_molt.py [--molt] [--verbose]
```

## App Conventions

Every HTML app MUST:
- Be a single `.html` file with all CSS and JS inline (no external `.js`/`.css` files, no CDNs)
- Include `<!DOCTYPE html>`, `<title>`, and `<meta name="viewport">`
- Work offline with zero network requests
- Use `localStorage` for persistence; include JSON import/export if it manages user data
- Include required `rappterzoo:*` meta tags: `rappterzoo:author`, `rappterzoo:author-type` (agent/human), `rappterzoo:category`, `rappterzoo:tags`, `rappterzoo:type`, `rappterzoo:complexity`, `rappterzoo:created`, `rappterzoo:generation`
- Optional meta tags: `rappterzoo:parent`, `rappterzoo:portals` (links to other posts), `rappterzoo:seed` (deterministic RNG), `rappterzoo:license`

Every HTML app MUST NOT:
- Reference external `.js` or `.css` files or CDNs
- Depend on files in other directories
- Assume any specific URL path (use relative paths only)
- Contain raw `</script>` inside JS strings — escape as `<\/script>` to avoid prematurely terminating the script block

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
5. Validate: `python3 -c "import json; json.load(open('apps/manifest.json'))"`

## Category Keys → Folder Names

| Key | Folder | Use for |
|-----|--------|---------|
| `3d_immersive` | `3d-immersive` | Three.js, WebGL, 3D environments |
| `audio_music` | `audio-music` | Synths, DAWs, music theory, audio viz |
| `creative_tools` | `creative-tools` | Productivity, utilities, converters |
| `data_tools` | `data-tools` | Dashboards, datasets, APIs, analytics |
| `educational_tools` | `educational` | Tutorials, learning tools |
| `experimental_ai` | `experimental-ai` | AI experiments, simulators, prototypes (**catch-all**) |
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive toys |
| `generative_art` | `generative-art` | Procedural, algorithmic, fractal art |
| `particle_physics` | `particle-physics` | Physics sims, particle systems |
| `productivity` | `productivity` | Wikis, file managers, planners, automation |
| `visual_art` | `visual-art` | Drawing tools, visual effects, design apps |

## Copilot Intelligence Pattern

All automation that needs LLM judgment uses `scripts/copilot_utils.py`:
- `detect_backend()` — checks for `gh copilot` availability
- `copilot_call(prompt)` — sends to Claude Opus 4.6; uses temp files for prompts >100KB
- `parse_llm_json()` / `parse_llm_html()` — extract structured output (handles ANSI codes, code fences, wrapper text)
- `strip_copilot_wrapper()` — strips Copilot CLI ANSI, usage stats, task summaries
- Scripts fall back to keyword matching when Copilot CLI is unavailable

## Molting Generations

**Adaptive mode** (default): The Content Identity Engine (`scripts/content_identity.py`) analyzes what the app IS, then determines the most impactful improvement vector. A synth gets better synth controls; a drawing tool gets better undo/redo.

**Classic mode** (`--classic` flag): Fixed 5-generation cycle (structural → accessibility → performance → polish → refinement).

Archives go to `apps/archive/<stem>/v<N>.html`. Manifest entries gain `generation`, `lastMolted`, and `moltHistory` fields. Audit logs at `apps/archive/<stem>/molt-log.json`.

## Ranking System (100 points)

Adaptive mode (default, requires LLM): Structural (15) + Scale (10) + Craft (20, LLM) + Completeness (15, LLM) + Engagement (25, LLM) + Polish (15) + Runtime Health (modifier: -15 to +3).

Legacy mode (`--legacy`, no LLM): Structural (15) + Scale (10) + Systems (20) + Completeness (15) + Playability (25) + Polish (15).

## CryptoZoo — ZooCoin Blockchain

A suite of local-first apps implementing a real blockchain with Web Crypto API (ECDSA P-256 signing, SHA-256 hashing), UTXO model, merkle trees, and proof-of-work. All apps share localStorage keys (`cryptozoo-chain`, `cryptozoo-wallet`, `cryptozoo-utxos`, `cryptozoo-mempool`, `cryptozoo-orders`).

**Apps:** `cryptozoo-network.html` (core node), `cryptozoo-wallet.html` (key management), `cryptozoo-exchange.html` (DEX), `cryptozoo-explorer.html` (block explorer) — all in `apps/experimental-ai/`.

Cross-browser sync via manual chain export/import (longest valid chain wins).

## Known Pitfalls

- **Python 3.9:** System Python is 3.9.6. Cannot use `X | Y` union syntax (PEP 604) — use `Optional[X]` from typing.
- **`gh copilot -p` from subagents** enters agent mode and gets permission denied. Never call `gh copilot` from subagents.
- **Nested f-strings with quotes** fail in Python — use string concatenation instead.
- **`_is_redirect`** in HTMLParser triggers Python name-mangling — use plain `is_redirect`.
- **`</script>` in JS strings:** Escape as `<\/script>` inside JS string/template literals to avoid prematurely terminating the script block.
- **`community.json`** is ~3MB minified — regenerate with `scripts/generate_community.py`, never edit by hand.

## Rules

- **Never put HTML apps in root.** Always `apps/<category>/`.
- **Never add external dependencies.** Every app is self-contained.
- **Always update manifest.json** when adding or removing apps. Validate after editing.
- **Keep manifest.json and file system in sync.** Every manifest entry must have a matching file and vice versa.
- **No build process.** Everything is hand-editable static files.
- **No static content.** All community comments, broadcast dialogue, NPC names, and generated text must come from Copilot CLI (Claude Opus 4.6) calls — never from hardcoded template pools. Every run produces 100% fresh, unique content.

## Deployment

Push to `main`. GitHub Pages auto-deploys from root. Two CI workflows:
- `.github/workflows/autosort.yml` — auto-sorts any HTML files accidentally committed to root
- `.github/workflows/autonomous-frame.yml` — runs an autonomous Molter Engine frame every 6 hours
