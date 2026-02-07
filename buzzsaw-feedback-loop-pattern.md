# Buzzsaw Feedback Loop: Self-Improving Production Pipeline

## The Vision

Combine three existing patterns into a closed-loop system that gets BETTER with every generation:

```
┌─────────────────────────────────────────────────────────┐
│                   GENERATION N                           │
│                                                          │
│  Buzzsaw v3 ──► Produce 10 games ──► Data Slosh scores  │
│       ▲                                    │             │
│       │         Feedback Loop              │             │
│       │                                    ▼             │
│  Best examples from Gen N    Quality report with         │
│  become reference for        per-game scores,            │
│  Gen N+1 prompts             failure patterns,           │
│                              improvement suggestions     │
│                                                          │
│  ──► Molt worst-scoring games using Copilot CLI ──►     │
│       Archive Gen N version, deploy Gen N+1              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## The Three Components

### 1. Buzzsaw v3 (Producer)
Three-layer parallel game production.
- Layer 1: Orchestrator spawns parallel subagents
- Layer 2: Subagents call `gh copilot` CLI
- Layer 3: Copilot generates code

**Output:** N new game HTML files

### 2. Data Slosh (Quality Scorer)
Analyzes each game file and scores it on multiple dimensions:
- **Structural**: DOCTYPE, meta tags, semantic HTML, no external deps
- **Code quality**: Lines of code, function count, class usage, error handling
- **Game systems**: Has canvas, has localStorage, has audio, has procedural gen
- **Completeness**: Has title screen, HUD, pause menu, game over, multiple endings
- **Size**: File size relative to target (80-120KB sweet spot)

**Output:** Per-game quality scores (0-100) + specific failure list

### 3. Generational Feedback (Improver)
Uses Data Slosh scores to:
- **Molt** the worst-scoring games (send to Copilot with targeted improvement prompt)
- **Archive** the current version (v1, v2, v3...)
- **Update prompts** for the next Buzzsaw run using the BEST games as reference
- **Build a versioned example library** that gets richer with each generation

## The Feedback Loop in Detail

### Generation 1: Blind Production
```
Buzzsaw v3 produces 10 games
  → No prior examples, just prompt engineering
  → Data Slosh scores all 10
  → Results: 3 excellent (85+), 4 good (60-84), 3 weak (<60)
```

### Generation 2: Informed Production
```
Take the 3 excellent games from Gen 1
  → Extract their patterns: what made them score high?
  → Feed patterns into Gen 2 prompts: "Follow the style of [excellent-game.html]"
  → Buzzsaw v3 produces 10 MORE games with improved prompts
  → Molt the 3 weak games from Gen 1 using targeted fix prompts
  → Data Slosh scores everything
  → Results: 5 excellent, 4 good, 1 weak (improvement!)
```

### Generation 3+: Compounding Quality
```
Best examples now include top games from Gen 1 AND Gen 2
  → Prompt library is richer
  → Known failure patterns are explicitly avoided
  → Average quality keeps climbing
  → Weak games get molted until they pass threshold
```

## Implementation

### Data Slosh Quality Check (per game)

```python
def score_game(filepath):
    """Score a game file on 0-100 scale across quality dimensions."""
    content = open(filepath).read()
    lines = content.count('\n')
    size_kb = len(content) / 1024

    score = 0
    checks = []

    # Structural (20 points)
    if '<!DOCTYPE html>' in content: score += 5; checks.append('DOCTYPE ✓')
    if '<meta name="viewport"' in content: score += 3; checks.append('viewport ✓')
    if '<title>' in content: score += 3; checks.append('title ✓')
    if 'src="http' not in content and 'href="http' not in content: score += 5; checks.append('no-ext-deps ✓')
    if '<style>' in content and '<script>' in content: score += 4; checks.append('inline-css-js ✓')

    # Scale (20 points)
    if lines > 2000: score += 10
    elif lines > 1000: score += 6
    elif lines > 500: score += 3

    if 50 <= size_kb <= 150: score += 10  # sweet spot
    elif 20 <= size_kb < 50: score += 5
    elif size_kb > 150: score += 7  # big is ok, just not ideal

    # Game Systems (30 points)
    if 'localStorage' in content: score += 5; checks.append('saves ✓')
    if 'requestAnimationFrame' in content: score += 5; checks.append('game-loop ✓')
    if 'AudioContext' in content or 'webkitAudioContext' in content: score += 5; checks.append('audio ✓')
    if 'canvas' in content.lower(): score += 5; checks.append('canvas ✓')
    if 'Math.random' in content: score += 3; checks.append('procedural ✓')
    if content.count('addEventListener') >= 3: score += 3; checks.append('input ✓')
    if 'class ' in content and content.count('class ') >= 3: score += 4; checks.append('classes ✓')

    # Completeness (20 points)
    if 'pause' in content.lower() or 'paused' in content.lower(): score += 4; checks.append('pause ✓')
    if 'game over' in content.lower() or 'gameover' in content.lower(): score += 4; checks.append('game-over ✓')
    if 'score' in content.lower(): score += 3; checks.append('scoring ✓')
    if 'level' in content.lower() or 'wave' in content.lower(): score += 3; checks.append('progression ✓')
    if content.count('ending') >= 2 or content.count('Ending') >= 2: score += 3; checks.append('endings ✓')
    if 'title' in content.lower() and ('start' in content.lower() or 'play' in content.lower()): score += 3

    # Code Quality (10 points)
    if 'try' in content and 'catch' in content: score += 3; checks.append('error-handling ✓')
    if 'const ' in content or 'let ' in content: score += 3; checks.append('modern-js ✓')
    if content.count('function') >= 10 or content.count('=>') >= 10: score += 4; checks.append('well-structured ✓')

    return min(score, 100), checks
