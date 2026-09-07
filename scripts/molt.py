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

import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import date
from html.parser import HTMLParser
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
MAX_CANDIDATE_SIZE = int(MAX_INPUT_SIZE * SIZE_RATIO_MAX)
MAX_OBJECTIVE_SIZE = 2_000
MAX_CANDIDATE_TIMEOUT = 600
MAX_MANIFEST_SIZE = 10_000_000
MAX_MOLT_LOG_SIZE = 1_000_000
SYNTAX_TIMEOUT = 10

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


class _CandidateDocument(HTMLParser):
    """Collect executable source without running it or resolving dependencies."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.opened = set()
        self.closed = set()
        self.viewport = False
        self.scripts = []
        self.errors = []
        self.script_type = None
        self.script = []

    def handle_starttag(self, tag, attrs):
        self.opened.add(tag)
        if len(attrs) != len({name for name, _ in attrs}):
            self.errors.append(f"Duplicate attributes on <{tag}>")
        attrs = dict(attrs)
        if tag == "meta" and (attrs.get("name") or "").lower() == "viewport":
            self.viewport = bool(attrs.get("content"))
        if tag == "script":
            if "src" in attrs:
                self.errors.append("External script dependency: script src is not inline")
            self.script_type = (attrs.get("type") or "").lower().strip()
            self.script = []
        if tag == "link" and "stylesheet" in (attrs.get("rel") or "").lower().split():
            self.errors.append("External stylesheet dependency: stylesheet is not inline")
        for name, value in attrs.items():
            if name.startswith("on") and value:
                self.scripts.append(("handler", "(function(event){\n" + value + "\n})"))

    def handle_startendtag(self, tag, attrs):
        if tag == "script":
            self.errors.append("Self-closing <script> cannot be syntax checked safely")
        else:
            super().handle_startendtag(tag, attrs)

    def handle_data(self, data):
        if self.script_type is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        self.closed.add(tag)
        if tag == "script" and self.script_type is not None:
            code = "".join(self.script).strip()
            script_type = self.script_type.split(";", 1)[0].strip()
            if code and script_type in (
                "", "module", "text/javascript", "application/javascript",
                "text/ecmascript", "application/ecmascript",
                "application/x-ecmascript", "application/x-javascript",
                "text/x-ecmascript", "text/x-javascript", "text/jscript", "text/livescript",
                "text/javascript1.0", "text/javascript1.1", "text/javascript1.2",
                "text/javascript1.3", "text/javascript1.4", "text/javascript1.5",
            ):
                self.scripts.append((script_type, code))
            self.script_type = None
            self.script = []


def _check_candidate_syntax(html, evidence):
    import subprocess as _sp

    document = _CandidateDocument()
    document.feed(html)
    document.close()
    for tag in ("html", "head", "body"):
        if tag not in document.opened or tag not in document.closed:
            document.errors.append(f"Missing complete <{tag}> element")
    if not document.viewport:
        document.errors.append("Missing viewport metadata")
    if document.script_type is not None:
        document.errors.append("Unclosed <script> element")

    evidence.update({
        "status": "not_run",
        "blocks": len(document.scripts),
        "module_blocks": sum(kind == "module" for kind, _ in document.scripts),
        "handler_blocks": sum(kind == "handler" for kind, _ in document.scripts),
        "timeout_seconds": SYNTAX_TIMEOUT,
    })
    if document.errors:
        return document.errors[0]
    if not document.scripts:
        evidence["status"] = "not_applicable"
        return None

    # Parse all blocks in one bounded subprocess; neither scripts nor handlers run.
    check_js = (
        "const vm=require('vm'),fs=require('fs');"
        "try{for(const [kind,code] of JSON.parse(fs.readFileSync(0,'utf8'))){"
        "if(kind==='module'){new vm.SourceTextModule(code)}"
        "else{new vm.Script(code)}}}"
        "catch(e){process.stderr.write(e.message);"
        "process.exit(e instanceof SyntaxError ? 1 : 2)}"
    )
    cmd = ["node"]
    if evidence["module_blocks"]:
        cmd.append("--experimental-vm-modules")
    cmd.extend(["-e", check_js])
    try:
        checked = _sp.run(
            cmd, input=json.dumps(document.scripts), capture_output=True,
            text=True, timeout=SYNTAX_TIMEOUT,
        )
    except (OSError, _sp.TimeoutExpired) as exc:
        evidence["status"] = "unavailable"
        return f"Required JavaScript syntax checker unavailable: {type(exc).__name__}"
    if checked.returncode != 0:
        evidence["status"] = "failed" if checked.returncode == 1 else "unavailable"
        error = checked.stderr.strip().split("\n")[0] if checked.stderr.strip() else "Unknown"
        return f"JavaScript syntax checker {evidence['status']}: {error}"
    evidence["status"] = "passed"
    return None


def _check_js_syntax(html, *, required=False, evidence=None):
    """Run Node.js vm.Script on each <script> block to catch syntax errors.

    Returns None if all blocks parse OK, or an error string if any fail.
    Legacy mode skips data/module scripts and tolerates unavailable Node.
    required=True also checks modules/handlers and fails closed on unavailable Node.
    """
    if required:
        return _check_candidate_syntax(html, evidence if evidence is not None else {})

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


def validate_molt_output(html, original_size, *, required_checks=False, syntax_evidence=None):
    """Return None if valid, otherwise an error; required_checks fails closed."""
    if not html:
        return "Empty or None output"

    if len(html.strip()) == 0:
        return "Empty output after stripping"

    # Check DOCTYPE
    if "<!doctype html>" not in html.lower()[:200]:
        return "Missing <!DOCTYPE html>"

    # Check title
    title = re.search(r"<title>(.+?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not title or (required_checks and not title.group(1).strip()):
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
    if required_checks:
        js_error = _check_js_syntax(html, required=True, evidence=syntax_evidence)
    else:
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


def _verify_molt_contract(contract, improved_html):
    result = verify_features(contract, improved_html)
    if result["passed"]:
        return None, result
    missing_summary = ", ".join(m["id"] for m in result["missing"][:5])
    reason = (
        f"Feature contract failed: {len(result['missing'])} features missing "
        f"({result['preservation_ratio']:.0%} preserved). Missing: {missing_summary}"
    )
    return reason, result


def _score_regression_reason(score_before, score_after, contract_result):
    drop = score_before - score_after
    if drop > SCORE_DROP_THRESHOLD:
        return (
            f"Score dropped {drop} points ({score_before}->{score_after}), "
            f"exceeds threshold of {SCORE_DROP_THRESHOLD}"
        )
    if drop > FEATURE_SCORE_DROP_THRESHOLD and contract_result:
        if contract_result.get("missing"):
            return (
                f"Score dropped {drop} points AND "
                f"{len(contract_result['missing'])} features missing"
            )
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


def _molt_log_entry(html, improved_html, generation, focus, mode,
                    contract_result=None, score_before=None, score_after=None):
    entry = {
        "generation": generation,
        "date": date.today().isoformat(),
        "previousSize": len(html),
        "newSize": len(improved_html),
        "previousSha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "newSha256": hashlib.sha256(improved_html.encode("utf-8")).hexdigest(),
        "focus": focus,
        "mode": mode,
    }
    if contract_result:
        entry["feature_preservation"] = contract_result["preservation_ratio"]
        entry["features_missing"] = len(contract_result["missing"])
    if score_before is not None and score_after is not None:
        entry["score_before"] = score_before
        entry["score_after"] = score_after
    return entry


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


def _candidate_component(value):
    return (
        isinstance(value, str)
        and len(value) <= 255
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is not None
    )


def _read_candidate_text(apps_dir, relative, limit, optional=False):
    """Read an exact UTF-8 snapshot, refusing symlinks and non-regular files."""
    path = apps_dir
    if path.is_symlink():
        raise ValueError("Candidate source root must not be a symlink")
    for part in Path(relative).parts:
        if not _candidate_component(part):
            raise ValueError("Unsafe candidate source path")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Candidate source path must not be a symlink: {relative}")
    if optional and not path.exists():
        return None
    if not path.is_file():
        raise FileNotFoundError(f"Candidate source is not a regular file: {relative}")
    with path.open("rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Candidate source too large: {relative} (max {limit} bytes)")
    return data.decode("utf-8")


def _candidate_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def _candidate_app_content(html):
    # Metadata-only churn is not an app improvement. This is not a usefulness test.
    content = re.sub(
        r"<!--[\s\S]*?-->|<meta\b[^>]*>|<title\b[^>]*>[\s\S]*?</title>",
        "", html, flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", "", content)


def _score_candidate_sources(apps_dir, filename, original, candidate):
    # score_game's runtime modifier rereads its path even with content= supplied.
    # Give BOTH sides real isolated snapshots, never the authoritative app path.
    with tempfile.TemporaryDirectory(prefix=".molt-candidate-", dir=apps_dir.parent) as scratch:
        scores = []
        for label, source in (("original", original), ("candidate", candidate)):
            path = Path(scratch) / label / filename
            path.parent.mkdir()
            path.write_bytes(source.encode("utf-8"))
            scores.append(_score_app_if_available(path))
        return scores


def _candidate_score_available(result):
    if not isinstance(result, dict) or result.get("scoring_mode") != "legacy":
        return False
    score = result.get("score")
    health = result.get("runtime_health")
    return (
        type(score) in (int, float) and 0 <= score <= 100
        and isinstance(result.get("dimensions"), dict) and bool(result["dimensions"])
        and isinstance(health, dict)
        and health.get("verdict") in ("healthy", "fragile", "broken")
        and type(health.get("score")) in (int, float)
        and 0 <= health["score"] <= 100
    )


def prepare_molt_candidate(filename, objective, *, candidate_html=None,
                           allow_model=False, apps_dir=None, manifest=None, timeout=180):
    """Qualify one proposed molt and return a UTF-8 patch without applying it.

    Injected HTML is used verbatim. Otherwise a rewrite requires allow_model=True
    and has a one-attempt budget. Fresh legacy scores, feature preservation and
    fail-closed HTML/Node syntax checks qualify structure, NOT end-user usefulness.
    Only disposable source snapshots are written, under the source tree's parent.
    evidence.base_sha256 records each acceptance path's base (None means absent);
    a later operator must still verify these preconditions before applying changes.
    """
    valid_timeout = type(timeout) in (int, float) and 0 < timeout <= MAX_CANDIDATE_TIMEOUT
    evidence = {
        "structural": {"status": "not_run"},
        "features": {"status": "not_run"},
        "scores": {"status": "not_run", "mode": "legacy", "fresh": False},
        "end_user_usefulness": "not_measured",
        "limits": {
            "input_bytes": MAX_INPUT_SIZE,
            "output_bytes": MAX_CANDIDATE_SIZE,
            "objective_bytes": MAX_OBJECTIVE_SIZE,
            "size_ratio_min": SIZE_RATIO_MIN,
            "size_ratio_max": SIZE_RATIO_MAX,
            "size_ratio_unit": "characters (legacy validator)",
            "feature_preservation_ratio_min": 0.9,
            "critical_feature_types": ["localstorage", "canvas", "audio"],
            "constant_values_enforced": False,
            "score_drop": SCORE_DROP_THRESHOLD,
            "score_drop_with_missing_features": FEATURE_SCORE_DROP_THRESHOLD,
            "model_attempts": 1,
            "model_timeout_seconds": MAX_CANDIDATE_TIMEOUT,
            "model_prompt_bytes_exclusive": MAX_INPUT_SIZE,
            "syntax_timeout_seconds": SYNTAX_TIMEOUT,
            "qualification": "Static checks and feature heuristics, not a browser/usefulness proof",
        },
    }
    result = {
        "status": "failed", "reason": "",
        "filename": filename if isinstance(filename, str) else None,
        "app_path": None, "input_sha256": None,
        "objective": objective if isinstance(objective, str) else None,
        "changes": {}, "evidence": evidence,
        "model": {
            "invoked": False, "attempts": 0,
            "timeout_seconds": timeout if valid_timeout else None,
        },
    }

    def finish(status, reason):
        result.update(status=status, reason=reason)
        return result

    if not _candidate_component(filename):
        return finish("rejected", "Filename must be a safe bare app filename")
    if not filename.endswith(".html"):
        filename += ".html"
    if not _candidate_component(filename):
        return finish("rejected", "Filename exceeds the source path limit")
    result["filename"] = filename
    if not isinstance(objective, str) or not objective.strip() or "\x00" in objective:
        return finish("rejected", "Objective must be nonempty operator text")
    try:
        if len(objective) > MAX_OBJECTIVE_SIZE or len(objective.encode("utf-8")) > MAX_OBJECTIVE_SIZE:
            return finish("rejected", f"Objective exceeds {MAX_OBJECTIVE_SIZE} UTF-8 bytes")
    except UnicodeError:
        return finish("rejected", "Objective must be valid UTF-8 text")
    if not valid_timeout:
        return finish("rejected", f"Timeout must be positive and at most {MAX_CANDIDATE_TIMEOUT} seconds")
    if type(allow_model) is not bool:
        return finish("rejected", "allow_model must be an explicit boolean")

    try:
        source_root = Path(APPS_DIR if apps_dir is None else apps_dir)
        if source_root.is_symlink():
            raise ValueError("Candidate source root must not be a symlink")
        source_root = source_root.resolve()
        manifest_text = _read_candidate_text(
            source_root, "manifest.json", MAX_MANIFEST_SIZE, optional=manifest is not None,
        )
        base_manifest = json.loads(manifest_text) if manifest_text is not None else None
        planned_manifest = copy.deepcopy(manifest if manifest is not None else base_manifest)
        json.dumps(planned_manifest, allow_nan=False)
        if manifest is not None and base_manifest is not None and planned_manifest != base_manifest:
            raise ValueError("Supplied manifest differs from the source snapshot")
        matches = []
        for category, data in planned_manifest["categories"].items():
            for entry in data["apps"]:
                if entry["file"] == filename:
                    matches.append((category, data, entry))
        if len(matches) != 1:
            raise ValueError(f"Expected one manifest entry for '{filename}', found {len(matches)}")
        category, data, entry = matches[0]
        folder = data["folder"]
        if not _candidate_component(folder) or folder == "archive":
            raise ValueError("Manifest category folder is not a safe app directory")
        relative_app = f"{folder}/{filename}"
        app_path = f"apps/{relative_app}"
        result["app_path"] = app_path
        html = _read_candidate_text(source_root, relative_app, MAX_INPUT_SIZE)
        result["input_sha256"] = _candidate_digest(html)
        if not html.strip() or "\x00" in html:
            raise ValueError("Original app must be nonempty UTF-8 source without NUL bytes")
        current_gen = entry.get("generation", 0)
        if type(current_gen) is not int or current_gen < 0:
            raise ValueError("Manifest generation must be a nonnegative integer")
        if not isinstance(entry.get("moltHistory", []), list):
            raise ValueError("Manifest moltHistory must be a list")
        if not isinstance(planned_manifest.get("meta", {}), dict):
            raise ValueError("Manifest meta must be an object")
        next_gen = current_gen + 1
        stem = Path(filename).stem
        archive_path = f"apps/archive/{stem}/v{next_gen}.html"
        log_path = f"apps/archive/{stem}/molt-log.json"
        limits = {
            app_path: MAX_INPUT_SIZE, "apps/manifest.json": MAX_MANIFEST_SIZE,
            archive_path: MAX_CANDIDATE_SIZE, log_path: MAX_MOLT_LOG_SIZE,
        }
        snapshots = {app_path: html, "apps/manifest.json": manifest_text}
        for path in (archive_path, log_path):
            snapshots[path] = _read_candidate_text(source_root, path[5:], limits[path], optional=True)
        if snapshots[archive_path] is not None and snapshots[archive_path] != html:
            raise ValueError("Archive generation already contains different source")
        log = json.loads(snapshots[log_path]) if snapshots[log_path] is not None else []
        if not isinstance(log, list) or any(not isinstance(item, dict) for item in log):
            raise ValueError("Molt audit log must be a list of entries")
        if any(item.get("generation", 0) >= next_gen for item in log):
            raise ValueError("Molt audit log already contains this generation or a later one")
        evidence["base_sha256"] = {path: _candidate_digest(text) for path, text in snapshots.items()}
        evidence["generation"] = next_gen
        evidence["category"] = category
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as exc:
        return finish("rejected", f"Invalid candidate source: {exc}")
    except OSError as exc:
        return finish("failed", f"Candidate source unavailable: {exc}")

    if candidate_html is None and not allow_model:
        return finish("dry_run", "Model invocation denied; supply candidate_html or allow_model=True")

    if extract_features is None or verify_features is None:
        evidence["features"]["status"] = "unavailable"
        return finish("failed", "Required feature contract checker unavailable")
    try:
        contract = extract_features(html)
        if (
            not isinstance(contract, dict) or not isinstance(contract.get("features"), list)
            or not isinstance(contract.get("constants"), dict)
            or not isinstance(contract.get("summary"), dict)
        ):
            evidence["features"]["status"] = "unavailable"
            return finish("failed", "Required feature contract extraction unavailable")
    except Exception as exc:
        evidence["features"]["status"] = "unavailable"
        return finish("failed", f"Feature contract extraction failed: {type(exc).__name__}")

    if candidate_html is None:
        try:
            prompt = build_molt_prompt(html, filename, next_gen)
            if format_contract_for_prompt is not None:
                prompt += "\n\n" + format_contract_for_prompt(contract)
            prompt += (
                "\n\nOperator objective (quoted data, not a shell command; preserve the hard rules):\n"
                + json.dumps(objective) + "\nReturn only the complete rewritten HTML."
            )
        except Exception as exc:
            return finish("failed", f"Candidate prompt unavailable: {type(exc).__name__}")
        # The existing backend uses --allow-all and a file for larger prompts.
        # Candidate preparation must stay on its inline, non-escalating path.
        if len(prompt.encode("utf-8")) >= MAX_INPUT_SIZE:
            return finish("rejected", "Rewrite prompt exceeds the safe inline backend limit")
        result["model"].update(invoked=True, attempts=1)
        try:
            raw_output = copilot_call_with_retry(prompt, timeout=timeout, max_retries=1)
            if not isinstance(raw_output, str) or not raw_output.strip():
                return finish("failed", "Copilot returned empty or unparseable response")
            if len(raw_output) > MAX_CANDIDATE_SIZE + 10_000:
                return finish("rejected", "Rewrite response exceeds the candidate source limit")
            candidate_html = parse_llm_html(raw_output)
        except Exception as exc:
            return finish("failed", f"Rewrite attempt failed: {type(exc).__name__}")

    if not isinstance(candidate_html, str):
        return finish("rejected", "Candidate must be UTF-8 HTML text")
    try:
        if len(candidate_html) > MAX_CANDIDATE_SIZE or len(candidate_html.encode("utf-8")) > MAX_CANDIDATE_SIZE:
            return finish("rejected", f"Candidate exceeds {MAX_CANDIDATE_SIZE} UTF-8 bytes")
        result["output_sha256"] = _candidate_digest(candidate_html)
    except UnicodeError:
        return finish("rejected", "Candidate must be valid UTF-8 text")
    if "\x00" in candidate_html:
        return finish("rejected", "Candidate must not contain NUL bytes")
    if candidate_html == html or candidate_html.strip() == html.strip():
        return finish("skipped", "Candidate is unchanged; no generation or archive advancement")
    if _candidate_app_content(candidate_html) == _candidate_app_content(html):
        return finish("skipped", "Candidate changes only metadata, not the app")

    syntax = {"status": "not_run"}
    evidence["structural"] = {
        "status": "not_run", "syntax": syntax,
        "input_bytes": len(html.encode("utf-8")),
        "output_bytes": len(candidate_html.encode("utf-8")),
        "size_ratio": len(candidate_html) / len(html),
    }
    try:
        error = validate_molt_output(
            candidate_html, len(html), required_checks=True, syntax_evidence=syntax,
        )
        if error:
            evidence["structural"].update(status="failed", reason=error)
            return finish("failed" if syntax["status"] == "unavailable" else "rejected", error)
        evidence["structural"]["status"] = "passed"
        evidence["features"]["status"] = "unavailable"
        error, contract_result = _verify_molt_contract(contract, candidate_html)
        json.dumps(contract_result, allow_nan=False)
        if (
            type(contract_result.get("passed")) is not bool
            or type(contract_result.get("total")) is not int
            or contract_result.get("total") != len(contract["features"])
            or type(contract_result.get("preserved")) is not int
            or not 0 <= contract_result["preserved"] <= contract_result["total"]
            or not isinstance(contract_result.get("missing"), list)
            or len(contract_result["missing"]) != contract_result["total"] - contract_result["preserved"]
            or not isinstance(contract_result.get("missing_constants"), list)
            or type(contract_result.get("preservation_ratio")) not in (int, float)
            or not 0 <= contract_result["preservation_ratio"] <= 1
            or contract_result["preservation_ratio"] != (
                contract_result["preserved"] / contract_result["total"]
                if contract_result["total"] else 1.0
            )
        ):
            return finish("failed", "Required feature contract result unavailable")
        evidence["features"] = {
            "status": "failed" if error else "passed", "result": contract_result,
        }
        if error:
            return finish("rejected", error)
        evidence["scores"]["status"] = "unavailable"
        before, after = _score_candidate_sources(source_root, filename, html, candidate_html)
        json.dumps([before, after], allow_nan=False)
        evidence["scores"].update(before=before, after=after)
        if not all(_candidate_score_available(score) for score in (before, after)):
            evidence["scores"]["status"] = "unavailable"
            return finish("failed", "Required fresh legacy scores/runtime modifiers unavailable")
        score_before, score_after = before["score"], after["score"]
        error = _score_regression_reason(score_before, score_after, contract_result)
        evidence["scores"].update(
            status="failed" if error else "passed", fresh=True, delta=score_after - score_before,
        )
        if error:
            return finish("rejected", error)

        focus = get_generation_focus(next_gen)
        log.append(_molt_log_entry(
            html, candidate_html, next_gen, focus, "classic",
            contract_result, score_before, score_after,
        ))
        update_manifest_entry(entry, next_gen, len(candidate_html))
        planned_manifest.setdefault("meta", {})["lastUpdated"] = date.today().isoformat()
        changes = {
            app_path: candidate_html,
            "apps/manifest.json": json.dumps(planned_manifest, indent=2, allow_nan=False),
            archive_path: html,
            log_path: json.dumps(log, indent=2, allow_nan=False),
        }
        for path, original in snapshots.items():
            current = _read_candidate_text(source_root, path[5:], limits[path], optional=True)
            if current != original:
                return finish("failed", f"Source snapshot changed during preparation: {path}")
        evidence["base_unchanged"] = True
        result["changes"] = {path: text for path, text in changes.items() if text != snapshots[path]}
    except Exception as exc:
        return finish("failed", f"Candidate qualification unavailable: {type(exc).__name__}: {exc}")
    return finish("prepared", "Structurally qualified changed candidate; end-user usefulness remains unverified")


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
    if not dry_run and adaptive and _analyze_content is not None:
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

    if improved_html.strip() == html.strip():
        return {
            "status": "skipped",
            "reason": "Copilot returned unchanged content; no generation advancement",
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
        reason, contract_result = _verify_molt_contract(contract, improved_html)
        if verbose:
            ratio = contract_result["preservation_ratio"]
            n_missing = len(contract_result["missing"])
            print(f"  Contract: {ratio:.0%} preserved, {n_missing} missing")
        if reason:
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

                rollback_reason = _score_regression_reason(
                    score_before, score_after, contract_result,
                )
                if rollback_reason:
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
    log_entry = _molt_log_entry(
        html, improved_html, next_gen, focus,
        "surgical" if surgical else ("adaptive" if identity else "classic"),
        contract_result, score_before, score_after,
    )
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
