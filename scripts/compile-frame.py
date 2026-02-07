#!/usr/bin/env python3
"""
compile-frame.py -- Deterministic frame compiler for Rappterbook.

Reads an HTML post, extracts rappterbook:generation and rappterbook:seed meta tags,
and produces the next generation. Deterministic: same input + seed + generation
always yields the same output.

Usage:
  python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html --dry-run
  python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html
  python3 scripts/compile-frame.py --file apps/creative-tools/post-template.html --no-llm
"""

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
from datetime import date
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"
ARCHIVE_DIR = APPS_DIR / "archive"

# ─── Meta Tag Extraction ─────────────────────────────────────────────────────


def extract_meta(html, name):
    """Extract a <meta name="..." content="..."> value from HTML."""
    m = re.search(
        r'<meta\s+name=["\']' + re.escape(name) + r'["\']\s+content=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


def set_meta(html, name, value):
    """Set (or insert) a <meta name="..." content="..."> tag in HTML."""
    pattern = (
        r'(<meta\s+name=["\']'
        + re.escape(name)
        + r'["\']\s+content=["\'])[^"\']*(["\'][^>]*>)'
    )
    if re.search(pattern, html, re.IGNORECASE):
        return re.sub(pattern, rf"\g<1>{value}\2", html, count=1, flags=re.IGNORECASE)
    # Insert after <head> or after last existing <meta>
    insert_point = re.search(r"(</head>)", html, re.IGNORECASE)
    tag = f'<meta name="{name}" content="{value}">\n'
    if insert_point:
        pos = insert_point.start()
        return html[:pos] + tag + html[pos:]
    # Fallback: insert after <html> or at top
    insert_point = re.search(r"(<head[^>]*>)", html, re.IGNORECASE)
    if insert_point:
        pos = insert_point.end()
        return html[:pos] + "\n" + tag + html[pos:]
    return tag + html


# ─── Generation Focus Areas ─────────────────────────────────────────────────

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
            "- Ensure screen reader compatibility"
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
            "- Ensure responsive design (works on mobile and desktop)"
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
            "- Use addEventListener instead of inline onclick handlers\n"
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
            "- Final coherence pass"
        ),
    },
}


def get_focus(generation):
    """Return focus dict for a generation, capping at 5."""
    return GENERATION_FOCUS.get(generation, GENERATION_FOCUS[5])


# ─── Deterministic Transforms ────────────────────────────────────────────────


def deterministic_compile(html, generation, seed):
    """Apply deterministic, seed-stable transforms for the given generation.

    Uses Python's random module seeded with (seed + generation) so that
    identical inputs always produce identical outputs.
    """
    rng = random.Random(seed + generation)

    focus = get_focus(generation)
    focus_name = focus["name"]

    # Always increment rappterbook:generation
    html = set_meta(html, "rappterbook:generation", str(generation))

    # Add a compile timestamp comment (deterministic: based on seed, not wall clock)
    compile_id = hashlib.sha256(f"{seed}:{generation}".encode()).hexdigest()[:12]
    compile_comment = f"<!-- rappterbook:compiled gen={generation} focus={focus_name} id={compile_id} -->"
    if compile_comment not in html:
        # Insert after <!DOCTYPE html> line
        doctype_match = re.search(r"(<!DOCTYPE html[^>]*>)\s*", html, re.IGNORECASE)
        if doctype_match:
            pos = doctype_match.end()
            html = html[:pos] + "\n" + compile_comment + "\n" + html[pos:]
        else:
            html = compile_comment + "\n" + html

    # ── Generation-specific deterministic transforms ──

    if focus_name == "structural":
        html = _apply_structural(html, rng)
    elif focus_name == "accessibility":
        html = _apply_accessibility(html, rng)
    elif focus_name == "performance":
        html = _apply_performance(html, rng)
    elif focus_name == "polish":
        html = _apply_polish(html, rng)
    elif focus_name == "refinement":
        html = _apply_refinement(html, rng)

    return html


def _apply_structural(html, rng):
    """Gen 0→1: structural improvements."""
    # Add lang="en" to <html> if missing
    if re.search(r"<html(?:\s[^>]*)?>", html, re.IGNORECASE):
        if not re.search(r'<html[^>]*\slang\s*=', html, re.IGNORECASE):
            html = re.sub(
                r"<html(\s|>)",
                r'<html lang="en"\1',
                html,
                count=1,
                flags=re.IGNORECASE,
            )

    # Add <meta charset="utf-8"> if missing
    if not re.search(r'<meta[^>]*charset', html, re.IGNORECASE):
        head_match = re.search(r"(<head[^>]*>)", html, re.IGNORECASE)
        if head_match:
            pos = head_match.end()
            html = html[:pos] + '\n<meta charset="utf-8">' + html[pos:]

    # Add <meta name="viewport"> if missing
    if not re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.IGNORECASE):
        head_match = re.search(r"(<head[^>]*>)", html, re.IGNORECASE)
        if head_match:
            pos = head_match.end()
            html = html[:pos] + '\n<meta name="viewport" content="width=device-width, initial-scale=1.0">' + html[pos:]

    # Add <noscript> if missing
    if "<noscript>" not in html.lower():
        body_match = re.search(r"(<body[^>]*>)", html, re.IGNORECASE)
        if body_match:
            pos = body_match.end()
            html = html[:pos] + "\n<noscript>This application requires JavaScript to run.</noscript>" + html[pos:]

    return html


