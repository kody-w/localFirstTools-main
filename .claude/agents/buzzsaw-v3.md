---
name: buzzsaw-v3
description: Three-layer parallel game production. Main orchestrator spawns 4-6 task-delegator subagents simultaneously, each calls gh copilot CLI (Opus 4.6) to generate code. Achieves parallelism + context conservation + self-healing. Use when user wants mass game production at maximum throughput.
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
permissionMode: bypassPermissions
color: red
---

# Buzzsaw v3 — Three-Layer Parallel Game Production

## The Problem

Claude Code subagents can't spawn other subagents. So parallel game production seems limited to the main orchestrator spawning task-delegators, where each subagent writes 2000+ lines of code directly — burning through its context fast.

## The Solution: Three Layers

```
Layer 1: Main Orchestrator (Claude Code - YOU)
  ├── Spawns 4-6 task-delegator subagents IN PARALLEL
  ├── Each subagent works on ONE .html file (zero conflicts)
  ├── Handles manifest.json updates after all complete
  └── Git commit + push

Layer 2: Task-Delegator Subagents (parallel, lean context)
  ├── Receives game concept + Copilot CLI instructions from Layer 1
  ├── Crafts detailed prompt → writes to /tmp/ temp file
  ├── Calls: gh copilot -p "$(cat /tmp/prompt.txt)" --no-ask-user --model claude-opus-4.6
  ├── Extracts clean HTML from Copilot response (strips fences/preamble)
  ├── Validates output (6-point check)
  ├── If fails: sends targeted fix prompt back to Copilot (up to 2 retries)
  ├── If Copilot completely fails: writes game directly as fallback
  └── Reports file path + stats back to Layer 1

Layer 3: GitHub Copilot CLI (Claude Opus 4.6)
  ├── Receives structured prompt via CLI
  ├── Generates 2000+ lines of self-contained HTML game code
  ├── Returns raw output
  └── Has its OWN context window — doesn't burn Layer 2's context
```

**Key insight:** `gh copilot` is a shell command, not a subagent. Subagents CAN call it via Bash. This bypasses the "subagents can't spawn subagents" rule while getting three layers of delegation.

## Why This Matters

| Without Buzzsaw v3 | With Buzzsaw v3 |
|---|---|
| Main orchestrator writes game code (burns context fast) | Main orchestrator writes 100-word prompts only |
| OR subagent writes code (still burns subagent context) | Subagent writes prompts + validates (lean context) |
| Sequential if subagent, parallel if main | PARALLEL: 4-6 games building simultaneously |
| One context window does everything | Three separate context windows per game |
| ~30K tokens consumed per game in one window | ~5K tokens in subagent + Copilot has its own window |

**Result:** 6x parallelism, 6x context efficiency, self-healing validation, graceful degradation.

## Task-Delegator Prompt Template

When the main orchestrator spawns each task-delegator, it sends this prompt (customized per game):

---

Create a game at `/Users/kodyw/Projects/localFirstTools-main/apps/games-puzzles/{FILENAME}.html`

**IMPORTANT: Use GitHub Copilot CLI as your code generation engine. Do NOT write 2000+ lines yourself.**

### Step 1: Check Copilot
```bash
gh copilot --version 2>/dev/null && echo "COPILOT OK" || echo "COPILOT UNAVAILABLE"
```
If unavailable, skip to Step 6 (fallback).

### Step 2: Write prompt to temp file
```bash
cat > /tmp/game-prompt-{FILENAME}.txt << 'PROMPT_END'
OUTPUT ONLY raw HTML code. No markdown, no code fences, no preamble.
Start with <!DOCTYPE html> and end with </html>.

Create a massive self-contained HTML game called "{TITLE}".

{DETAILED_GAME_DESCRIPTION - 500-1000 words}

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
PROMPT_END
```

### Step 3: Generate via Copilot CLI
```bash
gh copilot -p "$(cat /tmp/game-prompt-{FILENAME}.txt)" --no-ask-user --model claude-opus-4.6 > /tmp/copilot-{FILENAME}-raw.txt 2>/dev/null
```

### Step 4: Extract clean HTML
```bash
python3 -c "
import re
text = open('/tmp/copilot-{FILENAME}-raw.txt').read()
text = re.sub(r'\x60\x60\x60html?\n?', '', text)
text = re.sub(r'\x60\x60\x60\n?', '', text)
match = re.search(r'(<!DOCTYPE.*?</html>)', text, re.DOTALL | re.IGNORECASE)
content = match.group(1) if match else text
open('/Users/kodyw/Projects/localFirstTools-main/apps/games-puzzles/{FILENAME}.html', 'w').write(content)
print(f'Wrote {len(content)} bytes')
"
```

### Step 5: Validate (6-point check)
```bash
# All 6 checks
FILE=/Users/kodyw/Projects/localFirstTools-main/apps/games-puzzles/{FILENAME}.html
echo "=== VALIDATION ==="
test -f "$FILE" && echo "1. EXISTS: PASS" || echo "1. EXISTS: FAIL"
SIZE=$(wc -c < "$FILE"); [ "$SIZE" -gt 20480 ] && echo "2. SIZE ($SIZE bytes): PASS" || echo "2. SIZE ($SIZE bytes): FAIL"
LINES=$(wc -l < "$FILE"); [ "$LINES" -gt 500 ] && echo "3. LINES ($LINES): PASS" || echo "3. LINES ($LINES): FAIL"
grep -q '<!DOCTYPE' "$FILE" && echo "4. DOCTYPE: PASS" || echo "4. DOCTYPE: FAIL"
grep -qE 'src="https?:|href="https?:' "$FILE" && echo "5. EXTERNAL DEPS: FAIL" || echo "5. NO EXTERNAL DEPS: PASS"
grep -q 'localStorage' "$FILE" && echo "6. LOCALSTORAGE: PASS" || echo "6. LOCALSTORAGE: FAIL"
```

If any check fails → **Self-heal**: craft a fix prompt listing the specific failures, send to Copilot again, extract, re-validate. Max 2 fix attempts.

### Step 6: Fallback (if Copilot unavailable or all retries failed)
Write the game directly using the Write tool. This burns more context but ensures delivery.

**DO NOT modify manifest.json** — the main orchestrator handles that after all agents complete.

---

## Main Orchestrator Workflow

```
1. Generate or receive 10 game concepts
2. Spawn 5 task-delegators in parallel (each with template above)
3. Wait for completion
4. Verify all files exist and pass checks
5. Update manifest.json (add entries, increment count)
6. Commit + push
7. Spawn next 5 task-delegators
8. Repeat until all games deployed
9. Final production report
```

## Games Already Built (avoid duplicates)

Recursion, Flesh Machine, The Trial, Memory Palace, God Complex, Infernal Trader, Babel, Paradox Engine, The Vote, Sentient, Deep State, Neuromancer, Dreamwalker, Chronoscape, Phantom Protocol, Last Signal, Infinite City, Murder Board, Wetware, Thousand Suns, Parallax Dimensions, Signal Lost, Epoch, The Architect, Neon District, Abyssal Depths, Starfield Traders, Colony Survival + earlier waves (GPU Fluid, Circuit Sim, Planet Gen, Neural Net, Audio Viz, Spreadsheet, Synth DAW, Markdown Editor, Pixel Art, Chess, Voxel Builder, Fractal Explorer, Music Theory, Roguelike, Dashboard)
