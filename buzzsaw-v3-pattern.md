# Buzzsaw v3 Pattern: Three-Layer AI Delegation

## The Problem

AI coding agents (Claude Code, Cursor, Copilot Workspace, etc.) have a fundamental limitation: **subagents can't spawn other subagents**. This means you can either:

1. **Sequential**: One agent writes everything (slow, burns context)
2. **Parallel but shallow**: Main orchestrator spawns workers who each write code directly (fast, but each worker burns its own context writing 2000+ lines)

Neither is ideal for mass production of complex artifacts (games, apps, reports, etc.).

## The Breakthrough: CLI Tools as a Third Layer

**Key insight:** `gh copilot` (and similar CLI tools) are shell commands, not subagents. Subagents CAN call them via Bash. This creates a third layer of delegation that bypasses the subagent limitation.

```
Layer 1: Main Orchestrator (Claude Code)
  │  Spawns 4-6 subagents in PARALLEL
  │  Each subagent works on a separate file (zero conflicts)
  │  Handles coordination: manifest, git, reporting
  │
  ├─► Layer 2: Subagent A ─► Layer 3: gh copilot CLI (Opus 4.6)
  ├─► Layer 2: Subagent B ─► Layer 3: gh copilot CLI (Opus 4.6)
  ├─► Layer 2: Subagent C ─► Layer 3: gh copilot CLI (Opus 4.6)
  ├─► Layer 2: Subagent D ─► Layer 3: gh copilot CLI (Opus 4.6)
  ├─► Layer 2: Subagent E ─► Layer 3: gh copilot CLI (Opus 4.6)
  └─► Layer 2: Subagent F ─► Layer 3: gh copilot CLI (Opus 4.6)
```

Each subagent is a **lean orchestrator** that:
1. Writes a prompt (small — 500-1000 words)
2. Pipes it to `gh copilot` CLI
3. Validates the output (small — just grep/wc checks)
4. Sends fix prompts if needed (self-healing)
5. Falls back to direct code generation only if CLI fails

## Why This Is Important

### 1. Context Conservation
| Architecture | Tokens per artifact |
|---|---|
| Direct write (1 layer) | ~30,000 tokens in one context |
| Subagent write (2 layers) | ~30,000 tokens in subagent context |
| **Buzzsaw v3 (3 layers)** | **~5,000 tokens in subagent + Copilot has own context** |

The subagent's context stays lean because it only holds prompts and validation results, not the generated code. The heavy code generation happens in Copilot CLI's context window, which is completely separate.

### 2. Parallel Execution
The main orchestrator can spawn 4-6 subagents simultaneously, each calling Copilot CLI independently. This means 4-6 artifacts building in parallel, each with its own three-layer stack.

### 3. Self-Healing
When Copilot's output fails validation, the subagent can send targeted fix prompts back to Copilot. This creates an automated quality loop:

```
Generate → Validate → PASS → Done
                    → FAIL → Fix prompt → Regenerate → Validate → PASS → Done
                                                                → FAIL → Fix again → Validate → PASS/FAIL
                                                                                               → Fallback to direct write
```

### 4. Graceful Degradation
If `gh copilot` is unavailable (network issues, auth expired, rate limited), the subagent falls back to writing code directly. The pipeline never blocks — it just runs at reduced efficiency.

### 5. Longer Sessions
Because context is conserved at every layer, the main orchestrator can run for much longer before hitting context limits. In our testing:
- Without Buzzsaw v3: ~15-20 games before context exhaustion
- With Buzzsaw v3: 45+ games and still going

## The Pattern (Generalized)

This isn't specific to games. The pattern works for any mass-production pipeline:

```
Layer 1 (Orchestrator):
  - Defines WHAT to build (concepts, specs, requirements)
  - Spawns parallel workers
  - Handles shared resources (manifest, config, git)
  - Reports results

Layer 2 (Worker Subagent):
  - Receives ONE task from orchestrator
  - Crafts prompt for CLI tool
  - Calls CLI tool via Bash
  - Validates output
  - Self-heals on failure
  - Reports back

Layer 3 (CLI Tool):
  - Receives prompt
  - Generates artifact (code, content, analysis)
  - Returns raw output
  - Has its own context window
```

### Applicable Use Cases

| Use Case | Layer 1 | Layer 2 | Layer 3 |
|---|---|---|---|
| Game production | Claude Code | task-delegator | gh copilot CLI |
| Documentation | Claude Code | task-delegator | gh copilot CLI |
| Test generation | Claude Code | task-delegator | gh copilot CLI |
| Code migration | Claude Code | task-delegator | gh copilot CLI |
| Data transformation | Claude Code | task-delegator | any LLM CLI |
| Content generation | Claude Code | task-delegator | any LLM CLI |

### Other CLI Tools That Work as Layer 3

- `gh copilot` — GitHub Copilot CLI (Claude Opus 4.6, GPT-4, etc.)
- `ollama run` — Local LLM inference
- `anthropic messages create` — Anthropic API CLI
- `openai api chat.completions.create` — OpenAI API CLI
- Any CLI tool that accepts a prompt and returns generated text

## Implementation Details

### Prompt Engineering for Layer 3

The prompt sent to the CLI tool must be self-contained and explicit:

```
OUTPUT ONLY [format]. No markdown, no explanations, no preamble.

[Detailed specification of what to generate]

REQUIREMENTS:
- [Constraint 1]
- [Constraint 2]
- [Quality bar]
```

### Validation Checklist (customize per use case)

1. File exists and is non-empty
2. File size within expected range
3. Required patterns present (DOCTYPE, imports, etc.)
4. Forbidden patterns absent (external deps, secrets, etc.)
5. Structural integrity (valid JSON, valid HTML, compiles, etc.)
6. Domain-specific checks (has localStorage, has tests, etc.)

### Error Handling Chain

```
CLI generates → validation passes → DONE
CLI generates → validation fails → fix prompt to CLI (attempt 1)
CLI generates → validation fails again → fix prompt to CLI (attempt 2)
CLI generates → still fails → subagent writes directly (fallback)
CLI unavailable → subagent writes directly (immediate fallback)
Subagent fails → log error, skip, continue pipeline
```

## Real-World Results

In our localFirstTools gallery project:
- **45 games** built in a single session
- **6 parallel subagents** running simultaneously
- **~2.5MB** of playable game code generated
- **Zero manual intervention** after "go" command
- Each game: 50-100KB, 1500-2500 lines, fully playable with saves/audio/procedural gen

## Key Takeaways

1. **CLI tools bypass the subagent limitation** — they're shell commands, not agents
2. **Three layers = parallelism + context conservation + self-healing**
3. **The pattern is generalizable** — works for any mass-production task, not just games
4. **Graceful degradation ensures delivery** — pipeline never blocks on a single failure
5. **The orchestrator stays lean** — it only writes prompts and coordinates, never code
