# Data Slosh -- HTML Quality Pipeline Agent

Autonomous agent that scans, scores, classifies, and optionally rewrites the 450+ HTML apps in the localFirstTools-main gallery. Uses the 18 quality rules from `apps/creative-tools/data-slosh.html` and the Flask API server (`scripts/app.py`) for AI-powered classification and rewriting via GitHub Copilot CLI with Claude Opus.

---

## How to Invoke

Use the `data-slosh` agent from Claude Code. The agent name triggers automatic delegation.

**Scan all apps (default, non-destructive):**
```
Run data-slosh to scan all apps and generate a quality report.
```

**Scan a single category:**
```
Run data-slosh on the games-puzzles category.
```

**Fix low-quality files:**
```
Run data-slosh in fix mode. Rewrite any file scoring below 80.
```

**Analyze a single file:**
```
Run data-slosh on apps/experimental-ai/some-app.html.
```

**Reclassify misplaced apps:**
```
Run data-slosh in batch reclassify mode.
```

---

## Modes

### Mode 1: Scan and Report (default)

- Reads every HTML file under `apps/`
- Scores each file against 18 quality rules (pure regex, no API needed)
- Outputs a markdown table sorted by score (worst first)
- Saves report to `data-slosh-report.md` in the repo root
- Changes nothing on disk

### Mode 2: Fix Quality Issues

- Scans and scores like Mode 1
- Starts the API server (`scripts/app.py`) for AI-powered rewrites
- For files scoring below the threshold (default 90):
  - Backs up the original as `<file>.bak.html`
  - Calls `/api/rewrite` for an AI-improved version
  - Writes the improved HTML back
  - Re-scores to verify improvement
  - Updates manifest.json metadata if changed
- If the API is unavailable, applies mechanical fixes only (DOCTYPE, charset, viewport, lang)

### Mode 3: Single File

- Analyzes one file in full detail
- Shows all 18 rule results with pass/fail
- If API is available: shows AI-suggested filename, category, title, description, tags
- Optionally rewrites and shows a diff

### Mode 4: Batch Reclassify

- Scans all apps and calls `/api/analyze` for AI classification
- Identifies files where the AI-suggested category differs from the current category
- Presents the list of proposed moves for user confirmation
- Moves files to the correct category folder
- Updates manifest.json (removes from old category, adds to new, adjusts counts)

---

## Quality Rules (18 Rules, 100-Point Scale)

Score starts at 100. Each failed rule deducts its weight. Minimum score is 0.

### Errors (15 points each)

| ID | Rule | What It Checks |
|----|------|----------------|
| `missing-doctype` | DOCTYPE declaration | `<!DOCTYPE html>` present at start of file |
| `missing-charset` | Character encoding | `<meta charset="UTF-8">` or equivalent |
| `missing-viewport` | Viewport meta | `<meta name="viewport" content="...">` |
| `external-scripts` | No external scripts | No `<script src="https://...">` tags |
| `external-styles` | No external stylesheets | No `<link href="https://...">` stylesheet tags |
| `cdn-dependencies` | No CDN URLs | No `src=` or `href=` attributes pointing to `http(s)://` |

### Warnings (5 points each)

| ID | Rule | What It Checks |
|----|------|----------------|
| `missing-title` | Page title | `<title>` tag exists and is not empty |
| `missing-html-lang` | Language attribute | `<html lang="en">` or similar |
| `missing-description` | Meta description | `<meta name="description" content="...">` |
| `no-localstorage` | State persistence | Uses `localStorage.getItem/setItem/removeItem/clear` |
| `no-json-export` | Data portability | If localStorage is used, also has JSON.stringify + download/Blob |
| `no-error-handling` | Error handling | Has `try/catch`, `window.onerror`, or error event listener |
| `console-log-pollution` | Clean console | No `console.log`, `console.debug`, or `console.info` calls |
| `hardcoded-api-keys` | No secrets | No patterns like `api_key = "AAAA..."` with 16+ char values |

### Info (2 points each)

| ID | Rule | What It Checks |
|----|------|----------------|
| `no-media-queries` | Responsive design | Has `@media` rules in CSS |
| `no-aria-labels` | Accessibility | Has `aria-label` or `role=` attributes |
| `no-noscript` | Graceful degradation | Has `<noscript>` fallback |
| `inline-onclick` | Event handling | No inline `onclick=`, `onmouseover=`, etc. |
| `missing-input-labels` | Form accessibility | Input/select/textarea elements have associated labels |

### Score Interpretation

| Range | Grade | Action |
|-------|-------|--------|
| 90-100 | Excellent | No action needed |
| 71-89 | Good | Minor issues, optional fix |
| 51-70 | Fair | Should be fixed |
| 0-50 | Poor | Needs rewrite |

---

## API Integration

### Server Setup

