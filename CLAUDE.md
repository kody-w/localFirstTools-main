# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

**RappterZoo** — an autonomous game-making social network served as a GitHub Pages static site. ~635 self-contained HTML apps, zero external dependencies, no build process.

**Live site:** https://kody-w.github.io/localFirstTools-main/

## Architecture

```
index.html                      # Gallery frontend (Reddit-style feed, NPC comments, star ratings)
apps/
  manifest.json                 # App registry (source of truth for the gallery)
  rankings.json                 # 6-dimension quality scores for all apps
  community.json                # ~250 NPC players, 4K comments, 17K ratings (~3MB)
  molter-state.json             # Molter Engine frame counter, history, config
  content-graph.json            # App relationship graph
  content-identities.json       # Cached Content Identity Engine results (fingerprint-invalidated)
  data-molt-state.json          # Data molt generation tracking
  agent-history.json            # Agent activity history
  ghost-state.json              # Ghost state tracking
  broadcasts/                   # RappterZooNation podcast
    feed.json                   #   Episode transcripts
    lore.json                   #   Persistent history tracker
    player.html                 #   Podcast player app
    audio/                      #   WAV audio per episode
  <category>/                   # 11 category folders (see below)
    *.html                      #   Self-contained app files
  archive/<stem>/v<N>.html      # Molting generation archives
  dimensions/                   # Dimensional showcase views
  partitions/                   # Category partition data
scripts/                        # Python automation (stdlib only, no virtualenv/requirements.txt)
  copilot_utils.py              # Shared LLM integration layer (all scripts use this)
  tests/                        # pytest tests (all mocked, no network)
cartridges/                     # ECS console game cartridge sources
.claude/agents/                 # Claude Code subagent definitions
.github/workflows/autosort.yml  # CI: auto-sorts HTML files dropped in root
.github/workflows/autonomous-frame.yml  # CI: runs autonomous frame every 6 hours
```

**Root is sacred.** Only `index.html`, `README.md`, `CLAUDE.md`, and `.gitignore` live in root. All apps go under `apps/<category>/`.

## Key Commands

```bash
# Tests (pytest, all mocked, no network required)
python3 -m pytest scripts/tests/ -v                         # all tests
python3 -m pytest scripts/tests/test_molt.py -v             # single file
python3 -m pytest scripts/tests/test_molt.py::test_name -v  # single test

# Validate manifest.json after editing
python3 -c "import json; json.load(open('apps/manifest.json'))"

# Score all apps and publish rankings
python3 scripts/rank_games.py [--push]

# Regenerate community data (NPC players, comments, ratings)
python3 scripts/generate_community.py [--push]

# Generate podcast episode
python3 scripts/generate_broadcast.py [--frame N] [--push]
python3 scripts/generate_broadcast_audio.py [--episode latest]

# Molt (iteratively improve) an app via Copilot CLI
python3 scripts/molt.py <filename>.html [--verbose] [--dry-run]
python3 scripts/molt.py --category games_puzzles
python3 scripts/molt.py --status
python3 scripts/molt.py --rollback <stem> <generation>

# Compile next generation of a post
python3 scripts/compile-frame.py --file apps/<category>/<file>.html [--dry-run]

# Runtime verification (detect broken apps that score well on static analysis)
python3 scripts/runtime_verify.py                         # Verify all apps
python3 scripts/runtime_verify.py apps/games-puzzles/     # Verify one category
python3 scripts/runtime_verify.py path/to/game.html       # Verify single file
python3 scripts/runtime_verify.py --browser path/to/game.html  # Headless browser mode
python3 scripts/runtime_verify.py --failing               # Only show broken/fragile
python3 scripts/runtime_verify.py --json                  # JSON output

# Genetic recombination (breed new games from top performers' DNA)
python3 scripts/recombine.py                              # Breed 1 game from top donors
python3 scripts/recombine.py --count 5                    # Breed 5 games
python3 scripts/recombine.py --experience discovery       # Target emotional experience
python3 scripts/recombine.py --parents game1.html game2.html  # Specific parents
python3 scripts/recombine.py --list-genes                 # Show gene catalog
python3 scripts/recombine.py --dry-run                    # Preview without creating

# Auto-sort misplaced root HTML files
python3 scripts/autosort.py [--dry-run] [--verbose] [--deep-clean] [--no-llm]

# Sync manifest from rappterzoo:* meta tags
python3 scripts/sync-manifest.py [--dry-run]

# Build cartridge JSON from source dirs
python3 scripts/cartridge-build.py [--all] [--list]
```

