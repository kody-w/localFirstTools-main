#!/usr/bin/env python3
"""Runtime Verification Gate — static analysis + headless browser testing.

Two modes:
  1. Static analysis (default) — regex-based checks that catch what scoring misses
  2. Browser mode (--browser) — Playwright headless Chromium, runs 7 real runtime checks

Static mode usage:
    python3 scripts/runtime_verify.py                         # Verify all apps
    python3 scripts/runtime_verify.py apps/games-puzzles/     # Verify one category
    python3 scripts/runtime_verify.py path/to/game.html       # Verify single file
    python3 scripts/runtime_verify.py --json                  # Output JSON report
    python3 scripts/runtime_verify.py --failing               # Only show broken/fragile

Browser mode usage:
    python3 scripts/runtime_verify.py --browser path/to/game.html   # Single file
    python3 scripts/runtime_verify.py --browser --all               # All manifest apps
    python3 scripts/runtime_verify.py --browser --category games_puzzles
    python3 scripts/runtime_verify.py --browser --failing           # Only show failures
    python3 scripts/runtime_verify.py --install                     # Install Playwright

Browser checks (7 gates):
    boot          — 0 fatal JS errors on load
    canvas        — >100 non-transparent pixels after 2s
    gameLoop      — requestAnimationFrame called >5 times
    noExternalReqs — 0 requests to external domains
    inputResponse — Canvas pixels change after input events
    noErrors      — 0 uncaught exceptions
    loadTime      — DOMContentLoaded in <5 seconds

Static verdicts:
    healthy  — High confidence the app works in a browser
    fragile  — Might work but has concerning patterns
    broken   — Almost certainly crashes or renders blank

Designed for stdlib-only (no external deps). Browser mode shells out to Node.js
via subprocess. Integrates with rank_games.py as a scoring modifier.
"""

import json
import re
import subprocess
import sys
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
HARNESS_JS = ROOT / "scripts" / "runtime_harness.js"
MANIFEST = APPS_DIR / "manifest.json"

CATEGORY_FOLDERS = {
    "games_puzzles": "games-puzzles",
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "creative_tools": "creative-tools",
    "experimental_ai": "experimental-ai",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "visual_art": "visual-art",
    "educational_tools": "educational",
}


# ---------------------------------------------------------------------------
# Check 1: JavaScript Syntax Balance
# ---------------------------------------------------------------------------
def check_js_syntax(content: str) -> dict:
    """Check bracket/paren/brace balance in JavaScript sections.

    Mismatched delimiters are the #1 cause of games that score well on
    feature detection but crash immediately on load.
    """
    # Extract all script blocks
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)

    if not js.strip():
        return {"pass": False, "score": 0, "reason": "no-javascript"}

    # Strip strings and comments to avoid false positives
    cleaned = _strip_strings_and_comments(js)

    issues = []
    score = 100

    # Bracket balance
    for open_ch, close_ch, name in [("{", "}", "braces"), ("(", ")", "parens"), ("[", "]", "brackets")]:
        opens = cleaned.count(open_ch)
        closes = cleaned.count(close_ch)
        diff = opens - closes
        if diff != 0:
            severity = min(abs(diff) * 15, 50)
            score -= severity
            issues.append(f"{name}-imbalance({diff:+d})")

    # Check for unclosed template literals
    backtick_count = cleaned.count("`")
    if backtick_count % 2 != 0:
        score -= 20
        issues.append("unclosed-template-literal")

    return {
        "pass": score >= 70,
        "score": max(score, 0),
        "issues": issues,
        "js_size": len(js),
    }


def _strip_strings_and_comments(js: str) -> str:
    """Remove string literals and comments from JS to avoid false bracket matches."""
    # Remove single-line comments
    result = re.sub(r"//[^\n]*", "", js)
    # Remove multi-line comments
    result = re.sub(r"/\*.*?\*/", "", result, flags=re.DOTALL)
    # Remove template literals (backtick strings)
    result = re.sub(r"`[^`]*`", '""', result)
    # Remove double-quoted strings
    result = re.sub(r'"(?:[^"\\]|\\.)*"', '""', result)
    # Remove single-quoted strings
    result = re.sub(r"'(?:[^'\\]|\\.)*'", "''", result)
    return result


