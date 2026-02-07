# Copilot Intelligence Pattern

Reusable pattern for adding LLM-powered intelligence to any automation pipeline using GitHub Copilot SDK/CLI with Claude Opus.

**Why this pattern:** You get unlimited Claude Opus usage through your Copilot subscription. No API keys to manage, no billing surprises, no rate limits. Authentication flows through `gh` CLI automatically.

---

## Architecture

```
Your Script/Pipeline
        │
        ▼
┌──────────────────┐
│  Copilot CLI/SDK  │  ◄── gh copilot --model claude-opus-4.6
│  (JSON-RPC 2.0)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Claude Opus 4.6  │  ◄── Unlimited via Copilot subscription
│  (Intelligence)    │
└──────────────────┘
```

**Data flow:** Your code reads raw input → constructs a structured prompt → sends to Copilot CLI/SDK → Claude Opus analyzes and returns structured JSON → your code acts on the result.

---

## Two Integration Approaches

### Approach 1: CLI Subprocess (Simple, recommended for <20 items)

Call `gh copilot` directly from any language. No pip install, no async code. Already authenticated through `gh auth`.

```python
import subprocess
import json

def copilot_analyze(prompt, model="claude-opus-4.6"):
    """Send a prompt to Copilot CLI, get structured response."""
    result = subprocess.run(
        [
            "gh", "copilot",
            "--model", model,
            "-p", prompt,
            "--no-ask-user",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Copilot CLI failed: {result.stderr}")
    return result.stdout.strip()
```

**Pros:** Zero dependencies, works anywhere `gh` is installed, trivial to debug.
**Cons:** Process spawn overhead per call, harder to batch.

### Approach 2: Python SDK (Programmatic, recommended for batch/streaming)

```bash
pip install github-copilot-sdk
```

```python
import asyncio
from copilot import CopilotClient

async def copilot_batch_analyze(items, model="claude-opus-4.6"):
    """Analyze multiple items in a single session."""
    client = CopilotClient()
    await client.start()

    session = await client.create_session({"model": model})
    results = []

    for item in items:
        response = await session.send_and_wait({"prompt": item["prompt"]})
        results.append(json.loads(response.data.content))

    await client.stop()
    return results
```

**Pros:** Single session for multiple items, streaming support, custom tools.
**Cons:** Requires pip install, async code, alpha SDK.

---

## The Structured JSON Prompt Pattern

The key to reliable automation is forcing structured JSON output. Every prompt follows this template:

```
You are a {role} analyzing {input_type}.

Analyze the following {input_type} and return ONLY a JSON object (no markdown, no explanation, no code fences) with these exact keys:

{json_schema}

Rules:
- {constraint_1}
- {constraint_2}
- {constraint_3}

{input_type} to analyze:
---
{content}
---

Return ONLY the JSON object.
```

### Example: File Categorization Prompt

```
You are a content analyst categorizing HTML applications.

Analyze this HTML file and return ONLY a JSON object with these exact keys:

{
  "category": "one of: 3d_immersive, audio_music, games_puzzles, visual_art, generative_art, particle_physics, creative_tools, educational_tools, experimental_ai",
  "filename": "descriptive-kebab-case-name.html",
  "title": "Human Readable Title",
  "description": "One sentence describing what this app does",
  "tags": ["up to 6 tags from: 3d, canvas, svg, animation, audio, particles, physics, interactive, game, ai, creative, terminal, retro, simulation, crm"],
  "complexity": "simple|intermediate|advanced",
  "type": "game|visual|audio|interactive|interface|drawing"
}

Rules:
- category MUST be one of the 9 listed options. Never return "uncategorized" or "other".
- filename must be kebab-case, descriptive of the content, max 60 chars, ending in .html
- description must be exactly one sentence, under 120 characters
- complexity: simple (<20KB), intermediate (20-50KB), advanced (>50KB or uses WebGL/3D)
- Pick the MOST SPECIFIC category that fits. experimental_ai is the catch-all ONLY if nothing else fits.

File content (first 8000 chars):
---
{content[:8000]}
---

Return ONLY the JSON object.
```

---

## JSON Response Parsing

Always parse with fallback. LLMs occasionally wrap output in code fences or add preamble.

```python
import json
import re

def parse_llm_json(raw_output):
    """Extract JSON from LLM output, handling common formatting issues."""
    text = raw_output.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM output: {text[:200]}")
```

---

## Authentication

### Local Development

Already handled if you're logged into `gh`:
```bash
gh auth status  # Check if authenticated
gh auth login   # Login if needed
```

### GitHub Actions (CI)

The `GITHUB_TOKEN` provided by Actions works automatically:
```yaml
steps:
  - uses: actions/checkout@v4

  - name: Run intelligent pipeline
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    run: python3 scripts/autosort.py --verbose
```

For Copilot SDK, set the token explicitly:
```yaml
    env:
      COPILOT_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### BYOK (Bring Your Own Key) Fallback

If Copilot isn't available (forks, self-hosted runners), the script should fall back gracefully:
```python
def get_intelligence_backend():
    """Determine which intelligence backend to use."""
    # 1. Try Copilot CLI
    if shutil.which("gh"):
        result = subprocess.run(["gh", "copilot", "--help"], capture_output=True)
        if result.returncode == 0:
            return "copilot-cli"

    # 2. Try Copilot SDK
    try:
        import copilot
        return "copilot-sdk"
    except ImportError:
        pass

    # 3. Fall back to keyword matching (no LLM)
    return "keyword-fallback"
```

---

## Available Models (via Copilot)

| Model | ID | Best For |
|-------|----|----------|
| Claude Opus 4.6 | `claude-opus-4.6` | Complex analysis, planning, hard reasoning |
| Claude Sonnet 4.5 | `claude-sonnet-4.5` | Fast balanced tasks |
| Claude Haiku 4.5 | `claude-haiku-4.5` | Quick classification, simple extraction |
| GPT-5.2 | `gpt-5.2` | General purpose |
| Gemini 3 Pro | `gemini-3-pro-preview` | Multimodal |

**Default to `claude-opus-4.6`** for any task requiring judgment, categorization, or content understanding. Use `claude-haiku-4.5` for simple classification if latency matters.

---

## Pattern Checklist

When applying this pattern to a new automation:

- [ ] Define the structured JSON schema for your use case
- [ ] Write a prompt template with explicit constraints and examples
- [ ] Implement `parse_llm_json()` for robust response parsing
- [ ] Add a keyword-based fallback for environments without Copilot
- [ ] Handle timeouts (120s default) and retries (max 2)
- [ ] Log raw LLM output for debugging (`--verbose` flag)
- [ ] Test with `--dry-run` before executing destructive operations
- [ ] Set `--model claude-opus-4.6` explicitly (don't rely on defaults)

---

## Anti-Patterns

- **Don't parse free-text responses.** Always request JSON.
- **Don't send entire large files.** Truncate to first 8000 chars (title, meta, and early code are most informative).
- **Don't call the LLM for things you can check deterministically.** File size, tag detection via regex, collision avoidance — these don't need AI.
- **Don't skip the fallback.** Not every environment has Copilot. Keyword matching is a perfectly fine degraded mode.
- **Don't chain LLM calls.** One call per file, one structured response. Keep it simple.

---

## Example Implementation

See `scripts/autosort.py` in this repo for a complete working implementation that:
1. Reads HTML files dropped in root
2. Sends content to Claude Opus via Copilot CLI
3. Gets back structured JSON (category, filename, title, description, tags)
4. Renames, moves, and updates the manifest
5. Falls back to keyword matching if Copilot is unavailable
