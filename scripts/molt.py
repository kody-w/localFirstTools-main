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
    copilot_call_with_retry,
    detect_backend,
    load_manifest,
    parse_llm_html,
    save_manifest,
)

# Adaptive content identity (optional -- graceful if missing)
try:
    from content_identity import analyze as _analyze_content
except ImportError:
    _analyze_content = None

# Feature contract system (optional -- graceful if missing)
try:
    from feature_contract import extract_features, verify_features, format_contract_for_prompt
except ImportError:
    extract_features = None
    verify_features = None
    format_contract_for_prompt = None

MAX_INPUT_SIZE = 100_000  # 100KB
DEFAULT_MAX_GEN = 5
SIZE_RATIO_MIN = 0.3
SIZE_RATIO_MAX = 3.0
SCORE_DROP_THRESHOLD = 10  # auto-rollback if score drops more than this
FEATURE_SCORE_DROP_THRESHOLD = 5  # rollback if drop>5 AND features missing
COOLDOWN_MIN_GEN_FOR_THRESHOLD = 3  # after gen 3, apply "good enough" threshold
GOOD_ENOUGH_SCORE = 70  # apps scoring this+ are skipped unless forced

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


def build_adaptive_molt_prompt(html, filename, identity):
    """Build a content-aware improvement prompt using Content Identity.

    THE MEDIUM IS THE MESSAGE: instead of fixed generation focuses,
    the improvement direction comes from what the content actually IS.
    """
    medium = identity.get("medium", "HTML application")
    purpose = identity.get("purpose", "unknown purpose")
    strengths = ", ".join(identity.get("strengths", []))
    weaknesses = ", ".join(identity.get("weaknesses", []))
    vectors = identity.get("improvement_vectors", [])
    target = vectors[0] if vectors else "general quality improvement"

    return f"""You are an expert developer improving a self-contained HTML application.

THIS IS A: {medium}
IT DOES: {purpose}

STRENGTHS (preserve these): {strengths}
WEAKNESSES (address these): {weaknesses}

YOUR TASK: {target}

This is not a generic improvement. You are making this {medium} better at being
a {medium}. The improvement should be specific to what this content IS.

HARD RULES:
1. Return ONLY the complete rewritten HTML file -- no explanation, no markdown
2. Must remain a single self-contained .html file
3. No external dependencies (no CDN links, no external JS/CSS files)
4. Must have <!DOCTYPE html>, <title>, <meta name="viewport">
5. Preserve all existing user-facing behavior exactly
6. If the app uses localStorage, keep that working identically
7. Do not remove any user-facing UI elements
8. Focus your changes on the specific improvement target above

BUG PREVENTION (critical -- violating these causes the molt to be rejected):
- Never use CSS var() without quotes in JavaScript
- Never comment out closing braces
- Escape </script> inside JS string literals as <\\/script>
- Ensure every {{ has a matching }}
- Ensure every try has a catch or finally

Filename: {filename}

HTML content:
---
{html}
---

Return ONLY the complete rewritten HTML."""


def build_surgical_molt_prompt(html, filename, identity, contract):
    """Build a prompt that asks for surgical edits instead of a full rewrite.

    Returns a prompt that instructs the LLM to produce JSON edit instructions
    rather than regenerating the entire file. This prevents information loss
    by only touching what needs to change.
    """
    medium = identity.get("medium", "HTML application") if identity else "HTML application"
    purpose = identity.get("purpose", "unknown purpose") if identity else "unknown purpose"
    vectors = identity.get("improvement_vectors", []) if identity else []
    target = vectors[0] if vectors else "general quality improvement"
    weaknesses = ", ".join(identity.get("weaknesses", [])) if identity else ""

    contract_text = ""
    if contract and format_contract_for_prompt:
        contract_text = format_contract_for_prompt(contract)

    return f"""You are an expert developer making SURGICAL improvements to an HTML application.
Instead of rewriting the entire file, you will produce a list of specific edits.

THIS IS A: {medium}
IT DOES: {purpose}
WEAKNESS TO ADDRESS: {weaknesses}
YOUR TASK: {target}

{contract_text}

INSTRUCTIONS:
Return a JSON array of edit objects. Each edit has:
- "description": what this change does (string)
- "find": exact text to find in the source (string, must match exactly)
- "replace": text to replace it with (string)

Keep edits minimal and targeted. Do NOT rewrite large blocks.
Do NOT add new features — only improve what exists.
Each "find" string must appear EXACTLY ONCE in the source file.

Example response format:
```json
[
  {{
    "description": "Add ARIA label to start button",
    "find": "<button onclick=\\"startGame()\\">Start</button>",
    "replace": "<button onclick=\\"startGame()\\" aria-label=\\"Start game\\">Start</button>"
  }},
  {{
    "description": "Optimize particle loop",
    "find": "for (let i = 0; i < particles.length; i++) {{",
    "replace": "for (let i = particles.length - 1; i >= 0; i--) {{"
  }}
]
```

Return ONLY the JSON array — no explanation, no markdown fences, just the raw JSON.
Limit to 10 edits maximum. Each edit should be small and focused.

Filename: {filename}

HTML content:
---
{html}
---

Return ONLY the JSON array of edits."""