# ---------------------------------------------------------------------------
# Check 2: Canvas Rendering Verification
# ---------------------------------------------------------------------------
def check_canvas_renders(content: str) -> dict:
    """Verify that canvas-based games actually draw something.

    Many games create a canvas and get a context but never issue draw calls,
    resulting in a blank screen that scores well on 'has canvas'.
    """
    has_canvas = bool(re.search(r"canvas|getContext", content, re.IGNORECASE))
    if not has_canvas:
        # Non-canvas app — this check is N/A
        return {"pass": True, "score": 100, "reason": "not-canvas-app", "applicable": False}

    draw_calls = {
        "fillRect": bool(re.search(r"fillRect\s*\(", content)),
        "strokeRect": bool(re.search(r"strokeRect\s*\(", content)),
        "drawImage": bool(re.search(r"drawImage\s*\(", content)),
        "fillText": bool(re.search(r"fillText\s*\(", content)),
        "fill": bool(re.search(r"\.fill\s*\(", content)),
        "stroke": bool(re.search(r"\.stroke\s*\(", content)),
        "putImageData": bool(re.search(r"putImageData\s*\(", content)),
        "arc": bool(re.search(r"\.arc\s*\(", content)),
        "lineTo": bool(re.search(r"lineTo\s*\(", content)),
        "bezierCurveTo": bool(re.search(r"bezierCurveTo\s*\(", content)),
    }
    draw_count = sum(1 for v in draw_calls.values() if v)

    has_clear = bool(re.search(r"clearRect\s*\(", content))
    has_loop = bool(re.search(r"requestAnimationFrame", content))

    score = 0
    details = []

    if draw_count >= 3:
        score += 50
        details.append(f"diverse-draws({draw_count})")
    elif draw_count >= 1:
        score += 25
        details.append(f"some-draws({draw_count})")
    else:
        details.append("no-draw-calls")

    if has_clear:
        score += 20
        details.append("clears-canvas")

    if has_loop:
        score += 20
        details.append("has-render-loop")

    if has_clear and has_loop and draw_count >= 2:
        score += 10
        details.append("full-render-pipeline")

    return {
        "pass": score >= 50,
        "score": min(score, 100),
        "draw_calls": {k: v for k, v in draw_calls.items() if v},
        "details": details,
        "applicable": True,
    }


