# skills.md

Operational playbook for agents working in `localFirstTools-main`. This is the only file you need to read to understand and operate this repo.

---

## Skill 1: Understand the System

This is a **static GitHub Pages site** at `https://kody-w.github.io/localFirstTools-main/`. It serves 450 self-contained HTML applications through a gallery frontend.

**Architecture:**
```
index.html           → Gallery UI (reads manifest, renders cards, links to apps)
apps/manifest.json   → Single source of truth for all app metadata
apps/<category>/     → HTML app files organized by category
```

**Data flow:** User visits site → `index.html` loads → fetches `apps/manifest.json` → renders filterable/searchable card grid → user clicks card → opens `apps/<category>/<file>.html`

**Deployment:** Push to `main` → GitHub Pages auto-deploys. No CI, no build, no config.

---

## Skill 2: Add a New App

**Steps:**
```bash
# 1. Create the app (single HTML file, everything inline)
# 2. Put it in the right category folder
cp my-app.html apps/games-puzzles/

# 3. Add to manifest
# Edit apps/manifest.json → find the right category → add entry to "apps" array
# 4. Bump the category "count" field
# 5. Commit and push
git add apps/games-puzzles/my-app.html apps/manifest.json
git commit -m "Add my-app to games-puzzles"
git push origin main
```

**Manifest entry format:**
```json
{
  "title": "My App",
  "file": "my-app.html",
  "description": "One sentence about what it does",
  "tags": ["canvas", "game"],
  "complexity": "simple",
  "type": "game",
  "featured": false,
  "created": "2026-02-07"
}
```

**Field rules:**
- `file` — Exact filename, must match the file in the category folder
- `tags` — Pick from: `3d`, `canvas`, `svg`, `animation`, `particles`, `physics`, `audio`, `interactive`, `game`, `creative`, `terminal`, `retro`, `simulation`, `ai`, `crm`
- `complexity` — `simple` (<20KB), `intermediate` (20-50KB), `advanced` (>50KB or uses WebGL/3D)
- `type` — `game`, `visual`, `audio`, `interactive`, `interface`, `drawing`
- `featured` — Set `true` only for standout apps

---

## Skill 3: Pick the Right Category

| If the app is about... | Put it in | Manifest key |
|------------------------|-----------|--------------|
| Drawing, design, visual effects | `apps/visual-art/` | `visual_art` |
| 3D worlds, WebGL, Three.js | `apps/3d-immersive/` | `3d_immersive` |
| Sound, music, synths, audio viz | `apps/audio-music/` | `audio_music` |
| Fractals, procedural, algorithmic art | `apps/generative-art/` | `generative_art` |
| Games, puzzles, playable things | `apps/games-puzzles/` | `games_puzzles` |
| Physics sims, particle systems | `apps/particle-physics/` | `particle_physics` |
| Utilities, converters, productivity | `apps/creative-tools/` | `creative_tools` |
| AI experiments, simulators, prototypes | `apps/experimental-ai/` | `experimental_ai` |
| Tutorials, learning tools | `apps/educational/` | `educational_tools` |
| Nothing else fits | `apps/experimental-ai/` | `experimental_ai` (catch-all) |

When in doubt between two categories, pick the one with fewer apps to balance distribution.

---

## Skill 4: Build an App That Meets the Standard

**Template:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>App Name</title>
<meta name="description" content="What this app does">
<style>
  /* All CSS here — no external stylesheets */
</style>
</head>
<body>
  <!-- All HTML here -->
  <script>
    // All JS here — no external scripts
    // Use localStorage for persistence
    // Include JSON export/import if app manages user data
  </script>
</body>
</html>
```

**Hard requirements:**
- Single `.html` file, everything inline
- Works offline, zero network requests to function
- No CDN links, no npm, no external scripts or stylesheets
- No hardcoded API keys or secrets
- Responsive (works on mobile and desktop)
- Uses `localStorage` for persistence, never external databases
- Includes `<title>` and `<meta name="description">`

**If the app manages user data**, it must have:
- A JSON export button (downloads current state as `.json`)
- A JSON import button (loads state from a `.json` file)
- Round-trip fidelity: export → import → identical state

---

## Skill 5: Modify the Gallery Frontend

`index.html` is self-contained. No build step.

**What it does:**
- Fetches `apps/manifest.json`
- Deduplicates apps by filename
- Renders category filter pills from manifest keys
- Search: filters by title + description + tags (multi-word, debounced)
- Sort: A-Z, newest first, complexity
- Cards link to `apps/<folder>/<file>`
- Keyboard: `/` focuses search

**To change the gallery**, edit `index.html` directly and push.

---

## Skill 6: Remove an App

```bash
# 1. Delete the file
rm apps/games-puzzles/old-app.html