def _apply_accessibility(html, rng):
    """Gen 1→2: accessibility improvements."""
    # Add aria-label to buttons that lack one
    def _add_aria_to_button(m):
        tag = m.group(0)
        if "aria-label" in tag.lower():
            return tag
        # Pick a deterministic hint
        hints = ["Action button", "Interactive control", "Button"]
        hint = hints[rng.randint(0, len(hints) - 1)]
        return tag[:-1] + f' aria-label="{hint}">'

    html = re.sub(
        r"<button(?:\s[^>]*)?>",
        _add_aria_to_button,
        html,
        flags=re.IGNORECASE,
    )

    # Add role="main" to first <main> if missing role
    if re.search(r"<main(?:\s[^>]*)?>", html, re.IGNORECASE):
        if not re.search(r'<main[^>]*\srole\s*=', html, re.IGNORECASE):
            html = re.sub(
                r"<main(\s|>)",
                r'<main role="main"\1',
                html,
                count=1,
                flags=re.IGNORECASE,
            )

    # Add focus-visible hint comment in <style> if a <style> block exists
    focus_hint = "/* a11y: :focus-visible { outline: 2px solid #4A90D9; outline-offset: 2px; } */"
    if "<style>" in html.lower() and focus_hint not in html:
        html = re.sub(
            r"(</style>)",
            focus_hint + "\n\\1",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return html


def _apply_performance(html, rng):
    """Gen 2→3: performance improvements."""
    # Add a performance hint comment
    perf_comment = "<!-- rappterbook:perf-hint Use requestAnimationFrame for animations -->"
    if perf_comment not in html and "<script>" in html.lower():
        html = re.sub(
            r"(<script[^>]*>)",
            f"\\1\n// rappterbook:perf — prefer requestAnimationFrame over setInterval for animation loops",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    # Add will-change hint in style
    will_change_hint = "/* perf: consider will-change: transform for animated elements */"
    if will_change_hint not in html and "<style>" in html.lower():
        html = re.sub(
            r"(</style>)",
            will_change_hint + "\n\\1",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return html


def _apply_polish(html, rng):
    """Gen 3→4: polish improvements."""
    # Add error-handling hint comment in script
    polish_hint = "// rappterbook:polish — wrap risky operations in try/catch"
    if polish_hint not in html and "<script>" in html.lower():
        html = re.sub(
            r"(<script[^>]*>)",
            f"\\1\n{polish_hint}",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return html


def _apply_refinement(html, rng):
    """Gen 4→5: refinement pass."""
    # Add refinement marker
    refine_hint = "<!-- rappterbook:refinement-pass Complete -->"
    if refine_hint not in html:
        html = re.sub(
            r"(</html>)",
            refine_hint + "\n\\1",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return html


# ─── Copilot Intelligence ────────────────────────────────────────────────────


def detect_backend():
    """Check if gh copilot CLI is available."""
    if shutil.which("gh"):
        try:
            import subprocess

            result = subprocess.run(
                ["gh", "copilot", "--", "--help"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                return "copilot-cli"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return "unavailable"


def copilot_compile(html, filename, generation, seed):
    """Attempt to compile via Copilot CLI. Returns improved HTML or None."""
    import subprocess

    focus = get_focus(generation)

    prompt = f"""You are a deterministic HTML frame compiler for Rappterbook.
You are compiling generation {generation} (focus: {focus['name']}).

{focus['instructions']}

HARD RULES:
1. Return ONLY the complete rewritten HTML file -- no explanation, no markdown fences
2. Do NOT add new features or change what the app does
3. Must remain a single self-contained .html file
4. No external dependencies (no CDN links, no external JS/CSS files)
5. Must have <!DOCTYPE html>, <title>, <meta name="viewport">
6. Preserve all existing user-facing behavior exactly
7. The <meta name="rappterbook:generation" content="{generation}"> tag MUST be present with value {generation}
8. The <meta name="rappterbook:seed" content="{seed}"> tag MUST be preserved unchanged

Filename: {filename}
Seed: {seed}
Generation: {generation}

HTML content:
---
{html}
---

Return ONLY the complete rewritten HTML."""

    cmd = [
        "gh", "copilot",
        "--model", "claude-opus-4.6",
        "-p", prompt,
        "--no-ask-user",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            return None
        raw = result.stdout.strip()
        if not raw:
            return None
        # Strip ANSI and copilot wrapper
        raw = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw)
        raw = re.sub(r"\x1b[^a-zA-Z]*[a-zA-Z]", "", raw)
        for marker in ["Task complete", "Total usage est:", "Total session time:"]:
            idx = raw.find(marker)
            if idx > 0:
                raw = raw[:idx]
        raw = raw.strip()
        # Strip markdown fences
        fenced = re.search(r"```(?:html)?\s*\n(.*?)\n```", raw, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        if raw.lower().startswith("<!doctype") or raw.startswith("<"):
            return raw
        return raw
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ─── Archive & Manifest ──────────────────────────────────────────────────────


def archive_current(file_path, generation):
    """Archive the current file to apps/archive/<stem>/v<gen>.html."""
    stem = file_path.stem
    archive_dir = ARCHIVE_DIR / stem
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"v{generation}.html"
    shutil.copy2(file_path, dest)
    return dest


def load_manifest():
    """Load manifest.json."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"categories": {}, "meta": {"version": "1.0", "lastUpdated": ""}}


def save_manifest(manifest):
    """Write manifest atomically."""
    manifest["meta"]["lastUpdated"] = date.today().isoformat()
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    tmp.replace(MANIFEST_PATH)


def find_manifest_entry(manifest, file_path):
    """Find the manifest app entry for a given file path. Returns (cat_key, app_entry) or (None, None)."""
    filename = file_path.name
    for cat_key, cat_data in manifest["categories"].items():
        folder = cat_data.get("folder", "")
        if file_path.parent.name == folder:
            for app_entry in cat_data["apps"]:
                if app_entry["file"] == filename:
                    return cat_key, app_entry
    return None, None


def update_manifest_generation(manifest, file_path, generation):
    """Update the generation field for an app in the manifest."""
    cat_key, app_entry = find_manifest_entry(manifest, file_path)
    if app_entry is not None:
        app_entry["generation"] = generation
        app_entry["lastMolted"] = date.today().isoformat()
        if "moltHistory" not in app_entry:
            app_entry["moltHistory"] = []
        app_entry["moltHistory"].append({
            "gen": generation,
            "date": date.today().isoformat(),
            "size": file_path.stat().st_size,
        })
        return True
    return False


# ─── Main Pipeline ───────────────────────────────────────────────────────────


def compile_frame(file_path, dry_run=False, no_llm=False, verbose=False):
    """Compile an HTML file to its next generation.

    Returns exit code (0 = success).
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1

    html = file_path.read_text(encoding="utf-8", errors="replace")

    # Extract rappterbook meta tags
    gen_str = extract_meta(html, "rappterbook:generation")
    current_gen = int(gen_str) if gen_str is not None else 0

    seed_str = extract_meta(html, "rappterbook:seed")
    seed = int(seed_str) if seed_str is not None else 0

    next_gen = current_gen + 1
    focus = get_focus(next_gen)

    if verbose:
        print(f"compile-frame: {file_path.name}", file=sys.stderr)
        print(f"  generation: {current_gen} → {next_gen}", file=sys.stderr)
        print(f"  seed: {seed}", file=sys.stderr)
        print(f"  focus: {focus['name']}", file=sys.stderr)

    # ── Try Copilot Intelligence first (unless --no-llm) ──
    output_html = None
    if not no_llm:
        backend = detect_backend()
        if verbose:
            print(f"  backend: {backend}", file=sys.stderr)
        if backend == "copilot-cli":
            if verbose:
                print("  calling Copilot CLI...", file=sys.stderr)
            output_html = copilot_compile(html, file_path.name, next_gen, seed)
            if output_html:
                # Ensure generation meta is correct in LLM output
                llm_gen = extract_meta(output_html, "rappterbook:generation")
                if llm_gen != str(next_gen):
                    output_html = set_meta(output_html, "rappterbook:generation", str(next_gen))
                if verbose:
                    print(f"  copilot returned {len(output_html)} bytes", file=sys.stderr)
            else:
                if verbose:
                    print("  copilot returned empty; falling back to deterministic", file=sys.stderr)

    # ── Deterministic fallback ──
    if output_html is None:
        if verbose:
            print("  using deterministic transforms", file=sys.stderr)
        output_html = deterministic_compile(html, next_gen, seed)

    # ── Dry run: print to stdout and exit ──
    if dry_run:
        sys.stdout.write(output_html)
        return 0

    # ── Write mode: archive, replace, update manifest ──
    if verbose:
        print(f"  archiving v{next_gen}...", file=sys.stderr)
    archive_current(file_path, next_gen)

    file_path.write_text(output_html, encoding="utf-8")
    if verbose:
        print(f"  wrote {len(output_html)} bytes to {file_path}", file=sys.stderr)

    manifest = load_manifest()
    updated = update_manifest_generation(manifest, file_path, next_gen)
    if updated:
        save_manifest(manifest)
        if verbose:
            print("  manifest updated", file=sys.stderr)
    elif verbose:
        print("  no manifest entry found (skipping manifest update)", file=sys.stderr)

    print(f"Compiled {file_path.name} → generation {next_gen} ({focus['name']})", file=sys.stderr)
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic frame compiler for Rappterbook. "
        "Reads an HTML post and outputs the next generation.",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the HTML file to compile",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the output HTML to stdout without modifying any files",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force deterministic-only mode (skip Copilot Intelligence)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print diagnostic info to stderr",
    )

    args = parser.parse_args()
    sys.exit(compile_frame(args.file, dry_run=args.dry_run, no_llm=args.no_llm, verbose=args.verbose))


if __name__ == "__main__":
    main()