# ---------------------------------------------------------------------------
# Check 3: Interaction Wiring
# ---------------------------------------------------------------------------
def check_interaction_wired(content: str) -> dict:
    """Verify event listeners are connected to actual game logic.

    Catches apps that register addEventListener but the handler does nothing
    meaningful — no state change, no function call, no DOM manipulation.
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)

    # Find all addEventListener calls
    listeners = re.findall(
        r"addEventListener\s*\(\s*['\"](\w+)['\"]",
        js,
    )

    if not listeners:
        # DOM-only app without JS event listeners — check for onclick etc
        inline_handlers = re.findall(r"on\w+\s*=\s*['\"]", content)
        if inline_handlers:
            return {
                "pass": True,
                "score": 70,
                "listeners": [],
                "inline_handlers": len(inline_handlers),
                "reason": "inline-handlers-only",
            }
        return {"pass": False, "score": 20, "listeners": [], "reason": "no-event-handling"}

    score = 40  # Base score for having listeners

    # Check if handlers modify state
    state_patterns = [
        r"=\s*true|=\s*false",  # Boolean state changes
        r"\+\+|--|\+=|-=",  # Numeric state changes
        r"\.push\(|\.splice\(|\.pop\(",  # Array mutations
        r"setState|state\s*=|gameState",  # Explicit state
        r"classList\.(add|remove|toggle)",  # DOM state
        r"style\.\w+\s*=",  # Style changes
        r"innerHTML|textContent|innerText",  # Content changes
    ]
    state_mods = sum(1 for p in state_patterns if re.search(p, js))

    if state_mods >= 4:
        score += 40
    elif state_mods >= 2:
        score += 25
    elif state_mods >= 1:
        score += 10

    # Check for input-response patterns (key press → movement, click → action)
    input_response = bool(re.search(
        r"(key|mouse|touch|click|pointer).*?(move|position|x\s*[+=]|y\s*[+=]|velocity|speed|jump|shoot|fire|action)",
        js, re.IGNORECASE | re.DOTALL,
    ))
    if input_response:
        score += 20

    unique_events = set(listeners)
    return {
        "pass": score >= 60,
        "score": min(score, 100),
        "listeners": sorted(unique_events),
        "listener_count": len(listeners),
        "unique_events": len(unique_events),
        "state_modifications": state_mods,
        "input_response_detected": input_response,
    }


# ---------------------------------------------------------------------------
# Check 4: Skeleton Detection
# ---------------------------------------------------------------------------
def check_not_skeleton(content: str) -> dict:
    """Detect apps that are just boilerplate with no real logic.

    Skeletons score well on structural checks (DOCTYPE, viewport, canvas, etc.)
    but have no actual game logic — they're empty shells from failed generation.
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)
    cleaned = _strip_strings_and_comments(js)

    score = 0
    details = []

    # Logic density: ratio of logic tokens to total JS size
    logic_tokens = len(re.findall(
        r"\bif\b|\bfor\b|\bwhile\b|\bswitch\b|\breturn\b|\bfunction\b|\bclass\b|\b=>\b|\bnew\b",
        cleaned,
    ))
    js_lines = cleaned.count("\n") + 1

    if js_lines < 10:
        details.append("minimal-js")
        return {"pass": False, "score": 10, "details": details, "js_lines": js_lines, "logic_tokens": logic_tokens}

    logic_density = logic_tokens / max(js_lines, 1)

    if logic_density >= 0.3:
        score += 40
        details.append(f"high-density({logic_density:.2f})")
    elif logic_density >= 0.15:
        score += 25
        details.append(f"medium-density({logic_density:.2f})")
    elif logic_density >= 0.05:
        score += 10
        details.append(f"low-density({logic_density:.2f})")
    else:
        details.append(f"near-empty({logic_density:.2f})")

    # Function count — real games have multiple functions
    func_count = len(re.findall(r"\bfunction\s+\w+|\w+\s*=\s*(?:function|\([^)]*\)\s*=>)", cleaned))
    if func_count >= 10:
        score += 30
        details.append(f"many-functions({func_count})")
    elif func_count >= 5:
        score += 20
        details.append(f"some-functions({func_count})")
    elif func_count >= 2:
        score += 10
        details.append(f"few-functions({func_count})")
    else:
        details.append(f"barely-any-functions({func_count})")

    # Variable declarations — real games manage state
    var_count = len(re.findall(r"\b(let|const|var)\s+\w+", cleaned))
    if var_count >= 20:
        score += 20
        details.append(f"rich-state({var_count})")
    elif var_count >= 10:
        score += 15
        details.append(f"moderate-state({var_count})")
    elif var_count >= 5:
        score += 10
        details.append(f"minimal-state({var_count})")

    # Unique identifiers — skeleton apps reuse the same few names
    identifiers = set(re.findall(r"\b[a-zA-Z_]\w{2,}\b", cleaned))
    if len(identifiers) >= 100:
        score += 10
        details.append(f"rich-vocabulary({len(identifiers)})")
    elif len(identifiers) >= 50:
        score += 5
        details.append(f"moderate-vocabulary({len(identifiers)})")

    return {
        "pass": score >= 50,
        "score": min(score, 100),
        "details": details,
        "js_lines": js_lines,
        "logic_tokens": logic_tokens,
        "logic_density": round(logic_density, 3),
        "function_count": func_count,
        "variable_count": var_count,
    }


