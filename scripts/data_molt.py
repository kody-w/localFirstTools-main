#!/usr/bin/env python3
"""Universal Data Molt Engine.

Discovers, analyzes, and refreshes ANY data file in the RappterZoo ecosystem.
Not limited to HTML — handles JSON, TOML, CSV, or any content type.
Uses Copilot CLI (Claude Opus 4.6) for staleness analysis and content regeneration.

Usage:
    python3 scripts/data_molt.py                      # Analyze all data files
    python3 scripts/data_molt.py --molt               # Molt stale files
    python3 scripts/data_molt.py --molt --verbose      # Verbose output
    python3 scripts/data_molt.py --file community.json # Molt specific file
    python3 scripts/data_molt.py --status              # Show data molt state
    python3 scripts/data_molt.py --dry-run             # Analyze without changes
    python3 scripts/data_molt.py --push                # Molt + commit + push

Output: Refreshed data files + apps/data-molt-state.json
"""

import json
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
SCRIPTS_DIR = ROOT / "scripts"
ARCHIVE_DIR = APPS_DIR / "archive" / "data"
STATE_FILE = APPS_DIR / "data-molt-state.json"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

# Files that should NEVER be directly molted (source of truth or operational)
PROTECTED_FILES = {
    "manifest.json",      # Source of truth — synced from HTML meta tags
    "molter-state.json",  # Operational state tracker
}

# Known regeneration strategies — maps relative path patterns to scripts.
# If a file isn't here, the engine falls back to LLM inline rewrite.
KNOWN_STRATEGIES = {
    "community.json": {
        "script": "generate_community.py",
        "args": [],
        "description": "Regenerate community data via Copilot CLI",
    },
    "broadcasts/feed.json": {
        "script": "generate_broadcast.py",
        "args": ["--regenerate-all"],
        "description": "Regenerate all podcast episodes via Copilot CLI",
    },
    "content-graph.json": {
        "script": "compile_graph.py",
        "args": [],
        "description": "Recompile content relationship graph",
    },
    "rankings.json": {
        "script": "rank_games.py",
        "args": [],
        "description": "Recalculate quality rankings",
    },
}


def log(msg):
    if VERBOSE:
        print(f"  [data-molt] {msg}")


# ── Discovery ──

def discover_data_files(apps_dir):
    """Find all data files in the ecosystem, excluding HTML and archives.

    Returns list of Path objects for every non-HTML, non-archive content file.
    Automatically adapts to new file types — no hardcoded extension list.
    """
    apps_dir = Path(apps_dir)
    files = []

    # Known data extensions + catch-all for anything that's not HTML/media
    skip_extensions = {".html", ".htm", ".png", ".jpg", ".jpeg", ".gif",
                       ".svg", ".ico", ".wav", ".mp3", ".ogg", ".woff",
                       ".woff2", ".ttf", ".eot"}

    for path in apps_dir.rglob("*"):
        if not path.is_file():
            continue
        # Skip archives
        if "archive" in path.parts:
            continue
        # Skip HTML (handled by HTML molt system)
        if path.suffix.lower() in skip_extensions:
            continue
        # Skip hidden files
        if any(part.startswith(".") for part in path.parts):
            continue
        # Skip node_modules or similar
        if "node_modules" in path.parts:
            continue

        files.append(path)

    return sorted(files)


# ── Staleness Analysis ──