def apply_surgical_edits(html, edits_json):
    """Apply surgical edits from LLM response to HTML source.

    Args:
        html: Original HTML source
        edits_json: Raw JSON string from LLM (list of edit objects)

    Returns:
        (modified_html, applied_count, errors) tuple
    """
    try:
        edits = json.loads(edits_json)
    except (json.JSONDecodeError, TypeError):
        return None, 0, ["Failed to parse edits as JSON"]

    if not isinstance(edits, list):
        return None, 0, ["Edits response is not a list"]

    modified = html
    applied = 0
    errors = []

    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            errors.append(f"Edit {i}: not a dict")
            continue

        find = edit.get("find", "")
        replace = edit.get("replace", "")
        desc = edit.get("description", f"edit {i}")

        if not find:
            errors.append(f"Edit {i} ({desc}): empty 'find' string")
            continue

        count = modified.count(find)
        if count == 0:
            errors.append(f"Edit {i} ({desc}): 'find' text not found in source")
            continue
        if count > 1:
            errors.append(f"Edit {i} ({desc}): 'find' text matches {count} times (must be unique)")
            continue

        modified = modified.replace(find, replace, 1)
        applied += 1

    if applied == 0:
        return None, 0, errors

    return modified, applied, errors


def _score_app_if_available(path):
    """Try to score an app using rank_games. Returns score dict or None."""
    try:
        from rank_games import score_game
        content = path.read_text(encoding="utf-8", errors="replace")
        return score_game(path, content=content, legacy=True)
    except Exception:
        return None


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
    adaptive=True,
    surgical=False,
    use_contract=True,
    use_score_gate=True,
    force=False,
    _manifest=None,
    _apps_dir=None,
):
    """Molt a single app through one generation.

    Args:
        surgical: If True, use surgical edit mode (JSON patches) instead of full rewrite.
        use_contract: If True, extract feature contract before molt and verify after.
        use_score_gate: If True, auto-rollback if score drops significantly.
        force: If True, override cooldown and "good enough" threshold.

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

    # ── Cooldown: skip recently-molted and "good enough" apps ──
    if not force and current_gen >= COOLDOWN_MIN_GEN_FOR_THRESHOLD:
        # Score-based "good enough" check (uses rankings.json, not live scoring)
        try:
            rankings_path = apps_dir / "rankings.json"
            if rankings_path.exists():
                rankings = json.loads(rankings_path.read_text())
                for ranked in rankings.get("rankings", []):
                    if ranked.get("file") == filename:
                        current_score = ranked.get("score", 0)
                        if current_score >= GOOD_ENOUGH_SCORE:
                            reason = (
                                f"Score {current_score} >= {GOOD_ENOUGH_SCORE} "
                                f"at gen {current_gen} (use --force to override)"
                            )
                            if verbose:
                                print(f"  SKIP: {reason}")
                            return {"status": "skipped", "reason": reason}
                        break
        except Exception:
            pass  # rankings unavailable, continue

    # Read current content
    html = path.read_text(encoding="utf-8", errors="replace")
    original_size = len(html)

    # Check file size cap
    if original_size > max_size:
        reason = f"File too large: {original_size} bytes (max {max_size})"
        if verbose:
            print(f"  SKIP: {reason}")
        return {"status": "skipped", "reason": reason}

    # ── Feature contract extraction (before LLM call) ──
    contract = None
    if use_contract and extract_features is not None:
        contract = extract_features(html)
        if verbose and contract:
            n_features = len(contract.get("features", []))
            n_constants = len(contract.get("constants", {}))
            print(f"  Contract: {n_features} features, {n_constants} constants extracted")

    # Determine molt mode: adaptive (content-aware) or classic (generation-based)
    identity = None
    if adaptive and _analyze_content is not None:
        try:
            identity = _analyze_content(path, content=html)
        except Exception:
            pass

    # ── Build prompt (surgical or full rewrite) ──
    if surgical and identity and contract:
        focus = identity.get("improvement_vectors", ["general improvement"])[0]
        if verbose:
            print(f"  Mode: SURGICAL (medium: {identity.get('medium', '?')})")
            print(f"  Focus: {focus}")
            print(f"  Original size: {original_size} bytes")
        prompt = build_surgical_molt_prompt(html, filename, identity, contract)
    elif identity:
        focus = identity.get("improvement_vectors", ["general improvement"])[0]
        if verbose:
            print(f"  Mode: ADAPTIVE (medium: {identity.get('medium', '?')})")
            print(f"  Focus: {focus}")
            print(f"  Original size: {original_size} bytes")
        # Inject feature contract into adaptive prompt
        base_prompt = build_adaptive_molt_prompt(html, filename, identity)
        if contract and format_contract_for_prompt:
            contract_text = format_contract_for_prompt(contract)
            if contract_text:
                base_prompt = base_prompt.replace(
                    "HARD RULES:",
                    contract_text + "\n\nHARD RULES:",
                )
        prompt = base_prompt
    else:
        focus = get_generation_focus(next_gen)
        if verbose:
            if adaptive:
                print(f"  Mode: CLASSIC (adaptive unavailable)")
            else:
                print(f"  Mode: CLASSIC")
            print(f"  Focus: {focus}")
            print(f"  Original size: {original_size} bytes")
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
    raw_output = copilot_call_with_retry(prompt, timeout=timeout_secs)
    if verbose and raw_output:
        print(f"  Raw output length: {len(raw_output)} chars")
        print(f"  Raw output preview: {raw_output[:300]}...")

    # ── Parse response (surgical vs full rewrite) ──
    if surgical:
        improved_html, applied, errors = apply_surgical_edits(html, raw_output)
        if improved_html is None:
            # Fall back to full rewrite parsing
            if verbose:
                print(f"  Surgical failed ({errors}), trying full rewrite parse...")
            improved_html = parse_llm_html(raw_output)
        elif verbose:
            print(f"  Surgical: {applied} edits applied, {len(errors)} errors")
    else:
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

    # ── Feature contract verification (post-molt) ──
    contract_result = None
    if use_contract and contract and verify_features is not None:
        contract_result = verify_features(contract, improved_html)
        if verbose:
            ratio = contract_result["preservation_ratio"]
            n_missing = len(contract_result["missing"])
            print(f"  Contract: {ratio:.0%} preserved, {n_missing} missing")
        if not contract_result["passed"]:
            missing_summary = ", ".join(
                m["id"] for m in contract_result["missing"][:5]
            )
            reason = (
                f"Feature contract failed: {len(contract_result['missing'])} features missing "
                f"({contract_result['preservation_ratio']:.0%} preserved). "
                f"Missing: {missing_summary}"
            )
            if verbose:
                print(f"  REJECTED: {reason}")
            return {
                "status": "rejected",
                "reason": reason,
                "file": filename,
                "generation": next_gen,
                "contract_result": contract_result,
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

    # ── Score gate: auto-rollback on regression ──
    score_before = None
    score_after = None
    if use_score_gate:
        score_result = _score_app_if_available(path)
        if score_result:
            score_after = score_result.get("score", 0)
            # Check rankings for pre-molt score
            try:
                rankings_path = apps_dir / "rankings.json"
                if rankings_path.exists():
                    rankings = json.loads(rankings_path.read_text())
                    for ranked in rankings.get("rankings", []):
                        if ranked.get("file") == filename:
                            score_before = ranked.get("score", 0)
                            break
            except Exception:
                pass

            if score_before is not None:
                drop = score_before - score_after
                if verbose:
                    print(f"  Score gate: {score_before} -> {score_after} (delta: {-drop:+d})")

                should_rollback = False
                rollback_reason = ""

                if drop > SCORE_DROP_THRESHOLD:
                    should_rollback = True
                    rollback_reason = (
                        f"Score dropped {drop} points ({score_before}->{score_after}), "
                        f"exceeds threshold of {SCORE_DROP_THRESHOLD}"
                    )
                elif drop > FEATURE_SCORE_DROP_THRESHOLD and contract_result:
                    if contract_result.get("missing"):
                        should_rollback = True
                        rollback_reason = (
                            f"Score dropped {drop} points AND "
                            f"{len(contract_result['missing'])} features missing"
                        )

                if should_rollback:
                    # Restore from archive
                    archived = archive_dir / f"v{next_gen}.html"
                    if archived.exists():
                        path.write_text(html, encoding="utf-8")
                    if verbose:
                        print(f"  ROLLBACK: {rollback_reason}")
                    return {
                        "status": "rolled_back",
                        "reason": rollback_reason,
                        "file": filename,
                        "generation": next_gen,
                        "score_before": score_before,
                        "score_after": score_after,
                    }

    # Write audit log
    prev_sha = hashlib.sha256(html.encode()).hexdigest()
    new_sha = hashlib.sha256(improved_html.encode()).hexdigest()
    log_entry = {
        "generation": next_gen,
        "date": date.today().isoformat(),
        "previousSize": original_size,
        "newSize": new_size,
        "previousSha256": prev_sha,
        "newSha256": new_sha,
        "focus": focus,
        "mode": "surgical" if surgical else ("adaptive" if identity else "classic"),
    }
    if contract_result:
        log_entry["feature_preservation"] = contract_result["preservation_ratio"]
        log_entry["features_missing"] = len(contract_result["missing"])
    if score_before is not None and score_after is not None:
        log_entry["score_before"] = score_before
        log_entry["score_after"] = score_after
    append_molt_log(archive_dir, log_entry)

    # Update manifest entry
    update_manifest_entry(app_entry, next_gen, new_size)

    result = {
        "status": "success",
        "file": filename,
        "category": cat_key,
        "generation": next_gen,
        "focus": focus,
        "previousSize": original_size,
        "newSize": new_size,
    }
    if contract_result:
        result["feature_preservation"] = contract_result["preservation_ratio"]
    if score_before is not None:
        result["score_before"] = score_before
    if score_after is not None:
        result["score_after"] = score_after
    return result


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
    adaptive = "--classic" not in flags
    surgical = "--surgical" in flags
    use_contract = "--no-contract" not in flags
    use_score_gate = "--no-score-gate" not in flags
    force = "--force" in flags
    if surgical:
        print("molt: SURGICAL MODE (JSON patches)")
    elif adaptive:
        print("molt: ADAPTIVE MODE (content-aware)")
    else:
        print("molt: CLASSIC MODE (generation-based)")
    if use_contract:
        print("molt: feature contracts ENABLED")
    if use_score_gate:
        print("molt: score gate ENABLED")
    if force:
        print("molt: FORCE (cooldown override)")
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
                adaptive=adaptive,
                surgical=surgical,
                use_contract=use_contract,
                use_score_gate=use_score_gate,
                force=force,
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
        print("Usage: molt.py <app-file> [--dry-run] [--verbose] [--max-gen N] [--classic]")
        print("       molt.py --category <category_key>")
        print("       molt.py --status")
        print("       molt.py --rollback <app-name> <generation>")
        print("")
        print("  Modes:  --classic    Fixed 5-generation cycle")
        print("          --surgical   JSON patch edits (preserves untouched code)")
        print("  Guards: --no-contract   Skip feature contract verification")
        print("          --no-score-gate Skip score regression check")
        print("          --force         Override cooldown / good-enough threshold")
        return 1

    app_file = positional[0]
    print(f"\n--- Molting: {app_file} ---")

    result = molt_app(
        app_file,
        dry_run=dry_run,
        verbose=verbose,
        max_gen=max_gen,
        max_size=max_size,
        adaptive=adaptive,
        surgical=surgical,
        use_contract=use_contract,
        use_score_gate=use_score_gate,
        force=force,
        _manifest=manifest,
    )

    if result["status"] == "success":
        save_manifest(manifest)
        print(f"\nSUCCESS: {result['file']} molted to generation {result['generation']}")
        print(f"  Focus: {result['focus']}")
        print(f"  Size: {result['previousSize']} -> {result['newSize']} bytes")
        if "feature_preservation" in result:
            print(f"  Feature preservation: {result['feature_preservation']:.0%}")
        if "score_before" in result and "score_after" in result:
            print(f"  Score: {result['score_before']} -> {result['score_after']}")
    elif result["status"] == "rolled_back":
        print(f"\nROLLED BACK: {result['reason']}")
        if "score_before" in result:
            print(f"  Score: {result['score_before']} -> {result['score_after']}")
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