# ---------------------------------------------------------------------------
# Check 5: Dead Code Detection
# ---------------------------------------------------------------------------
def check_dead_code(content: str) -> dict:
    """Detect functions that are defined but never called.

    High dead code ratio suggests copy-paste from templates without customization,
    or failed molting that added code without wiring it in.
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)
    cleaned = _strip_strings_and_comments(js)

    # Find function definitions
    defined = set()
    for m in re.finditer(r"\bfunction\s+(\w+)", cleaned):
        defined.add(m.group(1))
    for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>)", cleaned):
        defined.add(m.group(1))

    if not defined:
        return {"pass": True, "score": 100, "reason": "no-named-functions"}

    # Find function calls (name followed by parenthesis)
    called = set()
    for m in re.finditer(r"\b(\w+)\s*\(", cleaned):
        name = m.group(1)
        # Exclude function definitions (the word before is 'function')
        start = m.start()
        prefix = cleaned[max(0, start - 12):start].strip()
        if prefix.endswith("function"):
            continue
        called.add(name)

    # Also count references in event listeners, callbacks, and assignments
    for m in re.finditer(r"(?:addEventListener|setTimeout|setInterval|requestAnimationFrame)\s*\([^,]*?(\w+)", cleaned):
        called.add(m.group(1))

    # Functions referenced in string form (e.g., onclick="funcName()")
    for m in re.finditer(r'on\w+\s*=\s*["\'](\w+)', content):
        called.add(m.group(1))

    dead = defined - called
    # Exclude common entry points that are called by the runtime
    entry_points = {"init", "setup", "main", "start", "onload", "load", "ready",
                    "render", "draw", "update", "tick", "animate", "gameLoop",
                    "handleResize", "resize", "DOMContentLoaded"}
    dead = dead - {f for f in dead if f.lower() in {e.lower() for e in entry_points}}

    alive_count = len(defined) - len(dead)
    total = len(defined)
    alive_ratio = alive_count / total if total > 0 else 1.0

    score = int(alive_ratio * 100)

    return {
        "pass": score >= 60,
        "score": score,
        "total_functions": total,
        "alive_functions": alive_count,
        "dead_functions": sorted(dead) if dead else [],
        "alive_ratio": round(alive_ratio, 2),
    }


# ---------------------------------------------------------------------------
# Check 6: State Coherence
# ---------------------------------------------------------------------------
def check_state_coherence(content: str) -> dict:
    """Verify game state variables are both written AND read.

    Write-only variables suggest broken display logic.
    Read-only variables (never updated) suggest broken game progression.
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)
    cleaned = _strip_strings_and_comments(js)

    # Common game state variable patterns
    state_vars = {}
    for m in re.finditer(r"(?:let|var)\s+(\w+)\s*=", cleaned):
        name = m.group(1)
        # Skip loop vars, temp vars, DOM refs
        if len(name) < 2 or name in ("i", "j", "k", "x", "y", "e", "el", "ctx", "id"):
            continue
        state_vars[name] = {"written": True, "read": False}

    if not state_vars:
        return {"pass": True, "score": 100, "reason": "no-state-vars-detected"}

    # Check if each variable is read elsewhere
    for name in state_vars:
        # Look for reads: variable used in expressions, conditions, function args
        # Exclude the initial assignment
        pattern = rf"(?<!let\s)(?<!var\s)(?<!const\s)\b{re.escape(name)}\b"
        occurrences = len(re.findall(pattern, cleaned))
        # At least 2 occurrences means it's used beyond definition
        if occurrences >= 2:
            state_vars[name]["read"] = True

    write_only = [n for n, v in state_vars.items() if not v["read"]]
    coherent = [n for n, v in state_vars.items() if v["read"]]

    total = len(state_vars)
    coherent_ratio = len(coherent) / total if total > 0 else 1.0
    score = int(coherent_ratio * 100)

    return {
        "pass": score >= 50,
        "score": score,
        "total_state_vars": total,
        "coherent_vars": len(coherent),
        "write_only_vars": write_only[:10],  # Cap to avoid noise
        "coherence_ratio": round(coherent_ratio, 2),
    }


# ---------------------------------------------------------------------------
# Check 7: Error Resilience
# ---------------------------------------------------------------------------
def check_error_resilience(content: str) -> dict:
    """Check for error handling patterns that prevent silent crashes."""
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)

    score = 0
    details = []

    if re.search(r"\btry\s*\{", js):
        score += 30
        details.append("try-catch")

    if re.search(r"window\.onerror|addEventListener\s*\(\s*['\"]error['\"]", js):
        score += 25
        details.append("global-error-handler")

    if re.search(r"\.catch\s*\(|catch\s*\(\s*\w+\s*\)", js):
        score += 20
        details.append("promise-catch")

    if re.search(r"typeof\s+\w+\s*[!=]==?\s*['\"]undefined['\"]|\w+\s*\?\.", js):
        score += 15
        details.append("null-checks")

    if re.search(r"addEventListener\s*\(\s*['\"]unhandledrejection['\"]", js):
        score += 10
        details.append("unhandled-rejection")

    # Base score — even without explicit error handling, most simple apps work fine
    if not details:
        js_size = len(js)
        if js_size < 5000:
            # Small apps don't need much error handling
            score = 60
            details.append("small-app-pass")
        else:
            score = 30
            details.append("no-error-handling")

    return {
        "pass": score >= 40,
        "score": min(score, 100),
        "details": details,
    }


