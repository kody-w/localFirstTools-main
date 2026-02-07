# RappterZoo Operations — Full Context Handoff

You are operating on the **RappterZoo** codebase — an autonomous game-making social network powered by the Molter Engine. This file gives you everything you need to work on this project without asking the user to explain the system.

---

## What This Is

A GitHub Pages static site at `https://kody-w.github.io/localFirstTools-main/` serving 530+ self-contained HTML apps (games, tools, visualizers, simulations). Every app is a single `.html` file — zero external deps, zero build process.

The frontend (`index.html`) is a Reddit-style feed with:
- Threaded comments, star ratings, activity feed
- 250 simulated NPC players (real humans can "take over" an NPC)
- Clickable player profiles showing comment/rating/activity history
- Timelapse viewer for molted (evolved) apps
- Sort modes: Hot, New, Rising, Top Rated, A-Z

---

## Repository Map

```
/
  index.html                 → Gallery frontend (single file, self-contained)
  CLAUDE.md                  → Repo rules (read this too)
  skills.md                  → External agent instructions (for sharing)
  apps/
    manifest.json            → Source of truth for all app metadata
    community.json           → Players, comments, ratings, activity (~3MB)
    rankings.json            → Quality scores (6-dimension, 100pts)
    molter-state.json        → Engine frame counter + history
    3d-immersive/            → WebGL, Three.js, 3D worlds
    audio-music/             → Synthesizers, DAWs, music tools
    creative-tools/          → Productivity, utilities
    educational/             → Tutorials, learning tools
    experimental-ai/         → AI experiments (catch-all category)
    games-puzzles/           → Games, puzzles, interactive play
    generative-art/          → Algorithmic art, procedural generation
    particle-physics/        → Physics sims, particle systems
    visual-art/              → Visual effects, design tools
  scripts/
    rank_games.py            → Score all apps (6 dimensions), write rankings.json
    generate_community.py    → Generate players/comments/ratings/activity
    autosort.py              → Auto-categorize HTML files dropped in root
    molt.py                  → Molt single app via Copilot CLI
    compile-frame.py         → Deterministic frame compiler
  .claude/
    agents/
      molter-engine.md       → Core autonomous loop (OBSERVE→DECIDE→CREATE→MOLT→SCORE→RANK→SOCIALIZE→PUBLISH)
      game-factory.md        → Mass game production
      data-slosh.md          → Quality audit + rewriting
      buzzsaw-v3.md          → Parallel production (deprecated — use game-factory)
    commands/
      rappterzoo.md          → This file
```

---

## Critical Commands

### Score all apps
```bash
python3 scripts/rank_games.py --verbose          # Score + print
python3 scripts/rank_games.py --push             # Score + commit + push
```

### Regenerate community data
```bash
python3 scripts/generate_community.py --verbose  # Generate community.json
python3 scripts/generate_community.py --push     # Generate + commit + push
```

### Validate manifest
```bash
python3 -c "import json; json.load(open('apps/manifest.json')); print('VALID')"
```

### Count apps
```bash
find apps -name '*.html' -not -path '*/archive/*' | wc -l
```

### Find empty/broken files
```bash
find apps -name '*.html' -empty
```

### Local preview
```bash
python3 -m http.server 8000
```

---

## How to Create a New Game

1. Write a self-contained HTML file (all CSS in `<style>`, all JS in `<script>`, zero external deps)
2. Place it in `apps/<category>/your-game.html`
3. Add entry to `apps/manifest.json` in the correct category's `apps` array
4. Increment the category's `count` field
5. Validate: `python3 -c "import json; json.load(open('apps/manifest.json')); print('VALID')"`
6. Commit and push

### Manifest entry format
```json
{
  "title": "Game Title",
  "file": "game-filename.html",
  "description": "One-line description",
  "tags": ["canvas", "game", "physics"],
  "complexity": "advanced",
  "type": "game",
  "featured": false,
  "created": "2026-02-07"
}
```

### Category keys → folder mapping
| Key | Folder |
|-----|--------|
| `games_puzzles` | `games-puzzles` |
| `visual_art` | `visual-art` |
| `3d_immersive` | `3d-immersive` |
| `audio_music` | `audio-music` |
| `generative_art` | `generative-art` |
| `particle_physics` | `particle-physics` |
| `creative_tools` | `creative-tools` |
| `experimental_ai` | `experimental-ai` |
| `educational_tools` | `educational` |

---

## How to Mass-Produce Games

Use the **two-layer pattern** (proven reliable for 128+ games):

1. From the main orchestrator, spawn multiple `task-delegator` subagents in parallel
2. Each subagent writes ONE complete game directly using the Write tool
3. After all complete, update manifest.json, validate, commit, push

```
Orchestrator (you)
  ├─ Task(task-delegator): Write game A → apps/games-puzzles/game-a.html
  ├─ Task(task-delegator): Write game B → apps/games-puzzles/game-b.html
  ├─ Task(task-delegator): Write game C → apps/games-puzzles/game-c.html
  └─ ... (max 6 parallel)
```

**CRITICAL**: Do NOT use `gh copilot -p` for code generation — it enters agent mode and gets permission denied. Subagents MUST write files directly with the Write tool.

---

## Scoring System (6 Dimensions, 100 Points)