def analyze_staleness(file_path, ecosystem_context=None):
    """Ask the LLM to analyze a data file for staleness.

    Returns dict with: stale (bool), score (0-100), strategy (str), issues (list)
    """
    from copilot_utils import copilot_call, parse_llm_json

    file_path = Path(file_path)
    if not file_path.exists():
        return {"stale": False, "score": 0, "strategy": "skip", "issues": ["File not found"]}

    content = file_path.read_text(errors="replace")
    size = len(content)

    # Sample for LLM (first 3000 chars + last 500 chars for large files)
    if len(content) > 4000:
        sample = content[:3000] + "\n...[truncated]...\n" + content[-500:]
    else:
        sample = content

    ctx = ecosystem_context or {}

    prompt = f"""Analyze this data file for staleness and quality issues.

File: {file_path.name}
Size: {size} bytes
Last modified: {datetime.fromtimestamp(file_path.stat().st_mtime).isoformat() if file_path.exists() else 'unknown'}
Ecosystem: {ctx.get('total_apps', '?')} total apps, frame {ctx.get('frame', '?')}

Content sample:
```
{sample}
```

Evaluate:
1. Is the content stale? (outdated timestamps, missing data, references old state)
2. Are there duplicates? (same text appearing multiple times, template-like patterns)
3. Is coverage complete? (does it cover all apps in the ecosystem?)
4. Is the content quality good? (specific, contextual, varied — or generic/repetitive?)

Return JSON:
{{
  "stale": true/false,
  "score": 0-100 (100 = perfectly fresh),
  "strategy": "regenerate" | "molt" | "skip",
  "issues": ["specific issue 1", "specific issue 2"]
}}

- "regenerate" = run the generation script from scratch
- "molt" = LLM should rewrite the content inline (for unknown file types)
- "skip" = content is fresh enough, no action needed

Return ONLY the JSON."""

    raw = copilot_call(prompt, timeout=45)
    result = parse_llm_json(raw) if raw else None

    if result and isinstance(result, dict):
        # Ensure required fields
        return {
            "stale": result.get("stale", False),
            "score": result.get("score", 50),
            "strategy": result.get("strategy", "skip"),
            "issues": result.get("issues", []),
        }

    # LLM failure — conservative default
    return {"stale": False, "score": 50, "strategy": "skip",
            "issues": ["LLM analysis failed — skipping"]}


# ── Routing ──

def route_strategy(file_path, analysis):
    """Decide how to refresh this file: existing script, LLM rewrite, or skip.

    Returns dict with: method (str), script (str|None), args (list|None)
    """
    file_path = Path(file_path)
    rel = file_path.name

    # Check relative path patterns for known strategies
    # Try both just filename and parent/filename
    try:
        rel_to_apps = str(file_path.relative_to(file_path.parent.parent))
    except (ValueError, IndexError):
        rel_to_apps = rel

    # Protected files are never molted
    if rel in PROTECTED_FILES:
        return {"method": "skip", "reason": "Protected file (source of truth)"}

    # If analysis says skip, skip
    if analysis.get("strategy") == "skip" or not analysis.get("stale", False):
        return {"method": "skip", "reason": "Content is fresh"}

    # Check known strategies (try both filename and relative path)
    for pattern, strategy in KNOWN_STRATEGIES.items():
        if rel == pattern or rel_to_apps == pattern or file_path.name == pattern.split("/")[-1]:
            # Only match if the full pattern matches for path-based patterns
            if "/" in pattern:
                if rel_to_apps == pattern:
                    return {"method": "script", **strategy}
            else:
                if rel == pattern:
                    return {"method": "script", **strategy}

    # Unknown file → LLM inline rewrite
    return {"method": "llm", "description": f"LLM rewrite of {rel}"}


# ── Validation ──

def validate_data_output(original, refreshed):
    """Validate that refreshed data preserves the schema of the original.

    Checks: same top-level keys, non-empty, reasonable size ratio.
    """
    if not refreshed:
        return {"valid": False, "reason": "Empty output"}

    if not isinstance(refreshed, type(original)):
        return {"valid": False, "reason": f"Type mismatch: expected {type(original).__name__}, got {type(refreshed).__name__}"}

    if isinstance(original, dict) and isinstance(refreshed, dict):
        orig_keys = set(original.keys())
        new_keys = set(refreshed.keys())

        # Refreshed must have at least 50% of original top-level keys
        if orig_keys:
            overlap = orig_keys & new_keys
            if len(overlap) / len(orig_keys) < 0.5:
                return {"valid": False,
                        "reason": f"Schema mismatch: original keys {orig_keys}, refreshed keys {new_keys}"}

    # Size check — refreshed shouldn't be drastically smaller
    orig_size = len(json.dumps(original))
    new_size = len(json.dumps(refreshed))
    if orig_size > 100 and new_size < orig_size * 0.1:
        return {"valid": False,
                "reason": f"Output too small: {new_size} bytes vs original {orig_size} bytes"}

    return {"valid": True, "reason": "OK"}


# ── Archive ──

def archive_data_file(file_path, archive_dir, generation=1):
    """Archive a data file before overwriting.

    Returns the archive path.
    """
    file_path = Path(file_path)
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    stem = file_path.stem
    ext = file_path.suffix
    archive_path = archive_dir / f"{stem}-v{generation}{ext}"

    shutil.copy2(file_path, archive_path)
    log(f"Archived {file_path.name} → {archive_path.name}")
    return archive_path


# ── Generation Tracking ──