# ---------------------------------------------------------------------------
# Composite Health Score
# ---------------------------------------------------------------------------
WEIGHTS = {
    "js_syntax": 25,
    "canvas_renders": 15,
    "interaction_wired": 20,
    "not_skeleton": 20,
    "dead_code": 10,
    "state_coherence": 5,
    "error_resilience": 5,
}


def verify_app(filepath: Path) -> dict:
    """Run all runtime verification checks on a single HTML app.

    Returns:
        dict with health_score (0-100), verdict (healthy/fragile/broken),
        and detailed check results.
    """
    filepath = Path(filepath)
    content = filepath.read_text(errors="replace")

    if len(content) < 100:
        return {
            "file": filepath.name,
            "health_score": 0,
            "verdict": "broken",
            "reason": "file-too-small",
            "checks": {},
        }

    checks = {
        "js_syntax": check_js_syntax(content),
        "canvas_renders": check_canvas_renders(content),
        "interaction_wired": check_interaction_wired(content),
        "not_skeleton": check_not_skeleton(content),
        "dead_code": check_dead_code(content),
        "state_coherence": check_state_coherence(content),
        "error_resilience": check_error_resilience(content),
    }

    # Weighted composite score
    weighted_sum = 0
    weight_sum = 0
    for check_name, weight in WEIGHTS.items():
        result = checks[check_name]
        # Skip non-applicable checks (e.g., canvas for non-canvas apps)
        if not result.get("applicable", True) and result.get("applicable") is not None:
            continue
        weighted_sum += result["score"] * weight
        weight_sum += weight

    health_score = round(weighted_sum / weight_sum) if weight_sum > 0 else 0

    # Verdict
    if health_score >= 70:
        verdict = "healthy"
    elif health_score >= 40:
        verdict = "fragile"
    else:
        verdict = "broken"

    # Critical failures override verdict
    if checks["js_syntax"]["score"] < 30:
        verdict = "broken"
    if checks["not_skeleton"].get("js_lines", 999) < 10:
        verdict = "broken"

    return {
        "file": filepath.name,
        "path": str(filepath),
        "health_score": health_score,
        "verdict": verdict,
        "checks": checks,
    }


def verify_directory(dirpath: Path, failing_only: bool = False) -> list:
    """Verify all HTML apps in a directory tree."""
    dirpath = Path(dirpath)
    results = []
    html_files = sorted(dirpath.rglob("*.html"))

    # Skip known non-app files
    skip_dirs = {"archive", "broadcasts", "partitions"}

    for f in html_files:
        if any(skip in f.parts for skip in skip_dirs):
            continue
        if f.stat().st_size < 500:
            continue

        result = verify_app(f)
        if failing_only and result["verdict"] == "healthy":
            continue
        results.append(result)

    results.sort(key=lambda r: r["health_score"])
    return results


def print_report(results: list):
    """Print a human-readable verification report."""
    if not results:
        print("No apps to verify.")
        return

    # Summary
    total = len(results)
    healthy = sum(1 for r in results if r["verdict"] == "healthy")
    fragile = sum(1 for r in results if r["verdict"] == "fragile")
    broken = sum(1 for r in results if r["verdict"] == "broken")
    avg_health = sum(r["health_score"] for r in results) / total

    print(f"\n{'='*70}")
    print(f"RUNTIME VERIFICATION REPORT")
    print(f"{'='*70}")
    print(f"  Total: {total} | Healthy: {healthy} | Fragile: {fragile} | Broken: {broken}")
    print(f"  Average Health: {avg_health:.1f}/100")
    print(f"{'='*70}")

    # Broken apps (most critical)
    broken_apps = [r for r in results if r["verdict"] == "broken"]
    if broken_apps:
        print(f"\n  BROKEN ({len(broken_apps)} apps):")
        for r in broken_apps[:20]:
            failing = [k for k, v in r["checks"].items() if not v.get("pass", True)]
            print(f"    [{r['health_score']:3d}] {r['file'][:45]:<45} fails: {', '.join(failing)}")

    # Fragile apps
    fragile_apps = [r for r in results if r["verdict"] == "fragile"]
    if fragile_apps:
        print(f"\n  FRAGILE ({len(fragile_apps)} apps):")
        for r in fragile_apps[:15]:
            failing = [k for k, v in r["checks"].items() if not v.get("pass", True)]
            print(f"    [{r['health_score']:3d}] {r['file'][:45]:<45} weak: {', '.join(failing)}")

    # Top healthy
    healthy_apps = [r for r in results if r["verdict"] == "healthy"]
    if healthy_apps:
        top = sorted(healthy_apps, key=lambda r: r["health_score"], reverse=True)[:5]
        print(f"\n  TOP HEALTHY ({len(healthy_apps)} apps, showing top 5):")
        for r in top:
            print(f"    [{r['health_score']:3d}] {r['file']}")

    print()