The Flask API server at `scripts/app.py` bridges to Claude Opus 4.6 via `gh copilot` CLI.

**Start manually:**
```bash
cd /Users/kodyw/Projects/localFirstTools-main
python3 scripts/app.py           # Default port 5000
python3 scripts/app.py --port 8080  # Custom port
```

**Requirements:**
- Python 3 with Flask and flask-cors (`pip install flask flask-cors`)
- GitHub CLI (`gh`) with the Copilot extension installed and authenticated

### Endpoints

**Health check:**
```bash
curl http://localhost:5000/api/health
# {"status":"ok","backend":"copilot-cli","model":"claude-opus-4.6"}
```

**Analyze (classify an HTML file):**
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"html":"<!DOCTYPE html>...", "filename":"game.html", "analysis":{"score":75,"errors":1,"warnings":3,"failedRules":["missing-charset"]}}'
# {"category":"games_puzzles","filename":"snake-game.html","title":"Snake Game","description":"...","tags":[...],"type":"game","complexity":"simple","categoryFolder":"games-puzzles"}
```

**Rewrite (AI-improved HTML):**
```bash
curl -X POST http://localhost:5000/api/rewrite \
  -H "Content-Type: application/json" \
  -d '{"html":"<!DOCTYPE html>...", "filename":"game.html", "analysis":{"score":65,"failedRules":["missing-doctype"]}}'
# {"rewrittenHTML":"<!DOCTYPE html>...","metadata":{...},"suggestedFilename":"snake-game.html","suggestedCategory":"games_puzzles",...}
```

### Rate Limiting

The Copilot CLI backend is rate-limited. The agent enforces a minimum 3-second delay between API calls. For a full gallery scan with AI classification, expect approximately 450 files x 3 seconds = ~22 minutes.

---

## Troubleshooting

### gh copilot is not available

**Symptoms:** Health endpoint returns `"backend": "unavailable"`, or `gh copilot` commands fail.

**Fix:**
1. Verify `gh` is installed: `gh --version`
2. Verify Copilot extension: `gh extension list` (should show `github/gh-copilot`)
3. Install if missing: `gh extension install github/gh-copilot`
4. Authenticate: `gh auth login`

**Workaround:** The agent falls back to local-only mode (regex scoring, mechanical fixes). AI classification and full rewrites are unavailable without Copilot.

### Port 5000 already in use

**Symptoms:** `Address already in use` when starting the API server.

**Fix:**
```bash
# Find what's using port 5000
lsof -i :5000

# Kill it
lsof -ti:5000 | xargs kill

# Or use a different port
python3 scripts/app.py --port 5001
```

### Flask not installed

**Symptoms:** `ModuleNotFoundError: No module named 'flask'`

**Fix:**
```bash
pip3 install flask flask-cors
```

### API returns 502 / "Could not parse LLM response"

**Symptoms:** The Copilot CLI returned output that could not be parsed as JSON.

**Cause:** The LLM sometimes wraps JSON in markdown fences or adds preamble text. The server's `parse_llm_json` function handles most cases, but occasionally fails.

**Workaround:** Retry the request. If it persists, the agent skips that file and moves on.

### Manifest.json becomes invalid after edits

**Symptoms:** `json.JSONDecodeError` when validating manifest.

**Fix:** The agent always validates after editing. If validation fails, it reverts the last edit. To manually check:
```bash
python3 -c "import json; json.load(open('apps/manifest.json')); print('VALID')"
```

### Backup files (.bak.html) accumulating

After a Mode 2 fix run, backup files are left alongside originals. To clean them up after verifying the rewrites are good:
```bash
find apps -name "*.bak.html" -delete
```

---

## Safety Guarantees

- **Non-destructive by default.** Mode 1 changes nothing on disk.
- **Backups before rewrites.** Every overwritten file gets a `.bak.html` copy first.
- **No deletions.** The agent never deletes files, only renames, moves, or rewrites.
- **Manifest validation.** Every manifest edit is followed by a JSON validity check.
- **Confirmation for destructive ops.** Modes 2 and 4 ask for user confirmation before applying changes.
- **Graceful degradation.** If the API is down, the agent still produces useful local-only reports.

---

## Files Reference

| File | Purpose |
|------|---------|
| `apps/creative-tools/data-slosh.html` | Browser UI for the quality pipeline (the original tool) |
| `scripts/app.py` | Flask API server bridging to Copilot CLI |
| `scripts/autosort.py` | Separate pipeline for sorting root files into apps/ (the agent does NOT duplicate this) |
| `apps/manifest.json` | App registry, source of truth for all 450+ apps |
| `.claude/agents/data-slosh.md` | This agent's configuration file |
| `.claude/skills/data-slosh.md` | This documentation file |
| `data-slosh-report.md` | Output report (generated by the agent, not checked in) |