def track_data_molt(state_file, filename, generation, strategy, issues=None):
    """Track a data molt in the state file."""
    state_file = Path(state_file)

    if state_file.exists():
        state = json.loads(state_file.read_text())
    else:
        state = {"files": {}, "total_molts": 0, "created": datetime.now().isoformat()}

    if filename not in state["files"]:
        state["files"][filename] = {"generation": 0, "history": []}

    entry = state["files"][filename]
    entry["generation"] = generation
    entry["last_molted"] = datetime.now().isoformat()
    entry["history"].append({
        "generation": generation,
        "date": datetime.now().isoformat(),
        "strategy": strategy,
        "issues": issues or [],
    })

    state["total_molts"] = state.get("total_molts", 0) + 1
    state_file.write_text(json.dumps(state, indent=2))
    log(f"Tracked {filename} at generation {generation}")


# ── LLM Inline Molt ──

def molt_inline(file_path, ecosystem_context=None):
    """Use LLM to rewrite a data file's content directly.

    For unknown file types that don't have a dedicated generation script.
    Preserves schema, refreshes values.
    """
    from copilot_utils import copilot_call, parse_llm_json

    file_path = Path(file_path)
    content = file_path.read_text(errors="replace")
    ctx = ecosystem_context or {}

    # For large files, send a schema sample + instructions
    if len(content) > 8000:
        sample = content[:4000] + "\n...[truncated at 4000 chars]...\n" + content[-2000:]
    else:
        sample = content

    prompt = f"""Refresh this data file with new, unique content while preserving the exact schema.

File: {file_path.name}
Ecosystem context: {ctx.get('total_apps', '?')} apps, frame {ctx.get('frame', '?')}

Current content:
```
{sample}
```

Rules:
1. PRESERVE the exact JSON schema (same keys, same structure, same types)
2. REPLACE all text content with fresh, unique, contextual content
3. UPDATE any timestamps to current
4. EXPAND coverage if the data seems incomplete
5. NO duplicate text — every string value must be unique
6. Return ONLY the complete JSON — no explanation, no markdown fences

Return the refreshed JSON:"""

    raw = copilot_call(prompt, timeout=60)
    result = parse_llm_json(raw) if raw else None
    return result


# ── Main Pipeline ──

def molt_data_file(file_path, apps_dir, ecosystem_context=None, dry_run=False):
    """Full pipeline for a single data file: analyze → route → molt → validate → archive → track."""
    file_path = Path(file_path)
    apps_dir = Path(apps_dir)
    rel_name = file_path.name

    # Use paths relative to apps_dir for portability (tests use temp dirs)
    archive_dir = apps_dir / "archive" / "data"
    state_file = apps_dir / "data-molt-state.json"

    log(f"Processing {rel_name}")

    # 1. Analyze staleness
    analysis = analyze_staleness(file_path, ecosystem_context)
    log(f"  Analysis: stale={analysis['stale']}, score={analysis['score']}, "
        f"strategy={analysis['strategy']}, issues={analysis['issues']}")

    # 2. Route
    route = route_strategy(file_path, analysis)
    log(f"  Route: {route['method']}")

    if route["method"] == "skip":
        return {"action": "skipped", "file": rel_name, "reason": route.get("reason", ""),
                "analysis": analysis}

    if dry_run:
        return {"action": "would_molt", "file": rel_name, "route": route,
                "analysis": analysis}

    # 3. Execute
    if route["method"] == "script":
        # Run the existing generation script
        script_path = SCRIPTS_DIR / route["script"]
        if not script_path.exists():
            return {"action": "error", "file": rel_name,
                    "error": f"Script not found: {route['script']}"}

        cmd = [sys.executable, str(script_path)] + route.get("args", [])
        if VERBOSE:
            cmd.append("--verbose")
        log(f"  Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=300, cwd=ROOT)
            if result.returncode != 0:
                log(f"  Script failed: {result.stderr[:200]}")
                return {"action": "error", "file": rel_name,
                        "error": result.stderr[:500]}
            log(f"  Script succeeded")
        except subprocess.TimeoutExpired:
            return {"action": "error", "file": rel_name,
                    "error": "Script timed out after 300s"}

        action = "regenerated"

    elif route["method"] == "llm":
        # Read original for validation
        original = json.loads(file_path.read_text()) if file_path.suffix == ".json" else None

        # LLM inline rewrite
        refreshed = molt_inline(file_path, ecosystem_context)
        if not refreshed:
            return {"action": "error", "file": rel_name,
                    "error": "LLM returned no content"}

        # Validate
        if original:
            validation = validate_data_output(original, refreshed)
            if not validation["valid"]:
                log(f"  Validation failed: {validation['reason']}")
                return {"action": "rejected", "file": rel_name,
                        "reason": validation["reason"]}

        # Archive
        state = {}
        if state_file.exists():
            state = json.loads(state_file.read_text())
        gen = state.get("files", {}).get(rel_name, {}).get("generation", 0) + 1
        archive_data_file(file_path, archive_dir, generation=gen)

        # Write refreshed content
        file_path.write_text(json.dumps(refreshed, indent=2) if isinstance(refreshed, (dict, list)) else str(refreshed))
        log(f"  Wrote refreshed {rel_name}")

        action = "molted"

    else:
        return {"action": "skipped", "file": rel_name, "reason": "Unknown method"}

    # 4. Track
    state = {}
    if state_file.exists():
        state = json.loads(state_file.read_text())
    gen = state.get("files", {}).get(rel_name, {}).get("generation", 0) + 1
    track_data_molt(state_file, rel_name, generation=gen,
                    strategy=route["method"], issues=analysis.get("issues", []))

    return {"action": action, "file": rel_name, "analysis": analysis, "route": route}


def _load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"files": {}, "total_molts": 0}


