#!/usr/bin/env python3
"""Tests that verify no JavaScript syntax errors exist in any HTML app.

Runs Node.js vm.Script to parse each <script> block and reports any
SyntaxError. Skips shader scripts (x-shader), importmap, and JSON types.

Usage:
    python3 -m pytest scripts/tests/test_syntax_scan.py -v
"""

import json
import subprocess
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT / "apps"

# Files that are known non-apps or have structural quirks the scanner can't handle
SKIP_FILES = {
    "TAROT_SYSTEM_ADDITION.html",  # Installation snippet, not an app
    "audio-reactive-fractal.html",  # WebGL shader scripts (type="x-shader")
    "artifact-converter.html",  # React app with external CDN deps
    "landmark-art-studio.html",  # ES module with CDN MediaPipe import
    "data-slosh-tests.html",  # Test file with <script> in string literals (works in browser)
    "steam-deck-game-store.html",  # Template literals with embedded HTML games (works in browser)
}

# Shader script types that are not JavaScript
SKIP_SCRIPT_TYPES = {"x-shader/x-vertex", "x-shader/x-fragment", "importmap",
                     "application/json", "application/ld+json"}


def collect_html_files():
    """Find all HTML app files, excluding archive/broadcasts/dimensions."""
    files = []
    skip_dirs = {"archive", "broadcasts", "dimensions", "cartridges"}
    for cat_dir in APPS_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name in skip_dirs:
            continue
        for html_file in cat_dir.glob("*.html"):
            if html_file.name not in SKIP_FILES:
                files.append(html_file)
    return sorted(files)


def check_syntax(html_path):
    """Check all script blocks in an HTML file for syntax errors.
    Returns list of error strings, empty if no errors.
    """
    content = html_path.read_text(encoding="utf-8", errors="replace")
    errors = []

    # Find all script blocks
    for match in re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', content, re.IGNORECASE):
        attrs = match.group(1)
        code = match.group(2).strip()
        if not code:
            continue

        # Skip non-JS script types
        type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', attrs)
        if type_match:
            stype = type_match.group(1).lower()
            if any(stype.startswith(skip) for skip in SKIP_SCRIPT_TYPES):
                continue
            if stype == "module":
                # For modules, strip imports/exports and check remaining syntax
                code = re.sub(r'^\s*import\s+.*$', '// import', code, flags=re.MULTILINE)
                code = re.sub(r'^\s*export\s+', '', code, flags=re.MULTILINE)

        # Use Node to check syntax
        result = subprocess.run(
            ["node", "--check", "--input-type=module", "-e", ""],
            input=code, capture_output=True, text=True, timeout=10
        )
        # Fallback: use vm.Script via node
        check_code = f"""
const vm = require('vm');
try {{
    new vm.Script({json.dumps(code)});
    process.exit(0);
}} catch(e) {{
    if (e instanceof SyntaxError) {{
        console.error(e.message);
        process.exit(1);
    }}
    process.exit(0);
}}
"""
        result = subprocess.run(
            ["node", "-e", check_code],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip().split("\n")[0] if result.stderr.strip() else "Unknown"
            # Filter out false positives from module scripts
            if type_match and type_match.group(1).lower() == "module":
                if any(kw in err_msg.lower() for kw in ["import", "export", "await"]):
                    continue
            errors.append(err_msg)

    return errors


# Collect files once at module level for parametrize
_HTML_FILES = collect_html_files()


@pytest.mark.parametrize("app_path", _HTML_FILES, ids=lambda f: f.name)
def test_no_syntax_errors(app_path):
    """Each HTML app should have zero JavaScript syntax errors."""
    errors = check_syntax(app_path)
    assert errors == [], f"{app_path.name} has syntax errors: {errors}"