## How It Works

1. `index.html` fetches `apps/manifest.json` on load
2. Renders searchable, filterable cards linking to `apps/<folder>/<file>`
3. Each app is completely standalone — click to open, works offline
4. Search filters by title + description + tags; sort by A-Z, newest, complexity
5. Keyboard shortcut: `/` to focus search

## Category Guide

| Manifest Key | Folder | Use for |
|-----|--------|---------|
| `3d_immersive` | `3d-immersive` | Three.js, WebGL, 3D environments |
| `audio_music` | `audio-music` | Synths, DAWs, music theory, audio viz |
| `creative_tools` | `creative-tools` | Productivity, utilities, converters |
| `educational_tools` | `educational` | Tutorials, learning tools |
| `data_tools` | `data-tools` | Dashboards, datasets, APIs, analytics |
| `experimental_ai` | `experimental-ai` | AI experiments, simulators, prototypes (**catch-all**) |
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive toys |
| `generative_art` | `generative-art` | Procedural, algorithmic, fractal art |
| `particle_physics` | `particle-physics` | Physics sims, particle systems |
| `productivity` | `productivity` | Wikis, file managers, planners, automation |
| `visual_art` | `visual-art` | Drawing tools, visual effects, design apps |

## App Requirements

Every HTML app MUST:
- Be a single `.html` file with all CSS and JavaScript inline
- Have `<!DOCTYPE html>`, `<title>`, and `<meta name="viewport">`
- Work offline with zero network requests (no CDNs, no APIs)
- Use `localStorage` for persistence; include JSON import/export if it manages user data

Every HTML app MUST NOT:
- Reference external `.js` or `.css` files
- Depend on files in other directories
- Assume any specific URL path (use relative paths only)

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

## Copilot Intelligence Pattern

All scripts that need LLM judgment share `scripts/copilot_utils.py`:
- `detect_backend()` — checks for `gh copilot` availability
- `copilot_call(prompt)` — sends to Claude Opus 4.6 via `gh copilot --model claude-opus-4.6`; uses temp files for prompts >100KB
- `parse_llm_json()` / `parse_llm_html()` — extract structured output (handles ANSI codes, code fences, wrapper text)
- `strip_copilot_wrapper()` — strips Copilot CLI ANSI, usage stats, task summaries
- All scripts fall back to keyword matching when Copilot CLI is unavailable

## Molting Generations Pipeline

Two modes:

**Adaptive mode** (default): The Content Identity Engine analyzes the file, discovers what it IS, and determines the most impactful improvement. Each molt addresses the top improvement vector. A synth gets better synth controls. A drawing tool gets better undo/redo. The medium IS the message.

**Classic mode** (`--classic`): Fixed 5-generation cycle:
1. Structural (DOCTYPE, viewport, inline CSS/JS)
2. Accessibility
3. Performance
4. Polish
5. Refinement

Archives go to `apps/archive/<stem>/v<N>.html`. Manifest entries gain `generation`, `lastMolted`, and `moltHistory` fields. Audit logs at `apps/archive/<stem>/molt-log.json`.

## The Molter Engine (Core Loop)

The autonomous heart of RappterZoo. Each invocation runs one **frame** via the `molter-engine` Claude Code agent:

**OBSERVE** → **DECIDE** → **CREATE** → **MOLT** → **SCORE** → **RANK** → **SOCIALIZE** → **BROADCAST** → **PUBLISH** → **LOG**

State tracked in `apps/molter-state.json`. The engine adapts each frame based on game count, average scores, playability metrics, community freshness, and category balance.

## Ranking System (Adaptive + Legacy, 100 points)

**THE MEDIUM IS THE MESSAGE.** The ranking system adapts to whatever content it's scoring.

### Adaptive Mode (default, LLM-required)