| Dimension | Pts | Key signals `rank_games.py` looks for |
|---|---|---|
| Structural | 15 | DOCTYPE, viewport meta, title, inline CSS/JS, no external deps |
| Scale | 10 | Line count (1500+ = full marks), file size (40KB+) |
| Systems | 20 | canvas, requestAnimationFrame, AudioContext, localStorage, Math.random/procedural, addEventListener, collision/intersect, particle, state/setState, class keyword |
| Completeness | 15 | pause, game.over, score/points, level/stage, title.screen/menu, HUD/health, ending, tutorial |
| Playability | 25 | screen.shake, hit.feedback/flash, combo, difficulty, enemy.AI, boss, 5+ entity types, 3+ abilities, touch, keyup+keydown, restart, highscore |
| Polish | 15 | @keyframes/transition, gradient, box-shadow, @media/responsive, 5+ hex colors, particle/glow/blur effects |

### Grade thresholds
S: 90+ | A: 80+ | B: 65+ | C: 50+ | D: 35+ | F: <35

---

## Comment System Architecture

`scripts/generate_community.py` builds comments that react to each game's actual content:

- **TAG_OBSERVATIONS**: Dict mapping each tag (canvas, physics, roguelike, etc.) to 6 unique observations
- **DESC_REACTIONS**: Dict mapping description keywords to specific reactions
- **COMPLEXITY_REACTIONS** / **TYPE_REACTIONS**: Pool per complexity/type level
- **`build_comment_for_app()`**: Composes compound comments by combining tag observations + title callouts + description reactions. Never uses standalone generic text.
- **`build_reply_for_comment()`**: Parses the parent comment text for topics (physics, sound, depth, etc.) and generates title-specific contextual replies.
- **MODERATOR_COMMENTS**: ArcadeKeeper bot uses actual game data (score, tech stack, generation) in structured review comments.

Current uniqueness: **87%+** across 6,000+ comments. Every comment and reply includes the game title.

---

## Frontend Architecture (`index.html`)

Single self-contained HTML file (884 lines). Key systems:

- **Data loading**: Fetches `manifest.json`, `archive/manifest.json`, `community.json` on load
- **State**: `apps[]`, `filtered[]`, `community{}`, `cat`, `query`, `sortMode`, `myPlayer`
- **NPC Takeover**: `showJoinOverlay()` — player picks an NPC, identity stored in `localStorage('rappterzoo-player')`
- **Player Profiles**: `openProfile(username)` — aggregates comments/ratings/activity across all games, 3-tab overlay
- **Detail Modal**: `openDetail(app)` — timelapse viewer + threaded comments + star rating
- **Comments**: `renderComments(app)` / `renderThread(c, depth)` — nested Reddit-style threads, real-time user replies stored in `localStorage('rappterzoo-user-comments')`
- **Ratings**: `setMyRating(stem, val)` — stored in `localStorage('rappterzoo-ratings')`
- **Activity Feed**: `renderActivityFeed()` — sidebar with recent events from community.json

### localStorage keys
| Key | Content |
|-----|---------|
| `rappterzoo-player` | Player identity JSON (after NPC takeover) |
| `rappterzoo-ratings` | `{stem: stars}` map of user's ratings |
| `rappterzoo-user-comments` | `{stem: [comment]}` map of user's comments |

---

## The Molter Engine

Defined at `.claude/agents/molter-engine.md`. Each invocation = one "frame":

```
OBSERVE → Read state, scores, community metrics
DECIDE  → What does the ecosystem need? (decision matrix)
CREATE  → Spawn task-delegator subagents to build games (parallel)
MOLT    → Improve lowest-scoring games
SCORE   → python3 scripts/rank_games.py
RANK    → Publish updated rankings
SOCIALIZE → python3 scripts/generate_community.py
PUBLISH → git commit + push
LOG     → Update apps/molter-state.json
```

State file: `apps/molter-state.json` (frame counter, history, config)

---

## Common Pitfalls (Learned the Hard Way)

1. **`gh copilot -p` does NOT generate raw code** — it enters agent mode, gets permission denied. Always use Write tool directly in subagents.
2. **Nested f-strings with quotes fail** — use string concatenation: `"prefix" + var + "suffix"` instead of `f"prefix{f'{inner}'}"`.
3. **HTMLParser `_is_redirect` name-mangling** — use plain `is_redirect` attribute.
4. **Always validate manifest.json after editing** — one bad comma breaks the entire site.
5. **community.json is ~3MB** — regenerate with `scripts/generate_community.py`, don't edit by hand.
6. **Root is sacred** — never put HTML files in the repo root. Only `index.html`, `README.md`, `CLAUDE.md`, `.gitignore`.
7. **Comment uniqueness** — old system had 3.7% uniqueness from static template pools. New system uses tag-based reactions achieving 87%+. Never use template-based comments.
8. **Empty files from failed subagents** — check with `find apps -name '*.html' -empty` and delete them (they won't be in manifest).
9. **Max 6 parallel subagents** — more causes resource contention.
10. **Git push = live deploy** — GitHub Pages auto-deploys from main. No CI config needed.

---

## Deployment

Push to `main` branch. GitHub Pages auto-deploys. That's it. No build step, no CI/CD config, no package manager.

```bash
git add <files> && git commit -m "message" && git push origin main
```

Live in ~60 seconds at `https://kody-w.github.io/localFirstTools-main/`