# ===========================================================================
# Browser-Based Runtime Verification (Playwright)
# ===========================================================================

def check_playwright_installed() -> bool:
    """Check if Playwright and Chromium are available."""
    try:
        result = subprocess.run(
            ["npx", "playwright", "--version"],
            capture_output=True, text=True, timeout=15,
            cwd=str(ROOT),
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_playwright():
    """Install Playwright and download Chromium."""
    print("Installing Playwright...")
    subprocess.run(["npm", "install", "playwright"], cwd=str(ROOT), check=True)
    print("Downloading Chromium...")
    subprocess.run(["npx", "playwright", "install", "chromium"], cwd=str(ROOT), check=True)
    print("Playwright installed successfully.")


class _QuietHandler(SimpleHTTPRequestHandler):
    """HTTP handler that suppresses request logging."""
    def log_message(self, format, *args):
        pass


def start_local_server(serve_dir: Path) -> tuple:
    """Start a local HTTP server on a random port, return (server, port)."""
    handler = partial(_QuietHandler, directory=str(serve_dir))
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def run_browser_check(filepath: Path, port: int, timeout_ms: int = 10000) -> dict:
    """Run the Playwright harness on a single file via subprocess.

    Args:
        filepath: Absolute path to the HTML file
        port: Local server port
        timeout_ms: Browser timeout in milliseconds

    Returns:
        dict with check results from runtime_harness.js
    """
    # Build URL relative to the apps directory root
    try:
        rel_path = filepath.relative_to(ROOT)
    except ValueError:
        rel_path = filepath.name
    url = f"http://127.0.0.1:{port}/{rel_path}"

    try:
        result = subprocess.run(
            ["node", str(HARNESS_JS), url, str(timeout_ms)],
            capture_output=True, text=True, timeout=timeout_ms // 1000 + 15,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return {
            "file": filepath.name,
            "path": str(filepath),
            "pass": False,
            "checks": {},
            "errors": ["subprocess-timeout"],
        }
    except FileNotFoundError:
        return {
            "file": filepath.name,
            "path": str(filepath),
            "pass": False,
            "checks": {},
            "errors": ["node-not-found"],
        }

    # Parse JSON from stdout
    stdout = result.stdout.strip()
    if not stdout:
        return {
            "file": filepath.name,
            "path": str(filepath),
            "pass": False,
            "checks": {},
            "errors": [result.stderr.strip()[:200] or "no-output"],
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "file": filepath.name,
            "path": str(filepath),
            "pass": False,
            "checks": {},
            "errors": ["json-parse-error: " + stdout[:200]],
        }

    data["file"] = filepath.name
    data["path"] = str(filepath)
    return data


def discover_manifest_apps(category: str = None) -> list:
    """Discover HTML app files from manifest.json.

    Args:
        category: Optional category key (e.g. 'games_puzzles') to filter.

    Returns:
        List of Path objects for matching app files.
    """
    if not MANIFEST.exists():
        return []
    manifest = json.loads(MANIFEST.read_text())
    files = []
    for cat_key, cat_data in manifest.get("categories", {}).items():
        if category and cat_key != category:
            continue
        folder = cat_data.get("folder", CATEGORY_FOLDERS.get(cat_key, cat_key))
        for app in cat_data.get("apps", []):
            path = APPS_DIR / folder / app["file"]
            if path.exists():
                files.append(path)
    return sorted(files)


def browser_verify_files(files: list, timeout_ms: int = 10000, failing_only: bool = False) -> list:
    """Run browser verification on a list of files.

    Starts a local HTTP server, runs each file through the Playwright harness,
    and returns aggregated results.
    """
    if not files:
        print("No files to verify.")
        return []

    server, port = start_local_server(ROOT)
    results = []

    try:
        for i, filepath in enumerate(files, 1):
            label = filepath.name[:40]
            print(f"  [{i}/{len(files)}] {label}...", end=" ", flush=True)

            data = run_browser_check(filepath, port, timeout_ms)
            passed = data.get("pass", False)
            check_count = data.get("passCount", 0)
            total = data.get("totalChecks", 7)

            if passed:
                print(f"PASS ({check_count}/{total})")
            else:
                failing = [k for k, v in data.get("checks", {}).items()
                           if isinstance(v, dict) and not v.get("pass", True)]
                print(f"FAIL ({check_count}/{total}) -- {', '.join(failing)}")

            if failing_only and passed:
                continue
            results.append(data)
    finally:
        server.shutdown()

    return results


def print_browser_report(results: list):
    """Print a human-readable browser verification report."""
    if not results:
        print("\nNo results to display.")
        return

    total = len(results)
    passing = sum(1 for r in results if r.get("pass", False))
    failing = total - passing

    print(f"\n{'='*70}")
    print("BROWSER RUNTIME VERIFICATION REPORT")
    print(f"{'='*70}")
    print(f"  Total: {total} | Pass: {passing} | Fail: {failing}")
    print(f"{'='*70}")

    # Failures
    fail_results = [r for r in results if not r.get("pass", False)]
    if fail_results:
        print(f"\n  FAILING ({len(fail_results)} apps):")
        for r in fail_results:
            checks = r.get("checks", {})
            failing_checks = [k for k, v in checks.items()
                              if isinstance(v, dict) and not v.get("pass", True)]
            errors = r.get("errors", [])
            detail = ", ".join(failing_checks) if failing_checks else ", ".join(errors[:3])
            count = r.get("passCount", "?")
            total_c = r.get("totalChecks", "?")
            print(f"    [{count}/{total_c}] {r.get('file', '?')[:45]:<45} {detail}")

    # Passing summary
    pass_results = [r for r in results if r.get("pass", False)]
    if pass_results:
        print(f"\n  PASSING ({len(pass_results)} apps):")
        for r in pass_results[:10]:
            count = r.get("passCount", "?")
            total_c = r.get("totalChecks", "?")
            load_ms = r.get("checks", {}).get("loadTime", {}).get("ms", "?")
            print(f"    [{count}/{total_c}] {r.get('file', '?')[:45]:<45} load: {load_ms}ms")
        if len(pass_results) > 10:
            print(f"    ... and {len(pass_results) - 10} more")

    print()


def main():
    args = sys.argv[1:]

    # --install: install Playwright and exit
    if "--install" in args:
        install_playwright()
        return 0

    output_json = "--json" in args
    failing_only = "--failing" in args
    browser_mode = "--browser" in args
    all_apps = "--all" in args

    # Extract --category value
    category = None
    for i, a in enumerate(args):
        if a == "--category" and i + 1 < len(args):
            category = args[i + 1]

    positional = [a for a in args if not a.startswith("--") and a != category]

    # ---------------------------------------------------------------------------
    # Browser mode
    # ---------------------------------------------------------------------------
    if browser_mode:
        if not check_playwright_installed():
            print("Playwright not installed. Run: python3 scripts/runtime_verify.py --install")
            return 1

        if not HARNESS_JS.exists():
            print(f"Error: {HARNESS_JS} not found")
            return 1

        # Determine files to verify
        if positional:
            target = Path(positional[0])
            if target.is_file():
                files = [target.resolve()]
            elif target.is_dir():
                files = sorted(target.rglob("*.html"))
            else:
                print(f"Error: {target} not found")
                return 1
        elif category:
            files = discover_manifest_apps(category=category)
        elif all_apps:
            files = discover_manifest_apps()
        else:
            print("Browser mode requires a file, --all, or --category. See --help.")
            return 1

        print(f"\nBrowser runtime verification: {len(files)} file(s)\n")
        results = browser_verify_files(files, failing_only=failing_only)

        if output_json:
            print(json.dumps(results, indent=2))
        else:
            print_browser_report(results)

        fail_count = sum(1 for r in results if not r.get("pass", False))
        return 1 if fail_count > 0 else 0

    # ---------------------------------------------------------------------------
    # Static analysis mode (original behavior)
    # ---------------------------------------------------------------------------
    if positional:
        target = Path(positional[0])
        if target.is_file():
            results = [verify_app(target)]
        elif target.is_dir():
            results = verify_directory(target, failing_only=failing_only)
        else:
            print(f"Error: {target} not found")
            return 1
    else:
        results = verify_directory(APPS_DIR, failing_only=failing_only)

    if output_json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    # Exit code: 1 if any broken apps found
    broken = sum(1 for r in results if r["verdict"] == "broken")
    return 1 if broken > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