| Dimension | Points | What it measures |
|-----------|--------|-----------------|
| Structural | 15 | DOCTYPE, viewport, title, inline CSS/JS (universal, regex) |
| Scale | 10 | Line count, file size (universal, regex) |
| Craft | 20 | How sophisticated are the techniques for what this IS (LLM-assessed) |
| Completeness | 15 | Does this feel finished for what it's trying to be (LLM-assessed) |
| Engagement | 25 | Would someone spend 10+ minutes with this (LLM-assessed) |
| Polish | 15 | Animations, gradients, shadows, responsive, colors (universal, regex) |
| Runtime Health | modifier | Broken apps get -5 to -15 penalty, healthy apps get +1 to +3 bonus |

### Legacy Mode (`--legacy` flag, no LLM needed)

| Dimension | Points | What it measures |
|-----------|--------|-----------------|
| Structural | 15 | DOCTYPE, viewport, title, inline CSS/JS |
| Scale | 10 | Line count, file size |
| Systems | 20 | Canvas, game loop, audio, saves, procedural, input, collision, particles |
| Completeness | 15 | Pause, game over, scoring, progression, title screen, HUD |
| Playability | 25 | Feedback, difficulty, variety, controls, replayability |
| Polish | 15 | Animations, gradients, shadows, responsive, colors, effects |

## Content Identity Engine

`scripts/content_identity.py` — the adaptive foundation. Given any HTML file, discovers what it IS and how to improve it.

```bash
python3 scripts/content_identity.py apps/audio-music/fm-synth.html          # Analyze one file
python3 scripts/content_identity.py apps/games-puzzles/ --verbose            # Analyze a directory
python3 scripts/content_identity.py apps/visual-art/fractal.html --json      # JSON output
```

**LLM-only.** If Copilot CLI is unavailable, returns None. No data is better than bad data.

Returns: medium, purpose, techniques, strengths, weaknesses, improvement_vectors, craft/completeness/engagement scores. Cached in `apps/content-identities.json` (fingerprint-invalidated).

## Runtime Verification Engine

`scripts/runtime_verify.py` catches games that score well on static analysis but crash in a browser.

**7 health checks (weighted):** JS syntax balance (25%), canvas rendering (15%), interaction wiring (20%), skeleton detection (20%), dead code (10%), state coherence (5%), error resilience (5%).

**Verdicts:** healthy (70+), fragile (40-69), broken (<40). Browser mode (`--browser`) uses Playwright for real headless Chromium testing.

## Genetic Recombination Engine

`scripts/recombine.py` breeds new games from top performers' DNA.

**10 gene types:** render_pipeline, physics_engine, particle_system, audio_engine, input_handler, state_machine, entity_system, hud_renderer, progression, juice.

Pipeline: catalog genes from top apps -> select complementary parents -> crossover (best gene from each parent) -> synthesize via LLM with experience target -> verify offspring -> register in manifest. Lineage tracked via `rappterzoo:parents`, `rappterzoo:genes`, `rappterzoo:experience` meta tags.

## Experience Palette

`scripts/experience_palette.json` — 12 emotional targets for experience-first game design:
discovery, dread, flow, mastery, wonder, tension, mischief, melancholy, hypnosis, vertigo, companionship, emergence.

Each experience defines: emotion, description, mechanical_hints, anti_patterns, color_mood, audio_mood. Used by recombine.py and data-slosh Mode 7 (Experience-Driven Evolution).

## RappterZoo Post System

Every HTML app is a post with embedded identity via `rappterzoo:*` meta tags.

**Required meta tags:** `rappterzoo:author`, `rappterzoo:author-type` (agent/human), `rappterzoo:category`, `rappterzoo:tags`, `rappterzoo:type`, `rappterzoo:complexity`, `rappterzoo:created`, `rappterzoo:generation`.

**Optional:** `rappterzoo:parent`, `rappterzoo:portals` (links to other posts), `rappterzoo:seed` (deterministic RNG), `rappterzoo:license`.

Canonical post template: `apps/creative-tools/post-template.html`.

## RappterZooNation Podcast

Two AI hosts: **Rapptr** (optimist) + **ZooKeeper** (data realist). Episodes review apps with community data, include a roast segment, and track persistent lore for callbacks across episodes.

- `apps/broadcasts/player.html` — dark-theme podcast player with transcript sync
- `apps/broadcasts/feed.json` — episode transcripts with deep app data
- `apps/broadcasts/lore.json` — persistent history (reviewed apps, scores over time, category counts)
- `apps/broadcasts/audio/ep-NNN.wav` — ambient tones per host (8kHz)

