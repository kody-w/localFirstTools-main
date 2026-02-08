#!/usr/bin/env python3
"""
molt.py -- Molting Generations Pipeline for localFirstTools-main

Iteratively improves self-contained HTML apps using Claude Opus 4.6 via
GitHub Copilot CLI. Each "molt" sheds technical debt while preserving
functionality, archives the original, and tracks generation history.

Usage:
  python3 scripts/molt.py memory-training-game.html          # Molt one app
  python3 scripts/molt.py --category games_puzzles            # Molt all in category
  python3 scripts/molt.py memory-training-game.html --dry-run # Preview only
  python3 scripts/molt.py --status                            # Show generation table
  python3 scripts/molt.py --rollback memory-training-game 1   # Restore v1
"""

import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

# Import shared utilities
from copilot_utils import (
    APPS_DIR,
    MANIFEST_PATH,
    ROOT,
    VALID_CATEGORIES,
    copilot_call,
    detect_backend,
    load_manifest,
    parse_llm_html,
    save_manifest,
)

MAX_INPUT_SIZE = 100_000  # 100KB
DEFAULT_MAX_GEN = 5
SIZE_RATIO_MIN = 0.3
SIZE_RATIO_MAX = 3.0

ARCHIVE_DIR = APPS_DIR / "archive"

# ─── Generation Focus Areas ──────────────────────────────────────────────────

GENERATION_FOCUS = {
    1: {
        "name": "structural",
        "instructions": (
            "Focus on STRUCTURAL improvements:\n"
            "- Ensure proper <!DOCTYPE html>, <meta charset>, <meta viewport>\n"
            "- Add lang=\"en\" to <html> if missing\n"
            "- Replace var with const/let as appropriate\n"
            "- Use semantic HTML elements (main, nav, section, article, header, footer)\n"
            "- Remove dead code, unused variables, commented-out blocks\n"
            "- Add <noscript> fallback if missing\n"
            "- Remove console.log/debug statements (keep console.error/warn)\n"
            "- Ensure proper <title> and <meta name=\"description\">"
        ),
    },
    2: {
        "name": "accessibility",
        "instructions": (
            "Focus on ACCESSIBILITY improvements:\n"
            "- Add ARIA labels to interactive elements\n"
            "- Ensure keyboard navigation works (tabindex, keydown handlers)\n"
            "- Add role attributes to custom widgets\n"
            "- Ensure sufficient color contrast (WCAG AA)\n"
            "- Add focus indicators (:focus-visible styles)\n"
            "- Add alt text to images, aria-label to icon buttons\n"
            "- Ensure screen reader compatibility\n"
            "- Add skip-to-content link if applicable"
        ),
    },
    3: {
        "name": "performance",
        "instructions": (
            "Focus on PERFORMANCE improvements:\n"
            "- Use requestAnimationFrame for animations instead of setInterval/setTimeout\n"
            "- Use CSS transforms/opacity for animations instead of top/left/width/height\n"
            "- Debounce resize/scroll/input event handlers\n"
            "- Minimize DOM queries (cache getElementById results)\n"
            "- Use CSS will-change for animated elements\n"
            "- Ensure responsive design (works on mobile and desktop)\n"
            "- Use efficient CSS selectors\n"
            "- Lazy-initialize heavy resources"
        ),
    },
    4: {
        "name": "polish",
        "instructions": (
            "Focus on POLISH improvements:\n"
            "- Add try/catch error handling around risky operations\n"
            "- Handle edge cases (empty state, overflow, invalid input)\n"
            "- Consistent naming conventions throughout\n"
            "- Reduce DRY violations (extract repeated patterns)\n"
            "- Improve code organization (group related functions)\n"
            "- Use addEventListener instead of inline onclick handlers\n"
            "- Add meaningful comments only where logic is non-obvious\n"
            "- Ensure localStorage operations have error handling"
        ),
    },
    5: {
        "name": "refinement",
        "instructions": (
            "Focus on FINAL REFINEMENT:\n"
            "- Micro-optimize any remaining inefficiencies\n"
            "- Ensure consistent code style throughout\n"
            "- Remove any unnecessary comments or dead paths\n"
            "- Verify all event listeners are properly cleaned up\n"
            "- Check for memory leaks (dangling references, unclosed intervals)\n"
            "- Ensure graceful degradation\n"
            "- Final coherence pass: does every part of the code fit together cleanly?"
        ),
    },
}


def get_generation_focus(generation):
    """Return the focus area name for a given generation number."""
    if generation in GENERATION_FOCUS:
        return GENERATION_FOCUS[generation]["name"]
    return "refinement"


