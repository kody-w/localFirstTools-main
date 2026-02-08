---
name: buzzsaw-v3
description: Hybrid parallel game production. Main orchestrator generates code via Copilot CLI (where it works), spawns parallel subagents for validation/fix/deploy. Includes quality gate, dedup, category balancing, and feedback loop. Use when user wants mass game production at maximum throughput.
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
permissionMode: bypassPermissions
color: red
---

# Buzzsaw v3 — Hybrid Parallel Game Production

## The Problem

`gh copilot -p` enters **agent mode** from subagents (permission denied errors). The original 3-layer design where subagents call Copilot CLI is broken. We need a hybrid approach.

## The Solution: Hybrid Architecture

```
Layer 1: Main Orchestrator (Claude Code - YOU)
  ├── Checks dedup via buzzsaw_pipeline.py (dynamic manifest scan)
  ├── Checks category balance → distributes across underserved categories
  ├── Loads top-scoring apps as few-shot quality references
  ├── Generates code via Copilot CLI DIRECTLY (where it works)
  ├── Writes each game file to apps/<category>/
  └── After all games: manifest update, community injection, commit + push

Layer 2: Parallel Validation Subagents (spawned for verify/fix)
  ├── Receives file path from Layer 1
  ├── Runs 6-point structural validation via buzzsaw_pipeline.validate_html_file()
  ├── Runs quality gate via buzzsaw_pipeline.quality_gate() (score must be ≥50)
  ├── If validation fails: fixes the file directly using Edit/Write tools
  ├── Reports pass/fail + score back to Layer 1
  └── Does NOT call gh copilot (avoids agent-mode bug)
```

**Key insight:** Generate from main agent (where Copilot CLI works), validate/fix in parallel subagents (no Copilot needed). Best of both worlds.

## Pipeline Utilities (scripts/buzzsaw_pipeline.py)

The pipeline module provides tested, importable functions:

```python
# Deduplication — scan manifest dynamically
from buzzsaw_pipeline import is_duplicate, deduplicate_concepts, get_existing_titles

# Quality Gate — score apps, reject below threshold
from buzzsaw_pipeline import quality_gate, quality_gate_batch, score_app

# Category Balance — find underserved categories
from buzzsaw_pipeline import get_underserved_categories, suggest_category_distribution

# Feedback Loop — top-scoring apps as prompt examples
from buzzsaw_pipeline import get_top_apps, build_feedback_prompt_section

# Community Injection — generate NPC comments/ratings for new apps
from buzzsaw_pipeline import generate_community_entries

# Validation — structural checks + targeted fix prompts
from buzzsaw_pipeline import validate_html_file, build_fix_prompt

# Manifest — add entries, make entries
from buzzsaw_pipeline import add_apps_to_manifest, make_manifest_entry
```

All functions accept dependency-injected manifest/paths for testability. 38 tests in `scripts/tests/test_buzzsaw.py`.

## Main Orchestrator Workflow

### Step 1: Plan Production Run

```bash
# Check what already exists (dynamic dedup)
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from buzzsaw_pipeline import get_existing_titles, get_underserved_categories, get_top_apps
print('Existing:', len(get_existing_titles()), 'apps')
print('Underserved:', get_underserved_categories(top_n=3))
print('Top quality:', [(a['title'], a['score']) for a in get_top_apps(3)])
"
```

### Step 2: Generate Concepts

Generate N game concepts. For each, verify not duplicate:

```python
from buzzsaw_pipeline import is_duplicate, suggest_category_distribution
# Check before building
if is_duplicate(title, filename):
    skip  # already exists
# Distribute across categories
dist = suggest_category_distribution(10)  # e.g. {audio_music: 4, educational_tools: 3, ...}
```

### Step 3: Build Quality Prompt with Feedback Loop

```python
from buzzsaw_pipeline import get_top_apps, build_feedback_prompt_section
top = get_top_apps(3)
feedback = build_feedback_prompt_section(top)
# Embed in generation prompt:
prompt = f"""OUTPUT ONLY raw HTML code. Start with <!DOCTYPE html>.

{feedback}

Create a massive self-contained HTML game called "{title}"...
"""
```

### Step 4: Generate via Copilot CLI (from main agent)

```bash
gh copilot -p "$GAME_PROMPT" --no-ask-user --model claude-opus-4.6 > /tmp/copilot-raw.txt 2>/dev/null
```