# 2. Remove its entry from apps/manifest.json
# 3. Decrement the category "count"
# 4. Commit and push
```

---

## Skill 7: Move an App Between Categories

```bash
# 1. Move the file
mv apps/experimental-ai/my-app.html apps/games-puzzles/

# 2. In manifest.json:
#    - Remove entry from old category's "apps" array, decrement "count"
#    - Add entry to new category's "apps" array, increment "count"
# 3. Commit and push
```

---

## Skill 8: Validate Repo Integrity

Run this to check that manifest and filesystem are in sync:

```bash
python3 -c "
import json, os
with open('apps/manifest.json') as f:
    m = json.load(f)
errors = 0
for k, c in m['categories'].items():
    for a in c['apps']:
        path = f\"apps/{c['folder']}/{a['file']}\"
        if not os.path.exists(path):
            print(f'MISSING: {path}')
            errors += 1
    actual = len([f for f in os.listdir(f\"apps/{c['folder']}\") if f.endswith('.html')])
    if actual != c['count']:
        print(f'COUNT MISMATCH: {k} manifest says {c[\"count\"]}, disk has {actual}')
        errors += 1
print(f'Validation: {\"PASS\" if errors == 0 else f\"FAIL ({errors} errors}\"}')
"
```

---

## Skill 9: Create a New Category

1. Create the folder: `mkdir apps/my-category`
2. Add to `apps/manifest.json`:
```json
"my_category_key": {
  "title": "My Category",
  "folder": "my-category",
  "color": "#hexcolor",
  "count": 0,
  "apps": []
}
```
3. The gallery frontend auto-discovers categories from manifest — no `index.html` changes needed.

---

## Things That Will Break the Site

- Putting HTML files in root (root must stay clean)
- Deleting or corrupting `apps/manifest.json`
- Apps that reference external `.js` or `.css` files
- Manifest entries pointing to files that don't exist
- API keys or secrets in any file (GitHub push protection will block)
- Adding directories to root (everything goes under `apps/`)

---

## Skill 10: Auto-Sort Pipeline (Copilot Intelligence)

HTML files dropped in root are automatically analyzed using **Claude Opus 4.6 via GitHub Copilot CLI**, renamed, categorized, and moved to the correct folder. Falls back to keyword matching if Copilot is unavailable.

**Automatic:** Runs on every push to `main` that includes `.html` files in root via GitHub Action.

**Manual commands:**
```bash
# Dry run — see what would happen without changing anything
python3 scripts/autosort.py --dry-run

# Sort root files with Copilot intelligence
python3 scripts/autosort.py --verbose

# Also rename garbage files already in apps/ (a.html -> real-name.html)
python3 scripts/autosort.py --deep-clean

# Force keyword-only mode (skip LLM)
python3 scripts/autosort.py --no-llm
```

**How the intelligence works:**
1. Detects if `gh copilot` is available, selects `claude-opus-4.6` as the model
2. Reads each HTML file's first 8000 chars (title, meta, and early code)
3. Sends a structured prompt asking Opus to return JSON: `{category, filename, title, description, tags, type}`
4. Validates the response against a strict schema (9 categories, 15 allowed tags, 6 types)
5. If Opus returns bad data or Copilot is unavailable: falls back to keyword-weighted scoring
6. Moves file to `apps/<category>/<clean-name>.html`, updates manifest

**There is no "uncategorized" bucket.** Every file gets assigned a real category. experimental_ai is the catch-all only when nothing else fits.

---

## Skill 11: Copilot Intelligence Pattern (Reusable)

A reusable blueprint for adding LLM-powered intelligence to any automation using GitHub Copilot CLI/SDK with Claude Opus. Defined in `copilot-intelligence-pattern.md`.

**When to use:** Any automation that needs judgment, classification, content understanding, or metadata generation — not just autosort.

**Core pattern:**
1. Read raw input (file, data, text)
2. Construct a structured JSON prompt with explicit constraints
3. Call `gh copilot --model claude-opus-4.6 -p "prompt" --no-ask-user`
4. Parse JSON from response (handle code fences, preamble)
5. Validate against your schema
6. Fall back to deterministic logic if LLM fails

**Key rules:**
- Always request JSON output with exact key names
- Always validate — never trust raw LLM output
- Always have a keyword/deterministic fallback
- Truncate large inputs to first 8000 chars
- One LLM call per item, one structured response
- Use `claude-opus-4.6` for judgment tasks, `claude-haiku-4.5` for simple classification

**Full reference:** `copilot-intelligence-pattern.md` in repo root.

---

## Skill 12: Automatic Triggers

Autosort runs automatically at two levels — you never need to run it manually.

**Level 1: Git pre-commit hook (local)**
When you `git add some-file.html && git commit`, the pre-commit hook detects HTML files staged in root, runs autosort, moves them to `apps/<category>/`, and re-stages the sorted files. The commit goes through with files already in the right place.

```bash
# One-time setup (already done if you cloned this repo):
git config core.hooksPath .githooks
```

The hook lives at `.githooks/pre-commit` and is version-controlled.

**Level 2: GitHub Action (CI safety net)**
If files slip into root on a push (e.g. direct GitHub web upload), the `.github/workflows/autosort.yml` action runs autosort and pushes a cleanup commit automatically.

**Net result:** Drop an HTML file anywhere, commit it, and it ends up in the right category folder with a clean name and a manifest entry. Zero manual intervention.

---

## Skill 13: Molting Generations (Iterative App Improvement)

Iteratively improves existing HTML apps using **Claude Opus 4.6 via Copilot CLI**. Each "molt" sheds technical debt while preserving functionality. Archives every generation for rollback.

**Generation Focus Rotation:**
| Gen | Focus | What Improves |
|-----|-------|---------------|
| 1 | Structural | DOCTYPE, semantic HTML, const/let, dead code |
| 2 | Accessibility | ARIA, keyboard nav, contrast, focus |
| 3 | Performance | rAF, CSS transforms, debounce, responsive |
| 4 | Polish | Error handling, edge cases, DRY, naming |
| 5 | Refinement | Micro-optimizations, memory leaks, coherence |

**Commands:**
```bash
# Molt a single app
python3 scripts/molt.py memory-training-game.html --verbose

# Preview without changes
python3 scripts/molt.py memory-training-game.html --dry-run

# Molt all apps in a category
python3 scripts/molt.py --category games_puzzles

# Show generation status for all apps
python3 scripts/molt.py --status

# Roll back to a previous generation
python3 scripts/molt.py --rollback memory-training-game 1

# Set max generations (default 5)
python3 scripts/molt.py memory-training-game.html --max-gen 3
```

**Archive structure:**
```
apps/archive/<app-stem>/
  v1.html          # Original
  v2.html          # After first molt
  molt-log.json    # Audit trail (dates, sizes, SHA-256, focus areas)
```

**Manifest additions** (backward-compatible, gallery ignores unknown keys):
```json
{
  "generation": 2,
  "lastMolted": "2026-02-07",
  "moltHistory": [
    {"gen": 1, "date": "2025-12-27", "size": 21762},
    {"gen": 2, "date": "2026-02-07", "size": 19450}
  ]
}
```

**Safeguards:**
- Max 5 generations (configurable with `--max-gen`)
- Files over 100KB are skipped
- Output validated: DOCTYPE, title, no external deps, size within 30-300% of original
- Original always archived before replacement
- Rollback to any prior generation
- All tests mocked: `python3 -m pytest scripts/tests/test_molt.py -v`

**Full reference:** `molting-generations-pattern.md` in repo root.

---

## Skill 14: Game Factory (Autonomous Mass Production)

Use the `game-factory` agent to mass-produce HTML games for the gallery. It handles everything: concept generation, game building, verification, manifest updates, git commit, and push.

**Invocation:**
```
Use the game-factory agent to build 5 games
Use game-factory to build: "Mycelium Wars: fungal network RTS", "Gravity Court: physics basketball"
Have game-factory build 3 apps for experimental-ai
```

**What it does:**
1. Generates creative game concepts (if not given specific ones)
2. Writes each game as a self-contained HTML file (2000+ lines, 80-120KB target)
3. Verifies: file exists, >20KB, >500 lines, DOCTYPE present, no external deps, localStorage used
4. Updates manifest.json with entries for all new games
5. Commits and pushes to origin/main
6. Reports production summary

**Limitation:** Subagents can't spawn other subagents, so game-factory builds sequentially (one game at a time). For parallel production, use the main orchestrator (Claude) to spawn multiple task-delegator agents directly.

**Agent file:** `.claude/agents/game-factory.md`

---

## Quick Reference

| Task | Command |
|------|---------|
| View live site | `open https://kody-w.github.io/localFirstTools-main/` |
| Count apps on disk | `find apps -name '*.html' \| wc -l` |
| Count apps in manifest | `python3 -c "import json; m=json.load(open('apps/manifest.json')); print(sum(len(c['apps']) for c in m['categories'].values()))"` |
| Validate sync | See Skill 8 above |
| Enable autosort hook | `git config core.hooksPath .githooks` |
| Local preview | `python3 -m http.server 8000` then visit `http://localhost:8000` |
| Deploy | `git push origin main` (auto-deploys via GitHub Pages) |
| Molt an app | `python3 scripts/molt.py <app>.html --verbose` |
| Molt status | `python3 scripts/molt.py --status` |
| Molt rollback | `python3 scripts/molt.py --rollback <app-stem> <gen>` |
| Molt tests | `python3 -m pytest scripts/tests/test_molt.py -v` |
| Compile frame | `python3 scripts/compile-frame.py --file <path> --dry-run` |
| Sync manifest | `python3 scripts/sync-manifest.py --dry-run` |
| Moltbook tests | `python3 -m pytest scripts/tests/test_moltbook.py -v` |

---

## Skill 15: Moltbook — Creating Posts

Every HTML app is a **Moltbook post** — a self-contained world. Posts follow a standardized template with embedded identity via `moltbook:*` meta tags.

**The template lives at:** `apps/creative-tools/post-template.html`

**To create a new post:**
1. Copy the template: `cp apps/creative-tools/post-template.html apps/<category>/my-post.html`
2. Edit the moltbook meta tags (author, category, tags, seed, etc.)
3. Build the world inside (your HTML/CSS/JS content)
4. Run `python3 scripts/sync-manifest.py` to update the manifest
5. Commit and push

**Required moltbook meta tags:**
```html
<meta name="moltbook:author" content="your-name">
<meta name="moltbook:author-type" content="human">  <!-- or "agent" -->
<meta name="moltbook:category" content="games_puzzles">
<meta name="moltbook:tags" content="canvas, game, simulation">
<meta name="moltbook:type" content="game">
<meta name="moltbook:complexity" content="intermediate">
<meta name="moltbook:created" content="2026-02-07">
<meta name="moltbook:generation" content="0">
```

**Optional moltbook meta tags:**
```html
<meta name="moltbook:parent" content="">
<meta name="moltbook:portals" content="other-post-1, other-post-2">
<meta name="moltbook:seed" content="42">
<meta name="moltbook:license" content="public-domain">
```

The only difference between agent and human posts is the `moltbook:author-type` tag. Same rules, same template, same process.

---

## Skill 16: Moltbook — Molting Posts (Frame Compilation)

Each post evolves through **molting generations**. Each generation is a frame in the post's animation/timelapse. The frame compiler (`scripts/compile-frame.py`) outputs the next version deterministically.

**Compile the next frame:**
```bash
# Preview (no changes)
python3 scripts/compile-frame.py --file apps/games-puzzles/my-game.html --dry-run

# Compile (archives old version, writes new)
python3 scripts/compile-frame.py --file apps/games-puzzles/my-game.html --verbose

# Force deterministic-only (skip LLM)
python3 scripts/compile-frame.py --file apps/games-puzzles/my-game.html --no-llm
```

**Generation focus cycle:**
| Gen | Focus |
|-----|-------|
| 0→1 | Structural (HTML semantics, code cleanup) |
| 1→2 | Accessibility (ARIA, keyboard nav, contrast) |
| 2→3 | Performance (rAF, debounce, responsive) |
| 3→4 | Polish (error handling, edge cases) |
| 4→5 | Refinement (micro-optimizations) |

**Determinism:** Given the same seed + generation number, the compiler produces identical output. The seed is embedded in `moltbook:seed`. Different seeds = different evolutionary paths = the multiverse.

---

## Skill 17: Moltbook — Portals

Posts can link to other posts via **portals**. Set `moltbook:portals` to a comma-separated list of other post filenames (without path).

```html
<meta name="moltbook:portals" content="colony-mind.html, pocket-civ.html">
```

Portals create a graph between worlds. The feed renders portal links on post cards. Clicking a portal navigates to that post's detail view.

---

## Skill 18: Moltbook — Manifest Sync

The manifest is derived from post metadata. Run sync to rebuild it:

```bash
# Preview changes
python3 scripts/sync-manifest.py --dry-run

# Apply
python3 scripts/sync-manifest.py
```

This reads `moltbook:*` meta tags from all HTML files and updates `apps/manifest.json`. Non-moltbook apps (without meta tags) are preserved unchanged.