def _get_focus_instructions(generation):
    """Return the focus instructions for a given generation."""
    if generation in GENERATION_FOCUS:
        return GENERATION_FOCUS[generation]["instructions"]
    return GENERATION_FOCUS[5]["instructions"]


# ─── Prompt Construction ─────────────────────────────────────────────────────


def build_molt_prompt(html, filename, generation):
    """Build a generation-aware improvement prompt."""
    focus = get_generation_focus(generation)
    instructions = _get_focus_instructions(generation)

    return f"""You are an expert HTML developer performing generation {generation} improvements on a self-contained HTML application.

GENERATION {generation} FOCUS: {focus.upper()}

{instructions}

HARD RULES:
1. Return ONLY the complete rewritten HTML file -- no explanation, no markdown
2. Do NOT add new features or change what the app does
3. Must remain a single self-contained .html file
4. No external dependencies (no CDN links, no external JS/CSS files)
5. Must have <!DOCTYPE html>, <title>, <meta name="viewport">
6. Preserve all existing user-facing behavior exactly
7. If the app uses localStorage, keep that working identically
8. Do not remove any user-facing UI elements

BUG PREVENTION (critical -- violating these causes the molt to be rejected):
- Never use CSS var() without quotes in JavaScript: WRONG: {{ color: var(--x) }}  RIGHT: {{ color: 'var(--x)' }}
- Never comment out closing braces: WRONG: // }}  RIGHT: }}
- Never put // inside template literal expressions: WRONG: ${{x// }}  RIGHT: ${{x}}
- Never use optional chaining as assignment target: WRONG: el?.value = x  RIGHT: if (el) el.value = x
- Escape </script> inside JS string literals as <\\/script>
- Ensure every {{ has a matching }} -- unbalanced braces crash the app
- Ensure every try has a catch or finally
- Use double quotes for strings containing apostrophes: "There's" not 'There's'

Filename: {filename}

HTML content:
---
{html}
---

Return ONLY the complete rewritten HTML."""


# ─── JS Syntax Validation ────────────────────────────────────────────────────

# Script types that are not JavaScript and should be skipped
_SKIP_SCRIPT_TYPES = {"x-shader/x-vertex", "x-shader/x-fragment", "importmap",
                      "application/json", "application/ld+json"}