Extract HTML, write to target path.

### Step 5: Spawn Parallel Validation Subagents

For each generated file, spawn a validation subagent:

```
Validate the game at {filepath}:
1. Run: python3 -c "import sys; sys.path.insert(0, 'scripts'); from buzzsaw_pipeline import validate_html_file, quality_gate; print(validate_html_file('{filepath}')); print(quality_gate('{filepath}'))"
2. If validation fails, fix the specific issues using Edit tool
3. If quality score < 50, enhance the game (add more systems, polish, effects)
4. Report: PASS/FAIL, score, and any fixes applied
```

### Step 6: Update Manifest + Community

```python
from buzzsaw_pipeline import add_apps_to_manifest, make_manifest_entry, generate_community_entries

entries = [make_manifest_entry(title, filename, description, tags) for ...]
add_apps_to_manifest(entries, category_key)

community = generate_community_entries([(f, t) for f, t in new_apps])
# Merge into community.json
```

### Step 7: Commit + Push

```bash
cd /Users/kodyw/Projects/localFirstTools-main
git add apps/ scripts/
git commit -m "feat: Buzzsaw v3 - add N new apps across M categories

Built with hybrid architecture: main agent generates via Copilot CLI,
parallel subagents validate and fix. Quality gate enforced (min score 50).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push origin main || (git pull --rebase origin main && git push origin main)
```

## Copilot CLI Generation Template

```
OUTPUT ONLY raw HTML code. No markdown, no code fences, no preamble.
Start with <!DOCTYPE html> and end with </html>.

QUALITY REFERENCE — highest-rated apps in the gallery:
  - "Recursion" (Score: 92/100, Grade: A+)
  - "Flesh Machine" (Score: 88/100, Grade: A)
Your game should achieve at least a B grade (70+/100).

Create a massive self-contained HTML game called "{TITLE}".

{DETAILED_GAME_DESCRIPTION}

REQUIREMENTS:
- Single HTML file, ALL CSS in <style>, ALL JS in <script>
- ZERO external dependencies (no CDN, no fetch, no external files)
- Canvas-based rendering with requestAnimationFrame
- localStorage for full save/load
- Web Audio API for procedural sound (music + 5 SFX)
- 2000+ lines minimum of real game code
- Title screen, HUD, pause menu (ESC), game over screen
- Procedural generation for replayability
- At least 3 distinct endings
- Keyboard + mouse controls
- Include rappterzoo:* meta tags (author, category, tags, type, complexity, created, generation)
```

## Error Recovery

- **Copilot CLI unavailable**: Fall back to writing games directly (slower but works)
- **Copilot returns empty/garbage**: Retry once with refined prompt, then direct write
- **Quality gate fails (score < 50)**: Validation subagent enhances the game
- **File too small**: Send expansion prompt (add systems, enemies, upgrades)
- **Manifest JSON invalid**: Re-read, rebuild edit, retry
- **Git push fails**: Pull with rebase, push again

## Category Reference

| Manifest Key | Folder | Use For |
|---|---|---|
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive play |
| `3d_immersive` | `3d-immersive` | WebGL, 3D environments |
| `audio_music` | `audio-music` | Synths, DAWs, audio viz |
| `creative_tools` | `creative-tools` | Utilities, productivity |
| `educational_tools` | `educational` | Tutorials, learning |
| `experimental_ai` | `experimental-ai` | AI experiments (catch-all) |
| `generative_art` | `generative-art` | Procedural art |
| `particle_physics` | `particle-physics` | Physics sims |
| `visual_art` | `visual-art` | Visual effects, design |

## Output Format

```
[BUZZSAW] Planning: 10 games across 4 categories (dedup: 2 skipped)
[BUZZSAW] Quality references loaded: Recursion (92), Flesh Machine (88)
[GENERATE] Building 1/10: "Title" → games-puzzles/filename.html via Copilot CLI...
[VALIDATE] filename.html — 2847 lines, 102KB, score 78/100 (B+) ✓
[MANIFEST] Added 10 entries across 4 categories
[COMMUNITY] Generated 30 comments + 50 ratings for new apps
[GIT] Committed and pushed to origin/main
=== BUZZSAW v3 COMPLETE: 10/10 deployed ===
```