```

### Versioned Example Library

```
apps/archive/quality-examples/
  ├── gen-1/
  │   ├── best-game-1.html (score: 92)
  │   ├── best-game-2.html (score: 88)
  │   └── quality-report.json
  ├── gen-2/
  │   ├── best-game-3.html (score: 95)
  │   ├── best-game-4.html (score: 91)
  │   └── quality-report.json
  └── patterns.md  ← extracted patterns from top-scoring games
```

### Prompt Enhancement from Examples

```
# Generation 1 prompt (blind):
"Create a massive game called X with these systems..."

# Generation 2 prompt (informed):
"Create a massive game called X with these systems...

QUALITY REFERENCE: The highest-scoring games in our gallery share these patterns:
- Canvas game loop with clear state machine (menu/playing/paused/gameover)
- Class-based entity system with collision detection
- Procedural generation using seeded random + noise functions
- Resource management with visible HUD bars
- Save system that serializes full game state to localStorage JSON
- Web Audio API with at least: ambient drone, action SFX, UI feedback sounds
- Visual polish: particle systems, screen shake on impact, smooth transitions
- Title screen with instructions, pause on ESC, game over with stats

AVOID these patterns found in low-scoring games:
- setInterval for game loops (use requestAnimationFrame)
- Global mutable state instead of game state object
- Missing pause functionality
- No save/load system
- Placeholder sounds or no audio
- Abrupt game over without summary screen
"
```

### Molt Integration

When Data Slosh identifies weak games (score < 60):

```bash
# Extract the specific failures
FAILURES=$(python3 score_game.py apps/games-puzzles/weak-game.html --failures-only)

# Send targeted molt prompt to Copilot
cat > /tmp/molt-prompt.txt << EOF
The following HTML game scores poorly on these dimensions:
$FAILURES

Rewrite the game to fix ALL listed issues while preserving the core gameplay.
OUTPUT ONLY the complete fixed HTML file.
$(head -c 8000 apps/games-puzzles/weak-game.html)
EOF

gh copilot -p "$(cat /tmp/molt-prompt.txt)" --no-ask-user --model claude-opus-4.6 > /tmp/molted.html

# Archive original, deploy improved version
mkdir -p apps/archive/weak-game/
cp apps/games-puzzles/weak-game.html apps/archive/weak-game/v1.html
# Extract and validate molted version, replace original
```

## The Compounding Effect

| Generation | Avg Score | Top Score | Weak Games | Example Library Size |
|---|---|---|---|---|
| Gen 1 | 65 | 85 | 3/10 | 3 examples |
| Gen 2 | 75 | 92 | 1/10 | 8 examples |
| Gen 3 | 82 | 96 | 0/10 | 15 examples |
| Gen 4+ | 85+ | 98 | 0/10 | 20+ examples |

Each generation:
1. Produces games at higher baseline quality (better prompts)
2. Molts any remaining weak games (self-healing)
3. Adds best games to the example library (compounding reference)
4. Extracts new patterns from top scorers (continuous learning)

## Key Insight: Why This Works

The system has **memory across generations**. Without the feedback loop, every batch starts blind. With it:
- Good patterns are preserved and amplified
- Bad patterns are identified and explicitly avoided
- The example library grows, giving future prompts richer context
- Molting catches what production missed

This is **artificial selection applied to code generation** — survival of the fittest games, with the selection pressure being the Data Slosh quality score.

## Related Patterns
- **Buzzsaw v3**: Three-layer production architecture (`buzzsaw-v3-pattern.md`)
- **Molting Generations**: Iterative improvement of individual apps (`molting-generations-pattern.md`)
- **Copilot Intelligence**: Using `gh copilot` CLI for LLM judgment (`copilot-intelligence-pattern.md`)
- **Data Slosh**: Quality scoring and auditing (`.claude/agents/data-slosh.md`)