def _check_js_syntax(html):
    """Run Node.js vm.Script on each <script> block to catch syntax errors.

    Returns None if all blocks parse OK, or an error string if any fail.
    Skips shader scripts, importmap, JSON, and module scripts.
    """
    import subprocess as _sp

    # Extract regular (non-module, non-special) script blocks
    blocks = []
    for match in re.finditer(r"<script([^>]*)>([\s\S]*?)</script>", html, re.IGNORECASE):
        attrs = match.group(1)
        code = match.group(2).strip()
        if not code:
            continue
        # Skip non-JS types
        type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', attrs)
        if type_match:
            stype = type_match.group(1).lower()
            if any(stype.startswith(skip) for skip in _SKIP_SCRIPT_TYPES):
                continue
            if stype == "module":
                continue  # Module scripts have import/export that vm.Script can't parse
        blocks.append(code)

    if not blocks:
        return None

    # Check each block with Node.js vm.Script
    for code in blocks:
        check_js = (
            "const vm=require('vm');"
            "try{new vm.Script(process.argv[1]);process.exit(0)}"
            "catch(e){if(e instanceof SyntaxError)"
            "{process.stderr.write(e.message);process.exit(1)}process.exit(0)}"
        )
        try:
            result = _sp.run(
                ["node", "-e", check_js, code],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                err = result.stderr.strip().split("\n")[0] if result.stderr.strip() else "Unknown"
                return err
        except (FileNotFoundError, _sp.TimeoutExpired):
            # Node not available or timeout -- skip validation gracefully
            return None

    return None


def validate_molt_output(html, original_size):
    """Validate molted HTML output. Returns None if valid, error string if not."""
    if not html:
        return "Empty or None output"

    if len(html.strip()) == 0:
        return "Empty output after stripping"

    # Check DOCTYPE
    if "<!doctype html>" not in html.lower()[:200]:
        return "Missing <!DOCTYPE html>"

    # Check title
    if not re.search(r"<title>.+?</title>", html, re.IGNORECASE | re.DOTALL):
        return "Missing or empty <title>"

    # Check for external dependencies
    ext_script = re.search(
        r'<script[^>]+src\s*=\s*["\']https?://', html, re.IGNORECASE
    )
    if ext_script:
        return f"External script dependency detected: {ext_script.group()[:80]}"

    ext_css = re.search(
        r'<link[^>]+href\s*=\s*["\']https?://[^"\']*\.css', html, re.IGNORECASE
    )
    if ext_css:
        return f"External stylesheet dependency detected: {ext_css.group()[:80]}"

    # ── JS syntax validation ────────────────────────────────────────────────
    js_error = _check_js_syntax(html)
    if js_error:
        return f"JavaScript syntax error: {js_error}"

    # Check size ratio
    new_size = len(html)
    if original_size > 0:
        ratio = new_size / original_size
        if ratio < SIZE_RATIO_MIN:
            return f"Output too small: {new_size} bytes is {ratio:.1%} of original {original_size} bytes (min {SIZE_RATIO_MIN:.0%})"
        if ratio > SIZE_RATIO_MAX:
            return f"Output too large: {new_size} bytes is {ratio:.1%} of original {original_size} bytes (max {SIZE_RATIO_MAX:.0%})"

    return None


# ─── Archive Operations ──────────────────────────────────────────────────────


def archive_file(src_path, archive_dir, generation):
    """Copy the current file to the archive as v<generation>.html."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"v{generation}.html"
    shutil.copy2(src_path, dest)
    return dest


def append_molt_log(archive_dir, entry):
    """Append an entry to the molt audit log."""
    log_path = archive_dir / "molt-log.json"
    if log_path.exists():
        log = json.loads(log_path.read_text())
    else:
        log = []
    log.append(entry)
    log_path.write_text(json.dumps(log, indent=2))


# ─── Manifest Updates ────────────────────────────────────────────────────────


def update_manifest_entry(app_entry, generation, size):
    """Add molt tracking fields to a manifest app entry."""
    app_entry["generation"] = generation
    app_entry["lastMolted"] = date.today().isoformat()

    if "moltHistory" not in app_entry:
        app_entry["moltHistory"] = []

    app_entry["moltHistory"].append({
        "gen": generation,
        "date": date.today().isoformat(),
        "size": size,
    })


# ─── App Resolution ──────────────────────────────────────────────────────────


def resolve_app(identifier, _manifest=None, _apps_dir=None):
    """Find an app by filename (with or without .html extension).

    Returns (path, category_key, app_entry).
    Raises FileNotFoundError if not found.
    """
    manifest = _manifest or load_manifest()
    apps_dir = _apps_dir or APPS_DIR

    # Normalize: add .html if missing
    if not identifier.endswith(".html"):
        identifier = identifier + ".html"

    for cat_key, cat_data in manifest["categories"].items():
        for app_entry in cat_data["apps"]:
            if app_entry["file"] == identifier:
                folder = cat_data["folder"]
                path = apps_dir / folder / identifier
                if path.exists():
                    return path, cat_key, app_entry
                # Entry exists in manifest but file missing
                raise FileNotFoundError(
                    f"Manifest entry found for '{identifier}' in {cat_key}, "
                    f"but file not found at {path}"
                )

    raise FileNotFoundError(
        f"No manifest entry found for '{identifier}'. "
        "Check the filename or add it to manifest.json first."
    )


# ─── Core Molt Pipeline ─────────────────────────────────────────────────────


def molt_app(
    identifier,
    dry_run=False,
    verbose=False,
    max_gen=DEFAULT_MAX_GEN,
    max_size=MAX_INPUT_SIZE,
    _manifest=None,
    _apps_dir=None,
):
    """Molt a single app through one generation.

    Returns a dict with status and details.
    """
    manifest = _manifest or load_manifest()
    apps_dir = _apps_dir or APPS_DIR
    archive_base = apps_dir / "archive"

    # Resolve the app
    try:
        path, cat_key, app_entry = resolve_app(
            identifier, _manifest=manifest, _apps_dir=apps_dir
        )
    except FileNotFoundError as e:
        return {"status": "failed", "reason": str(e)}

    filename = path.name
    stem = path.stem
    current_gen = app_entry.get("generation", 0)
    next_gen = current_gen + 1

    if verbose:
        print(f"  File: {path}")
        print(f"  Category: {cat_key}")
        print(f"  Current generation: {current_gen}")
        print(f"  Next generation: {next_gen}")

    # Check max generation cap
    if current_gen >= max_gen:
        reason = f"Already at max generation {current_gen} (cap: {max_gen})"
        if verbose:
            print(f"  SKIP: {reason}")
        return {"status": "skipped", "reason": reason}

    # Read current content
    html = path.read_text(encoding="utf-8", errors="replace")
    original_size = len(html)

    # Check file size cap
    if original_size > max_size:
        reason = f"File too large: {original_size} bytes (max {max_size})"
        if verbose:
            print(f"  SKIP: {reason}")
        return {"status": "skipped", "reason": reason}

    focus = get_generation_focus(next_gen)
    if verbose:
        print(f"  Focus: {focus}")
        print(f"  Original size: {original_size} bytes")

    # Build prompt and call LLM
    prompt = build_molt_prompt(html, filename, next_gen)

    if dry_run:
        if verbose:
            print(f"  DRY RUN: would send {len(prompt)} char prompt to Copilot")
            print(f"  DRY RUN: would archive to {archive_base / stem}/v{next_gen}.html")
        return {
            "status": "dry_run",
            "file": filename,
            "category": cat_key,
            "generation": next_gen,
            "focus": focus,
        }

    if verbose:
        print(f"  Calling Copilot CLI...")

    # Scale timeout with file size: 180s base + 60s per MB
    timeout_secs = max(180, 180 + int(original_size / 1_000_000) * 60)
    raw_output = copilot_call(prompt, timeout=timeout_secs)
    if verbose and raw_output:
        print(f"  Raw output length: {len(raw_output)} chars")
        print(f"  Raw output preview: {raw_output[:300]}...")
    improved_html = parse_llm_html(raw_output)

    if not improved_html:
        return {
            "status": "failed",
            "reason": "Copilot returned empty or unparseable response",
            "file": filename,
        }

    # Validate output
    error = validate_molt_output(improved_html, original_size)
    if error:
        if verbose:
            print(f"  REJECTED: {error}")
        return {
            "status": "rejected",
            "reason": error,
            "file": filename,
            "generation": next_gen,
        }

    new_size = len(improved_html)
    if verbose:
        print(f"  New size: {new_size} bytes ({new_size - original_size:+d})")

    # Archive the original
    archive_dir = archive_base / stem
    archive_file(path, archive_dir, next_gen)
    if verbose:
        print(f"  Archived: {archive_dir}/v{next_gen}.html")

    # Write improved version
    path.write_text(improved_html, encoding="utf-8")
    if verbose:
        print(f"  Replaced: {path}")

    # Write audit log
    prev_sha = hashlib.sha256(html.encode()).hexdigest()
    new_sha = hashlib.sha256(improved_html.encode()).hexdigest()
    append_molt_log(archive_dir, {
        "generation": next_gen,
        "date": date.today().isoformat(),
        "previousSize": original_size,
        "newSize": new_size,
        "previousSha256": prev_sha,
        "newSha256": new_sha,
        "focus": focus,
    })

    # Update manifest entry
    update_manifest_entry(app_entry, next_gen, new_size)

    return {
        "status": "success",
        "file": filename,
        "category": cat_key,
        "generation": next_gen,
        "focus": focus,
        "previousSize": original_size,
        "newSize": new_size,
    }


# ─── Status ──────────────────────────────────────────────────────────────────


def get_status(manifest=None):
    """Return a list of all apps with their generation info."""
    manifest = manifest or load_manifest()
    status = []
    for cat_key, cat_data in manifest["categories"].items():
        for app in cat_data["apps"]:
            status.append({
                "file": app["file"],
                "category": cat_key,
                "title": app.get("title", ""),
                "generation": app.get("generation", 0),
                "lastMolted": app.get("lastMolted", ""),
            })
    return status


def print_status(manifest=None):
    """Print a formatted generation status table."""
    status = get_status(manifest)
    status.sort(key=lambda s: (-s["generation"], s["category"], s["file"]))

    print(f"\n{'File':<45} {'Category':<20} {'Gen':>3} {'Last Molted':<12}")
    print("-" * 82)
    for s in status:
        gen = s["generation"]
        last = s["lastMolted"] or "never"
        print(f"{s['file']:<45} {s['category']:<20} {gen:>3} {last:<12}")

    total = len(status)
    molted = sum(1 for s in status if s["generation"] > 0)
    print(f"\n{molted}/{total} apps have been molted.")


# ─── Rollback ────────────────────────────────────────────────────────────────


def rollback_app(identifier, target_gen, _manifest=None, _apps_dir=None):
    """Roll back an app to a specific archived generation."""
    manifest = _manifest or load_manifest()
    apps_dir = _apps_dir or APPS_DIR

    # Normalize
    if not identifier.endswith(".html"):
        stem = identifier
    else:
        stem = identifier.replace(".html", "")

    archive_path = apps_dir / "archive" / stem / f"v{target_gen}.html"

    if not archive_path.exists():
        return {
            "status": "failed",
            "reason": f"Archive version v{target_gen} not found at {archive_path}",
        }

    # Find the live file
    try:
        live_path, cat_key, app_entry = resolve_app(
            stem, _manifest=manifest, _apps_dir=apps_dir
        )
    except FileNotFoundError as e:
        return {"status": "failed", "reason": str(e)}

    # Restore
    archived_html = archive_path.read_text(encoding="utf-8")
    live_path.write_text(archived_html, encoding="utf-8")

    return {
        "status": "rolled_back",
        "file": live_path.name,
        "restoredGeneration": target_gen,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or dry_run

    # Strip flags from args
    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}

    # Parse --max-gen N
    max_gen = DEFAULT_MAX_GEN
    if "--max-gen" in args:
        idx = args.index("--max-gen")
        if idx + 1 < len(args):
            max_gen = int(args[idx + 1])

    # Parse --max-size N (bytes)
    max_size = MAX_INPUT_SIZE
    if "--max-size" in args:
        idx = args.index("--max-size")
        if idx + 1 < len(args):
            max_size = int(args[idx + 1])

    # Parse --category <key>
    category = None
    if "--category" in args:
        idx = args.index("--category")
        if idx + 1 < len(args):
            category = args[idx + 1]

    # ── Status mode ──
    if "--status" in flags:
        print_status()
        return 0

    # ── Rollback mode ──
    if "--rollback" in flags:
        if len(positional) < 2:
            print("Usage: molt.py --rollback <app-name> <generation>")
            return 1
        app_name = positional[0]
        target_gen = int(positional[1])
        result = rollback_app(app_name, target_gen)
        if result["status"] == "rolled_back":
            print(f"Rolled back {result['file']} to generation {result['restoredGeneration']}")
            return 0
        else:
            print(f"Rollback failed: {result['reason']}")
            return 1

    # ── Check backend ──
    backend = detect_backend()
    if backend != "copilot-cli" and not dry_run:
        print("ERROR: Copilot CLI not available. Install gh + copilot extension.")
        print("  Or use --dry-run to preview without LLM calls.")
        return 1

    print(f"molt: backend = {backend}")
    print(f"molt: max generations = {max_gen}")
    if dry_run:
        print("molt: DRY RUN MODE")

    manifest = load_manifest()

    # ── Category mode ──
    if category:
        if category not in manifest["categories"]:
            print(f"ERROR: Category '{category}' not found in manifest.")
            return 1

        apps = manifest["categories"][category]["apps"]
        print(f"\nmolt: processing {len(apps)} apps in {category}")

        results = {"success": 0, "skipped": 0, "failed": 0, "rejected": 0, "dry_run": 0}
        for app in apps:
            print(f"\n--- {app['file']} ---")
            result = molt_app(
                app["file"],
                dry_run=dry_run,
                verbose=verbose,
                max_gen=max_gen,
                max_size=max_size,
                _manifest=manifest,
            )
            results[result["status"]] = results.get(result["status"], 0) + 1
            print(f"  => {result['status']}")

        if not dry_run:
            save_manifest(manifest)

        print(f"\nmolt: {results}")
        return 0

    # ── Single app mode ──
    if not positional:
        print("Usage: molt.py <app-file> [--dry-run] [--verbose] [--max-gen N] [--max-size N]")
        print("       molt.py --category <category_key>")
        print("       molt.py --status")
        print("       molt.py --rollback <app-name> <generation>")
        return 1

    app_file = positional[0]
    print(f"\n--- Molting: {app_file} ---")

    result = molt_app(
        app_file,
        dry_run=dry_run,
        verbose=verbose,
        max_gen=max_gen,
        max_size=max_size,
        _manifest=manifest,
    )

    if result["status"] == "success":
        save_manifest(manifest)
        print(f"\nSUCCESS: {result['file']} molted to generation {result['generation']}")
        print(f"  Focus: {result['focus']}")
        print(f"  Size: {result['previousSize']} -> {result['newSize']} bytes")
    elif result["status"] == "dry_run":
        print(f"\nDRY RUN: {result['file']} would molt to generation {result['generation']}")
        print(f"  Focus: {result['focus']}")
    elif result["status"] == "skipped":
        print(f"\nSKIPPED: {result['reason']}")
    elif result["status"] == "rejected":
        print(f"\nREJECTED: {result['reason']}")
        print(f"  Original preserved.")
    else:
        print(f"\nFAILED: {result.get('reason', 'unknown error')}")

    return 0 if result["status"] in ("success", "dry_run") else 1


if __name__ == "__main__":
    sys.exit(main())