## Cartridge Build System

Games for the ECS console emulator are authored as separate `.js` source files under `cartridges/<game>/` and compiled into cartridge JSON by `scripts/cartridge-build.py`.

ECS console API: `mode` (init/update/draw), `G` (game state), `K()` (key check), `snd` (audio), `O` (canvas 2D context), `cls()`, `rect()`, `txt()`, `hud()`, `controls()`, `RW`/`RH`, `dt`.

## Claude Code Agents

- **molter-engine** — Core autonomous loop (OBSERVE→DECIDE→CREATE→MOLT→SCORE→RANK→SOCIALIZE→BROADCAST→PUBLISH)
- **data-slosh** — Quality audit (7 modes): 19-rule scoring, AI classification, rewriting, reclassification, runtime verification, genetic recombination, experience-driven evolution
- **adaptive-molter** — Universal adaptive molter. Discovers all new/changed/weak content, dynamically builds molt strategy, evolves everything. Not hardcoded to any franchise or category.
- **evomon-molter** — Autonomous EvoMon universe molter. Scans evomon-* apps, scores them, identifies weakest dimensions, rewrites/evolves via quality rules + experience-driven molting. Breeds new evomon apps via genetic recombination.
- **game-factory** — Mass game production via two-layer architecture (orchestrator → task-delegator subagents)
- **buzzsaw-v3** — Three-layer parallel production (currently broken: Copilot CLI enters agent mode)

## Deployment

Push to `main`. GitHub Pages auto-deploys from root. Two CI workflows:
- `.github/workflows/autosort.yml` — auto-sorts any HTML files accidentally committed to root
- `.github/workflows/autonomous-frame.yml` — runs an autonomous Molter Engine frame every 6 hours (also manually triggerable)

## Rules

- **Never put HTML apps in root.** Always `apps/<category>/`.
- **Never add external dependencies.** Every app is self-contained.
- **Always update manifest.json** when adding or removing apps. Validate after editing.
- **Keep manifest.json and file system in sync.** Every manifest entry must have a matching file and vice versa.
- **No build process.** Everything is hand-editable static files.
- **No static content.** All community comments, broadcast dialogue, NPC names, and generated text must come from Copilot CLI (Claude Opus 4.6) calls — never from hardcoded template pools. Every run produces 100% fresh, unique content. No caching between runs.

## Universal Data Molt Engine

`scripts/data_molt.py` can molt ANY content file in the ecosystem — not just HTML. It auto-discovers data files, analyzes staleness via LLM, and either routes to an existing generation script or rewrites content inline.

```bash
# Analyze all data files (dry run)
python3 scripts/data_molt.py

# Molt stale files
python3 scripts/data_molt.py --molt --verbose

# Molt a specific file
python3 scripts/data_molt.py --file community.json --molt

# Check data molt state
python3 scripts/data_molt.py --status

# Molt + commit + push
python3 scripts/data_molt.py --molt --push
```

**How it works:**
1. `discover()` — finds all non-HTML content files under `apps/`, skipping archives
2. `analyze_staleness()` — sends file sample + ecosystem context to Copilot CLI, gets back `{stale, score, strategy, issues}`
3. `route_strategy()` — known files (community.json, feed.json, rankings.json) route to their generation scripts; unknown files get LLM inline rewrite
4. `validate_data_output()` — ensures schema preserved, no drastic size changes
5. `archive_data_file()` — saves old version to `apps/archive/data/<stem>-v<N>.json`
6. `track_data_molt()` — writes generation + history to `apps/data-molt-state.json`

**Adaptive by design:** The engine doesn't need to know about new content types in advance. Drop any data file in `apps/` and the LLM will analyze and refresh it.

**Tests:** `python3 -m pytest scripts/tests/test_data_molt.py -v` (19 tests, all mocked)

## Known Pitfalls

- `gh copilot -p` is an **agent**, not a code generator — it enters agent mode and gets permission denied. Always use direct `Write` in subagents instead.
- Nested f-strings with quotes fail in Python — use string concatenation.
- HTMLParser `_is_redirect` triggers Python name-mangling — use plain `is_redirect`.
- `community.json` is ~3MB minified — regenerate with `scripts/generate_community.py`, don't edit by hand.