# ── CLI ──

def molt_all(apps_dir=None, dry_run=False, target_file=None):
    """Discover and molt all stale data files."""
    apps_dir = Path(apps_dir or APPS_DIR)

    # Build ecosystem context
    manifest_path = apps_dir / "manifest.json"
    molter_state_path = apps_dir / "molter-state.json"

    total_apps = 0
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for cat in manifest.get("categories", {}).values():
            total_apps += len(cat.get("apps", []))

    frame = 0
    if molter_state_path.exists():
        ms = json.loads(molter_state_path.read_text())
        frame = ms.get("frame", 0)

    context = {"total_apps": total_apps, "frame": frame}
    print(f"Ecosystem: {total_apps} apps, frame {frame}")

    if target_file:
        # Molt a specific file
        target = apps_dir / target_file
        if not target.exists():
            # Try relative paths
            for f in discover_data_files(apps_dir):
                if f.name == target_file or str(f).endswith(target_file):
                    target = f
                    break
        if not target.exists():
            print(f"ERROR: File not found: {target_file}")
            return []
        files = [target]
    else:
        files = discover_data_files(apps_dir)

    print(f"Discovered {len(files)} data files")

    results = []
    for f in files:
        result = molt_data_file(f, apps_dir, ecosystem_context=context, dry_run=dry_run)
        results.append(result)
        status = result["action"]
        icon = {"skipped": "⏭", "molted": "✅", "regenerated": "🔄",
                "rejected": "❌", "error": "💥", "would_molt": "🔍"}.get(status, "?")
        print(f"  {icon} {result['file']}: {status}")
        if result.get("error"):
            print(f"     Error: {result['error'][:100]}")

    # Summary
    actions = [r["action"] for r in results]
    print(f"\nSummary: {len(results)} files processed")
    for action in set(actions):
        print(f"  {action}: {actions.count(action)}")

    return results


def show_status():
    """Print current data molt state."""
    if not STATE_FILE.exists():
        print("No data molt state found. Run `data_molt.py --molt` first.")
        return

    state = json.loads(STATE_FILE.read_text())
    print(f"Data Molt State")
    print(f"  Total molts: {state.get('total_molts', 0)}")
    print(f"  Files tracked: {len(state.get('files', {}))}")
    print()

    for filename, info in sorted(state.get("files", {}).items()):
        gen = info.get("generation", 0)
        last = info.get("last_molted", "never")
        print(f"  {filename}: gen {gen}, last molted {last}")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    do_molt = "--molt" in args
    target = None

    for i, arg in enumerate(args):
        if arg == "--file" and i + 1 < len(args):
            target = args[i + 1]

    if "--status" in args:
        show_status()
        return

    if do_molt or target:
        results = molt_all(dry_run=dry_run, target_file=target)

        if "--push" in args and not dry_run:
            print("\nCommitting and pushing...")
            subprocess.run(["git", "add", "-A"], cwd=ROOT)
            subprocess.run(["git", "commit", "-m",
                            "chore: data molt — refresh stale ecosystem data"],
                           cwd=ROOT)
            subprocess.run(["git", "push"], cwd=ROOT)
            print("Pushed!")
    else:
        # Default: analyze only (dry run)
        print("Analyzing data files (use --molt to apply changes)...")
        molt_all(dry_run=True)


if __name__ == "__main__":
    main()
