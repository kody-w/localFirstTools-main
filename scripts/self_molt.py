#!/usr/bin/env python3
"""
self_molt.py — The Molter That Molts Itself

A recursive self-improvement agent for Python scripts. Reads its own source
code (or any target script), scores it against a 6-dimension quality rubric,
identifies the weakest dimension, then rewrites itself via Copilot CLI and
commits the improved version. The molter molts the molter.

Usage:
  python3 scripts/self_molt.py                        # Molt itself
  python3 scripts/self_molt.py scripts/molt.py        # Molt another script
  python3 scripts/self_molt.py --score                # Score only, no rewrite
  python3 scripts/self_molt.py --score-all            # Score all scripts/
  python3 scripts/self_molt.py --dry-run --verbose    # Preview without writing
  python3 scripts/self_molt.py --surgical             # JSON-patch mode
  python3 scripts/self_molt.py --target-dim robustness  # Force a specific dimension

Quality Rubric (100 points, 6 dimensions):
  Structure & Docs  (18) — docstrings, type hints, imports, naming
  Robustness        (16) — error handling, fallbacks, validation, logging
  Maintainability   (16) — constants, DRY, function size, clarity
  Testing           (20) — test file exists, coverage signals, mocks
  Performance       (15) — file size, efficiency, compiled regex
  Polish            (15) — CLI help, progress, error messages, style
"""

import ast
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# ─── Path Setup ──────────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
ARCHIVE_DIR = SCRIPTS_DIR / "archive" / "self-molt"

# Import shared utilities
sys.path.insert(0, str(SCRIPTS_DIR))
from copilot_utils import (
    copilot_call_with_retry,
    detect_backend,
    parse_llm_json,
    strip_copilot_wrapper,
)

# Feature contract (optional)
try:
    from feature_contract import extract_features as _extract_html_features
except ImportError:
    _extract_html_features = None

# ─── Constants ───────────────────────────────────────────────────────────────

MAX_GEN = 10
SIZE_RATIO_MIN = 0.4
SIZE_RATIO_MAX = 2.5
MAX_INPUT_SIZE = 150_000  # 150KB — Python files can be large
SCORE_DROP_THRESHOLD = 8

DIMENSIONS = [
    "structure",
    "robustness",
    "maintainability",
    "testing",
    "performance",
    "polish",
]

GRADE_THRESHOLDS = [
    (90, "S"), (80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "F"),
]


# ─── Python AST Helpers ─────────────────────────────────────────────────────


def _parse_ast(code: str) -> Optional[ast.Module]:
    """Parse Python source into AST. Returns None on syntax error."""
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _check_python_syntax(code: str) -> Optional[str]:
    """Validate Python syntax. Returns None if valid, error string if not."""
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return "line %d: %s" % (e.lineno or 0, e.msg)


def _count_functions(tree: ast.Module) -> int:
    """Count top-level and nested function definitions."""
    return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _count_classes(tree: ast.Module) -> int:
    """Count class definitions."""
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))


def _get_function_lengths(code: str, tree: ast.Module) -> list:
    """Get line count of each function body."""
    lines = code.split("\n")
    lengths = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno and node.lineno:
                lengths.append(node.end_lineno - node.lineno + 1)
    return lengths


def _has_type_hints(tree: ast.Module) -> tuple:
    """Count functions with and without type hints."""
    hinted = 0
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            if node.returns is not None or any(
                a.annotation is not None for a in node.args.args
            ):
                hinted += 1
    return hinted, total


# ─── Scoring Rubric ─────────────────────────────────────────────────────────


def score_structure(code: str, tree: Optional[ast.Module]) -> dict:
    """Structure & Documentation dimension (18 pts max).

    Checks: module docstring, function docstrings, type hints,
    import organization, dead code, naming conventions.
    """
    score = 0
    details = []

    # Module docstring (3 pts)
    if tree and ast.get_docstring(tree):
        score += 3
        details.append("module_docstring")

    # Function docstrings (4 pts) — check ratio
    if tree:
        funcs_with_docs = 0
        total_funcs = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_funcs += 1
                if ast.get_docstring(node):
                    funcs_with_docs += 1
        if total_funcs > 0:
            ratio = funcs_with_docs / total_funcs
            if ratio >= 0.8:
                score += 4
                details.append("func_docstrings_80pct")
            elif ratio >= 0.5:
                score += 2
                details.append("func_docstrings_50pct")
            elif ratio > 0:
                score += 1
                details.append("func_docstrings_some")

    # Type hints (3 pts)
    if tree:
        hinted, total = _has_type_hints(tree)
        if total > 0:
            ratio = hinted / total
            if ratio >= 0.6:
                score += 3
                details.append("type_hints_60pct")
            elif ratio >= 0.3:
                score += 1
                details.append("type_hints_some")

    # Proper imports at top (2 pts)
    if re.search(r'^(?:import |from )', code, re.MULTILINE):
        score += 1
        details.append("has_imports")
    if not re.search(r'^(?!#).*\nimport ', code[500:], re.MULTILINE):
        score += 1
        details.append("imports_at_top")

    # No large commented-out blocks (3 pts)
    commented_lines = len(re.findall(r'^\s*#(?!!).*$', code, re.MULTILINE))
    total_lines = code.count("\n") + 1
    if total_lines > 0 and commented_lines / total_lines < 0.15:
        score += 3
        details.append("low_comment_noise")
    elif total_lines > 0 and commented_lines / total_lines < 0.25:
        score += 1
        details.append("moderate_comment_noise")

    # Semantic naming — no single-letter function names (3 pts)
    if tree:
        bad_names = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.name) <= 1 and not node.name.startswith("_"):
                    bad_names += 1
        if bad_names == 0:
            score += 3
            details.append("semantic_names")

    return {"score": min(score, 18), "max": 18, "details": details}


def score_robustness(code: str, tree: Optional[ast.Module]) -> dict:
    """Robustness & Error Handling dimension (16 pts max).

    Checks: try/except, input validation, graceful fallbacks,
    logging, timeout handling.
    """
    score = 0
    details = []

    # Try/except blocks (3 pts)
    try_count = len(re.findall(r'^\s*try\s*:', code, re.MULTILINE))
    if try_count >= 3:
        score += 3
        details.append("robust_error_handling")
    elif try_count >= 1:
        score += 1
        details.append("basic_error_handling")

    # Graceful optional imports (4 pts)
    graceful = len(re.findall(
        r'try:\s*\n\s+(?:from|import)\s+.*\nexcept\s+ImportError',
        code, re.MULTILINE,
    ))
    if graceful >= 2:
        score += 4
        details.append("graceful_imports")
    elif graceful >= 1:
        score += 2
        details.append("graceful_import")

    # Input validation — checks for None, empty, type (2 pts)
    validations = len(re.findall(
        r'if\s+(?:not\s+\w+|.*is\s+None|len\(\w+\)\s*[<>=])',
        code,
    ))
    if validations >= 3:
        score += 2
        details.append("input_validation")
    elif validations >= 1:
        score += 1
        details.append("basic_validation")

    # Logging or structured output (3 pts)
    if "import logging" in code or "getLogger" in code:
        score += 3
        details.append("logging_configured")
    elif re.search(r'print\s*\(f?["\'].*(?:ERROR|WARN|INFO)', code):
        score += 1
        details.append("structured_prints")

    # Timeout/resource awareness (2 pts)
    if re.search(r'timeout|TIMEOUT|time\.time\(\)|deadline', code):
        score += 2
        details.append("timeout_aware")

    # Doesn't use bare except (2 pts)
    bare_excepts = len(re.findall(r'except\s*:', code))
    if bare_excepts == 0:
        score += 2
        details.append("no_bare_except")

    return {"score": min(score, 16), "max": 16, "details": details}


def score_maintainability(code: str, tree: Optional[ast.Module]) -> dict:
    """Maintainability dimension (16 pts max).

    Checks: named constants, function size, DRY, clear control flow.
    """
    score = 0
    details = []

    # Named constants vs magic numbers (3 pts)
    upper_consts = len(re.findall(r'^[A-Z][A-Z_]{2,}\s*=', code, re.MULTILINE))
    if upper_consts >= 5:
        score += 3
        details.append("named_constants")
    elif upper_consts >= 2:
        score += 1
        details.append("some_constants")

    # Functions under 50 lines (3 pts)
    if tree:
        lengths = _get_function_lengths(code, tree)
        if lengths:
            long_funcs = sum(1 for l in lengths if l > 50)
            if long_funcs == 0:
                score += 3
                details.append("all_funcs_under_50")
            elif long_funcs <= 1:
                score += 2
                details.append("most_funcs_under_50")
            elif long_funcs <= len(lengths) * 0.2:
                score += 1
                details.append("some_long_funcs")

    # DRY — no obvious duplication (3 pts)
    lines = [l.strip() for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
    seen = {}
    for line in lines:
        if len(line) > 30:
            seen[line] = seen.get(line, 0) + 1
    duplicates = sum(1 for c in seen.values() if c > 2)
    if duplicates == 0:
        score += 3
        details.append("no_duplication")
    elif duplicates <= 3:
        score += 1
        details.append("low_duplication")

    # Configuration not hardcoded (2 pts)
    if re.search(r'(?:config|CONFIG|settings|SETTINGS|options|OPTIONS)\s*[=\[]', code):
        score += 2
        details.append("config_externalized")
    elif upper_consts >= 3:
        score += 1
        details.append("constants_as_config")

    # Clear control flow — limited nesting (2 pts)
    deep_nesting = len(re.findall(r'^(?:\s{16,}|\t{4,})\S', code, re.MULTILINE))
    if deep_nesting <= 5:
        score += 2
        details.append("clear_control_flow")
    elif deep_nesting <= 15:
        score += 1
        details.append("moderate_nesting")

    # Regex patterns named/compiled (3 pts)
    raw_regexes = len(re.findall(r're\.(?:search|findall|match|sub)\s*\(', code))
    compiled = len(re.findall(r're\.compile\s*\(', code))
    named_patterns = len(re.findall(r'_(?:PATTERN|REGEX|RE)\s*=\s*re\.compile', code, re.IGNORECASE))
    if raw_regexes > 0:
        if compiled >= raw_regexes * 0.3 or named_patterns >= 2:
            score += 3
            details.append("compiled_regex")
        elif compiled >= 1:
            score += 1
            details.append("some_compiled_regex")
    else:
        score += 3
        details.append("no_regex_needed")

    return {"score": min(score, 16), "max": 16, "details": details}


def score_testing(code: str, filepath: Path) -> dict:
    """Testing dimension (20 pts max).

    Checks: corresponding test file exists, test count, mocking,
    edge case coverage, fixture usage.
    """
    score = 0
    details = []

    # Find test file
    stem = filepath.stem
    tests_dir = filepath.parent / "tests"
    test_file = tests_dir / ("test_" + stem + ".py")
    alt_test = tests_dir / ("test_" + stem.replace("-", "_") + ".py")

    test_path = None
    if test_file.exists():
        test_path = test_file
    elif alt_test.exists():
        test_path = alt_test

    if test_path is None:
        # Check all test files for imports of this module
        if tests_dir.exists():
            for tf in tests_dir.glob("test_*.py"):
                tc = tf.read_text(encoding="utf-8", errors="replace")
                if ("import " + stem) in tc or ("from " + stem) in tc:
                    test_path = tf
                    break

    if test_path is None:
        details.append("no_test_file")
        return {"score": 0, "max": 20, "details": details}

    test_code = test_path.read_text(encoding="utf-8", errors="replace")
    details.append("test_file_exists")
    score += 4

    # Test count (3 pts)
    test_count = len(re.findall(r'def test_\w+', test_code))
    if test_count >= 15:
        score += 3
        details.append("15plus_tests")
    elif test_count >= 8:
        score += 2
        details.append("8plus_tests")
    elif test_count >= 3:
        score += 1
        details.append("3plus_tests")

    # Edge cases tested (3 pts)
    edge_signals = sum(1 for pattern in [
        r'test_.*(?:empty|none|null|zero|negative|invalid|missing|edge)',
        r'test_.*(?:error|fail|reject|bad|broken|corrupt)',
        r'test_.*(?:large|huge|max|overflow|boundary)',
    ] if re.search(pattern, test_code, re.IGNORECASE))
    score += min(edge_signals, 3)
    if edge_signals > 0:
        details.append("edge_cases_%d" % min(edge_signals, 3))

    # Mocks for external deps (2 pts)
    if "mock.patch" in test_code or "MagicMock" in test_code:
        score += 2
        details.append("uses_mocks")

    # Integration tests (2 pts)
    if re.search(r'class\s+Test\w*(?:Integration|EndToEnd|E2E)', test_code, re.IGNORECASE):
        score += 2
        details.append("integration_tests")
    elif re.search(r'def test_\w*(?:full|pipeline|end_to_end|integration)', test_code, re.IGNORECASE):
        score += 1
        details.append("integration_test_funcs")

    # Test isolation — uses tmp_path or tempfile (3 pts)
    if "tmp_path" in test_code or "tmp_project" in test_code:
        score += 3
        details.append("test_isolation")
    elif "tempfile" in test_code or "TemporaryDirectory" in test_code:
        score += 2
        details.append("tempfile_isolation")

    # Fixtures/helpers (3 pts)
    fixture_count = len(re.findall(r'@pytest\.fixture', test_code))
    if fixture_count >= 2:
        score += 3
        details.append("rich_fixtures")
    elif fixture_count >= 1:
        score += 1
        details.append("has_fixtures")

    return {"score": min(score, 20), "max": 20, "details": details}


def score_performance(code: str, tree: Optional[ast.Module]) -> dict:
    """Performance & Scale dimension (15 pts max).

    Checks: file size, nested loops, data structures, compiled regex,
    streaming for large inputs.
    """
    score = 0
    details = []

    lines = code.count("\n") + 1

    # File size (2 pts)
    if lines <= 500:
        score += 2
        details.append("compact_file")
    elif lines <= 1000:
        score += 1
        details.append("moderate_file")

    # No gratuitous nested loops (2 pts)
    nested = len(re.findall(r'for\s+.*:\s*\n(?:\s+.*\n)*\s+for\s+.*:', code))
    if nested <= 1:
        score += 2
        details.append("minimal_nesting")
    elif nested <= 3:
        score += 1
        details.append("some_nesting")

    # Efficient data structures — set/dict usage (3 pts)
    if re.search(r'\bset\s*\(|{.*:.*}|\bdict\s*\(', code):
        score += 2
        details.append("efficient_structures")
    if re.search(r'\bdefaultdict|\bCounter\b|\bcollections\b', code):
        score += 1
        details.append("collections_used")

    # Compiled regex (2 pts)
    compiled = len(re.findall(r're\.compile\s*\(', code))
    total_re = len(re.findall(r're\.(?:search|findall|match|sub)\s*\(', code))
    if total_re == 0 or compiled >= total_re * 0.3:
        score += 2
        details.append("regex_compiled")
    elif compiled >= 1:
        score += 1
        details.append("some_regex_compiled")

    # Memory awareness — generators, streaming (2 pts)
    if re.search(r'\byield\b|\.read\(\d+\)|iter\(|chunk', code):
        score += 2
        details.append("memory_aware")
    elif re.search(r'with\s+open', code):
        score += 1
        details.append("file_context_managers")

    # Handles large inputs (2 pts)
    if re.search(r'MAX_.*SIZE|max_size|LIMIT|truncat|[:]\d+\]', code):
        score += 2
        details.append("size_aware")

    # Avoids global state mutation (2 pts)
    global_count = len(re.findall(r'^\s*global\s+', code, re.MULTILINE))
    if global_count == 0:
        score += 2
        details.append("no_global_mutation")

    return {"score": min(score, 15), "max": 15, "details": details}


def score_polish(code: str, filepath: Path) -> dict:
    """Polish & Usability dimension (15 pts max).

    Checks: CLI help, progress indicators, error messages,
    code style, exit codes.
    """
    score = 0
    details = []

    # CLI help/usage (2 pts)
    if re.search(r'argparse|--help|Usage:|usage:', code):
        score += 2
        details.append("cli_help")
    elif re.search(r'sys\.argv|if __name__', code):
        score += 1
        details.append("has_cli")

    # Progress indicators (1 pt)
    if re.search(r'print\s*\(.*(?:\d+[/|]\d+|progress|Processing|\.\.\.)', code):
        score += 1
        details.append("progress_output")

    # Readable error messages (2 pts)
    error_msgs = len(re.findall(r'(?:raise|print|warn).*(?:ERROR|Error|failed|invalid|missing)', code, re.IGNORECASE))
    if error_msgs >= 3:
        score += 2
        details.append("clear_errors")
    elif error_msgs >= 1:
        score += 1
        details.append("some_errors")

    # Docstring examples (2 pts)
    if re.search(r'Example|>>>|Usage:', code):
        score += 2
        details.append("has_examples")

    # Consistent style (2 pts) — check for consistent quoting & indentation
    single_quotes = code.count("'")
    double_quotes = code.count('"')
    # Dominant style used consistently
    if single_quotes > 0 or double_quotes > 0:
        dominant = max(single_quotes, double_quotes)
        total = single_quotes + double_quotes
        if dominant / total > 0.7:
            score += 2
            details.append("consistent_style")
        else:
            score += 1
            details.append("mixed_style")

    # Semantic exit codes (1 pt)
    if re.search(r'sys\.exit\s*\(\s*[01]\s*\)', code):
        score += 1
        details.append("exit_codes")

    # Quiet/verbose mode support (2 pts)
    if re.search(r'--verbose|verbose|--quiet|-v\b', code):
        score += 2
        details.append("verbose_mode")

    # Section separators / visual organization (2 pts)
    if re.search(r'^# ─|^# ═|^# \*{3,}|^# -{10,}', code, re.MULTILINE):
        score += 2
        details.append("visual_sections")
    elif re.search(r'^#{2,}\s+\w', code, re.MULTILINE):
        score += 1
        details.append("section_comments")

    return {"score": min(score, 15), "max": 15, "details": details}


# ─── Aggregate Scoring ───────────────────────────────────────────────────────


def score_script(filepath: Path, content: Optional[str] = None) -> dict:
    """Score a Python script across all 6 dimensions.

    Returns:
        dict with score, grade, dimensions, weakest_dimension, and details.
    """
    if content is None:
        content = filepath.read_text(encoding="utf-8", errors="replace")

    tree = _parse_ast(content)

    dimensions = {
        "structure": score_structure(content, tree),
        "robustness": score_robustness(content, tree),
        "maintainability": score_maintainability(content, tree),
        "testing": score_testing(content, filepath),
        "performance": score_performance(content, tree),
        "polish": score_polish(content, filepath),
    }

    total = sum(d["score"] for d in dimensions.values())
    max_total = sum(d["max"] for d in dimensions.values())

    # Find weakest dimension (lowest % of max)
    weakest = min(
        dimensions.items(),
        key=lambda kv: kv[1]["score"] / kv[1]["max"] if kv[1]["max"] > 0 else 1.0,
    )

    # Grade
    grade = "F"
    for threshold, g in GRADE_THRESHOLDS:
        if total >= threshold:
            grade = g
            break

    return {
        "file": filepath.name,
        "path": str(filepath),
        "score": total,
        "max": max_total,
        "grade": grade,
        "lines": content.count("\n") + 1,
        "size_bytes": len(content),
        "functions": _count_functions(tree) if tree else 0,
        "classes": _count_classes(tree) if tree else 0,
        "dimensions": dimensions,
        "weakest_dimension": weakest[0],
        "weakest_score": "%d/%d" % (weakest[1]["score"], weakest[1]["max"]),
        "syntax_valid": tree is not None,
    }


def format_scorecard(result: dict) -> str:
    """Format a score result as a readable scorecard."""
    lines = []
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════╗")
    lines.append("║  SELF-MOLT SCORECARD                                ║")
    lines.append("╠══════════════════════════════════════════════════════╣")
    lines.append("║  File: %-45s ║" % result["file"][:45])
    lines.append("║  Score: %d/%d  Grade: %-2s                            ║" % (
        result["score"], result["max"], result["grade"]))
    lines.append("║  Lines: %-6d  Functions: %-4d  Classes: %-4d        ║" % (
        result["lines"], result["functions"], result["classes"]))
    lines.append("╠══════════════════════════════════════════════════════╣")

    for dim_name in DIMENSIONS:
        dim = result["dimensions"][dim_name]
        bar_len = int(dim["score"] / dim["max"] * 20) if dim["max"] > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)
        marker = " ◄ WEAKEST" if dim_name == result["weakest_dimension"] else ""
        lines.append("║  %-17s %s %2d/%-2d%s" % (
            dim_name.title(), bar, dim["score"], dim["max"], marker))
        if dim["details"]:
            detail_str = ", ".join(dim["details"][:4])
            lines.append("║    %s" % detail_str[:52])

    lines.append("╠══════════════════════════════════════════════════════╣")
    lines.append("║  Weakest: %-15s (%s)                   ║" % (
        result["weakest_dimension"], result["weakest_score"]))
    lines.append("╚══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


# ─── Self-Molt Pipeline ─────────────────────────────────────────────────────


def build_self_molt_prompt(
    code: str,
    filepath: Path,
    scorecard: dict,
    target_dim: Optional[str] = None,
    surgical: bool = False,
) -> str:
    """Build the LLM prompt for self-improvement.

    Tells the LLM exactly what dimension to improve and what the current
    weaknesses are, based on the scoring rubric.
    """
    dim_name = target_dim or scorecard["weakest_dimension"]
    dim_data = scorecard["dimensions"][dim_name]
    missing = [d for d in DIMENSIONS if d not in [
        detail for detail in dim_data["details"]
    ]]

    dimension_guidance = {
        "structure": (
            "Improve STRUCTURE & DOCUMENTATION:\n"
            "- Add/improve module docstring with purpose, usage, examples\n"
            "- Add docstrings to undocumented functions (Args, Returns format)\n"
            "- Add type hints to function signatures\n"
            "- Ensure imports are organized (stdlib, third-party, local)\n"
            "- Remove dead/commented-out code\n"
            "- Use semantic function/variable names"
        ),
        "robustness": (
            "Improve ROBUSTNESS & ERROR HANDLING:\n"
            "- Add try/except around external calls (file I/O, subprocess, network)\n"
            "- Add input validation (None checks, type checks, bounds)\n"
            "- Add graceful fallbacks for optional imports\n"
            "- Replace bare 'except:' with specific exception types\n"
            "- Add timeout awareness for long operations\n"
            "- Consider adding logging instead of bare print statements"
        ),
        "maintainability": (
            "Improve MAINTAINABILITY:\n"
            "- Replace magic numbers with named ALL_CAPS constants\n"
            "- Break functions longer than 50 lines into smaller ones\n"
            "- Eliminate code duplication (DRY principle)\n"
            "- Compile regex patterns used multiple times\n"
            "- Reduce deep nesting with early returns\n"
            "- Externalize configuration values"
        ),
        "testing": (
            "Improve TESTING (this is about the script's testability, not writing tests):\n"
            "- Make functions more testable (dependency injection, return values)\n"
            "- Separate pure logic from I/O side effects\n"
            "- Add parameters for dependency injection (_manifest, _apps_dir pattern)\n"
            "- Ensure functions have clear inputs and outputs\n"
            "- Make external dependencies mockable"
        ),
        "performance": (
            "Improve PERFORMANCE & SCALE:\n"
            "- Compile regex patterns used in loops (re.compile)\n"
            "- Use sets/dicts instead of lists for lookups\n"
            "- Add generators/streaming for large file processing\n"
            "- Reduce unnecessary nested loops\n"
            "- Add size limits and truncation for large inputs\n"
            "- Eliminate global state mutation"
        ),
        "polish": (
            "Improve POLISH & USABILITY:\n"
            "- Add --help/usage text for CLI entry points\n"
            "- Add progress indicators for long operations\n"
            "- Improve error messages to be actionable\n"
            "- Add examples in docstrings\n"
            "- Support --verbose/--quiet modes\n"
            "- Add visual section separators for code organization\n"
            "- Use semantic exit codes (0=success, 1=failure)"
        ),
    }

    guidance = dimension_guidance.get(dim_name, "General improvement")

    current_details = ", ".join(dim_data["details"]) if dim_data["details"] else "none"

    if surgical:
        return _build_surgical_self_molt_prompt(
            code, filepath, scorecard, dim_name, guidance, current_details,
        )

    return """You are improving a Python script's quality. Focus on ONE dimension.

FILE: {filename}
CURRENT SCORE: {score}/{max_score} (Grade {grade})
TARGET DIMENSION: {dim_name} ({dim_score}/{dim_max})
CURRENT STRENGTHS IN THIS DIM: {current_details}

{guidance}

HARD RULES:
1. Return ONLY the complete Python file — no explanation, no markdown
2. Do NOT change the script's functionality or public API
3. Do NOT add new dependencies
4. Do NOT remove any existing functions or change their signatures
5. Preserve all existing behavior exactly
6. The output must be valid Python (passes ast.parse)
7. Focus ONLY on the target dimension — don't touch unrelated code

The script currently has {functions} functions and {lines} lines.
Improve the {dim_name} dimension from {dim_score}/{dim_max} to as high as possible.

Python source:
---
{code}
---

Return ONLY the complete Python file.""".format(
        filename=filepath.name,
        score=scorecard["score"],
        max_score=scorecard["max"],
        grade=scorecard["grade"],
        dim_name=dim_name.upper(),
        dim_score=dim_data["score"],
        dim_max=dim_data["max"],
        current_details=current_details,
        guidance=guidance,
        functions=scorecard["functions"],
        lines=scorecard["lines"],
        code=code,
    )


def _build_surgical_self_molt_prompt(
    code, filepath, scorecard, dim_name, guidance, current_details,
):
    """Build a surgical (JSON-patch) prompt for self-improvement."""
    dim_data = scorecard["dimensions"][dim_name]

    return """You are making SURGICAL improvements to a Python script.
Return a JSON array of edit objects — NOT the whole file.

FILE: {filename}
TARGET: {dim_name} dimension ({dim_score}/{dim_max})
CURRENT STRENGTHS: {current_details}

{guidance}

Return a JSON array of edits:
[
  {{"description": "what this change does", "find": "exact text to find", "replace": "replacement text"}}
]

Rules:
- Each "find" must appear EXACTLY ONCE in the source
- Maximum 15 edits
- Do NOT change functionality or public API
- Focus ONLY on {dim_name}

Python source:
---
{code}
---

Return ONLY the JSON array.""".format(
        filename=filepath.name,
        dim_name=dim_name.upper(),
        dim_score=dim_data["score"],
        dim_max=dim_data["max"],
        current_details=current_details,
        guidance=guidance,
        code=code,
    )


def apply_surgical_edits(code: str, raw_response: str) -> tuple:
    """Apply surgical JSON edits to Python source.

    Returns (modified_code, applied_count, errors).
    """
    # Try to extract JSON from response
    text = strip_copilot_wrapper(raw_response) if raw_response else ""
    edits = parse_llm_json(text)
    if edits is None:
        # Try extracting from code fences
        fenced = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if fenced:
            try:
                edits = json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

    if not isinstance(edits, list):
        return None, 0, ["Response is not a JSON array"]

    modified = code
    applied = 0
    errors = []

    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            errors.append("Edit %d: not a dict" % i)
            continue

        find = edit.get("find", "")
        replace = edit.get("replace", "")
        desc = edit.get("description", "edit %d" % i)

        if not find:
            errors.append("Edit %d (%s): empty find" % (i, desc))
            continue

        count = modified.count(find)
        if count == 0:
            errors.append("Edit %d (%s): not found" % (i, desc))
            continue
        if count > 1:
            errors.append("Edit %d (%s): %d matches" % (i, desc, count))
            continue

        modified = modified.replace(find, replace, 1)
        applied += 1

    return (modified if applied > 0 else None), applied, errors


def validate_molt_output(new_code: str, original_code: str) -> Optional[str]:
    """Validate the molted Python code. Returns None if valid, error string if not."""
    if not new_code or not new_code.strip():
        return "Empty output"

    # Syntax check
    syntax_err = _check_python_syntax(new_code)
    if syntax_err:
        return "Syntax error: %s" % syntax_err

    # Size ratio
    new_size = len(new_code)
    orig_size = len(original_code)
    if orig_size > 0:
        ratio = new_size / orig_size
        if ratio < SIZE_RATIO_MIN:
            return "Too small: %.1f%% of original (min %.0f%%)" % (ratio * 100, SIZE_RATIO_MIN * 100)
        if ratio > SIZE_RATIO_MAX:
            return "Too large: %.1f%% of original (max %.0f%%)" % (ratio * 100, SIZE_RATIO_MAX * 100)

    # Must still have the same module docstring topic (not a completely different file)
    orig_tree = _parse_ast(original_code)
    new_tree = _parse_ast(new_code)
    if orig_tree and new_tree:
        orig_doc = ast.get_docstring(orig_tree) or ""
        new_doc = ast.get_docstring(new_tree) or ""
        if orig_doc and not new_doc:
            return "Module docstring removed"

    # Function preservation — all original function names must still exist
    if orig_tree and new_tree:
        orig_funcs = {
            node.name for node in ast.walk(orig_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        new_funcs = {
            node.name for node in ast.walk(new_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        missing = orig_funcs - new_funcs
        if missing:
            return "Functions removed: %s" % ", ".join(sorted(missing)[:5])

    return None


def archive_version(filepath: Path, generation: int) -> Path:
    """Archive the current version before overwriting."""
    archive_dir = ARCHIVE_DIR / filepath.stem
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / ("v%d.py" % generation)
    shutil.copy2(filepath, dest)
    return dest


def append_log(filepath: Path, entry: dict) -> None:
    """Append to the self-molt audit log."""
    log_dir = ARCHIVE_DIR / filepath.stem
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "molt-log.json"
    if log_path.exists():
        log = json.loads(log_path.read_text())
    else:
        log = []
    log.append(entry)
    log_path.write_text(json.dumps(log, indent=2))


def get_generation(filepath: Path) -> int:
    """Get the current generation from the audit log."""
    log_path = ARCHIVE_DIR / filepath.stem / "molt-log.json"
    if not log_path.exists():
        return 0
    try:
        log = json.loads(log_path.read_text())
        return max(e.get("generation", 0) for e in log) if log else 0
    except Exception:
        return 0


# ─── Core Pipeline ───────────────────────────────────────────────────────────


def self_molt(
    filepath: Optional[Path] = None,
    dry_run: bool = False,
    verbose: bool = False,
    surgical: bool = False,
    target_dim: Optional[str] = None,
) -> dict:
    """Run one self-improvement cycle on a Python script.

    Args:
        filepath: Target script. Defaults to this file (self_molt.py).
        dry_run: Preview without writing changes.
        surgical: Use JSON-patch mode instead of full rewrite.
        target_dim: Force improvement of a specific dimension.

    Returns:
        dict with status, scores, and details.
    """
    if filepath is None:
        filepath = Path(__file__).resolve()

    if not filepath.exists():
        return {"status": "failed", "reason": "File not found: %s" % filepath}

    # Read source
    code = filepath.read_text(encoding="utf-8", errors="replace")
    if len(code) > MAX_INPUT_SIZE:
        return {"status": "skipped", "reason": "File too large: %d bytes" % len(code)}

    # Score before
    score_before = score_script(filepath, code)
    current_gen = get_generation(filepath)
    next_gen = current_gen + 1

    if verbose:
        print(format_scorecard(score_before))

    if current_gen >= MAX_GEN:
        return {
            "status": "skipped",
            "reason": "Max generation %d reached" % MAX_GEN,
            "score": score_before,
        }

    # Determine target dimension
    dim = target_dim or score_before["weakest_dimension"]
    if dim not in DIMENSIONS:
        return {"status": "failed", "reason": "Unknown dimension: %s" % dim}

    dim_data = score_before["dimensions"][dim]
    if verbose:
        print("\n  Target: %s (%d/%d)" % (dim, dim_data["score"], dim_data["max"]))
        print("  Generation: %d -> %d" % (current_gen, next_gen))
        print("  Mode: %s" % ("surgical" if surgical else "full rewrite"))

    # Build prompt
    prompt = build_self_molt_prompt(code, filepath, score_before, dim, surgical)

    if dry_run:
        if verbose:
            print("  DRY RUN: prompt is %d chars" % len(prompt))
        return {
            "status": "dry_run",
            "file": filepath.name,
            "score": score_before,
            "target_dimension": dim,
            "generation": next_gen,
            "prompt_size": len(prompt),
        }

    if verbose:
        print("  Calling Copilot CLI...")

    # Call LLM
    raw = copilot_call_with_retry(prompt, timeout=180)
    if not raw:
        return {
            "status": "failed",
            "reason": "Copilot returned empty response",
            "score": score_before,
        }

    # Parse response
    if surgical:
        new_code, applied, errors = apply_surgical_edits(code, raw)
        if new_code is None:
            if verbose:
                print("  Surgical failed: %s" % errors)
                print("  Falling back to full rewrite parse...")
            # Fallback: try to extract Python from response
            text = strip_copilot_wrapper(raw)
            fenced = re.search(r'```(?:python)?\s*\n(.*?)\n```', text, re.DOTALL)
            new_code = fenced.group(1) if fenced else text
        elif verbose:
            print("  Surgical: %d edits applied, %d errors" % (applied, len(errors)))
    else:
        text = strip_copilot_wrapper(raw)
        fenced = re.search(r'```(?:python)?\s*\n(.*?)\n```', text, re.DOTALL)
        new_code = fenced.group(1) if fenced else text

    # Validate
    error = validate_molt_output(new_code, code)
    if error:
        if verbose:
            print("  REJECTED: %s" % error)
        return {
            "status": "rejected",
            "reason": error,
            "score": score_before,
        }

    # Score after (write to temp to score with correct path)
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir=filepath.parent, delete=False,
    ) as tmp:
        tmp.write(new_code)
        tmp_path = Path(tmp.name)

    try:
        # Rename to match original for test file detection
        score_path = tmp_path.rename(filepath.parent / ("_scoring_" + filepath.name))
        # Actually score against original path for test detection
        score_after = score_script(filepath, new_code)
    finally:
        try:
            score_path.unlink()
        except Exception:
            pass
        try:
            tmp_path.unlink()
        except Exception:
            pass

    if verbose:
        print("\n  Score: %d -> %d (%+d)" % (
            score_before["score"], score_after["score"],
            score_after["score"] - score_before["score"],
        ))
        dim_before = score_before["dimensions"][dim]["score"]
        dim_after = score_after["dimensions"][dim]["score"]
        print("  %s: %d -> %d (%+d)" % (dim, dim_before, dim_after, dim_after - dim_before))

    # Score gate
    drop = score_before["score"] - score_after["score"]
    if drop > SCORE_DROP_THRESHOLD:
        reason = "Score dropped %d points (%d->%d)" % (
            drop, score_before["score"], score_after["score"],
        )
        if verbose:
            print("  ROLLBACK: %s" % reason)
        return {
            "status": "rolled_back",
            "reason": reason,
            "score_before": score_before,
            "score_after": score_after,
        }

    # Archive and write
    archive_version(filepath, next_gen)
    if verbose:
        print("  Archived: v%d.py" % next_gen)

    filepath.write_text(new_code, encoding="utf-8")
    if verbose:
        print("  Written: %s" % filepath)

    # Log
    prev_sha = hashlib.sha256(code.encode()).hexdigest()
    new_sha = hashlib.sha256(new_code.encode()).hexdigest()
    append_log(filepath, {
        "generation": next_gen,
        "date": date.today().isoformat(),
        "target_dimension": dim,
        "score_before": score_before["score"],
        "score_after": score_after["score"],
        "delta": score_after["score"] - score_before["score"],
        "dim_before": score_before["dimensions"][dim]["score"],
        "dim_after": score_after["dimensions"][dim]["score"],
        "mode": "surgical" if surgical else "rewrite",
        "previousSize": len(code),
        "newSize": len(new_code),
        "previousSha256": prev_sha,
        "newSha256": new_sha,
    })

    return {
        "status": "success",
        "file": filepath.name,
        "generation": next_gen,
        "target_dimension": dim,
        "score_before": score_before,
        "score_after": score_after,
        "delta": score_after["score"] - score_before["score"],
    }


# ─── Score All Scripts ───────────────────────────────────────────────────────


def score_all_scripts(verbose: bool = False) -> list:
    """Score every Python script in scripts/."""
    results = []
    for py_file in sorted(SCRIPTS_DIR.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name.startswith("test_"):
            continue
        try:
            result = score_script(py_file)
            results.append(result)
        except Exception as e:
            if verbose:
                print("  Error scoring %s: %s" % (py_file.name, e))

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point for self-molt."""
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or dry_run
    surgical = "--surgical" in args
    score_only = "--score" in args
    score_all = "--score-all" in args

    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}

    # Parse --target-dim
    target_dim = None
    if "--target-dim" in args:
        idx = args.index("--target-dim")
        if idx + 1 < len(args):
            target_dim = args[idx + 1]

    # ── Score all mode ──
    if score_all:
        results = score_all_scripts(verbose)
        print("\n%-35s %5s %5s  %-18s %s" % ("File", "Score", "Grade", "Weakest", "Details"))
        print("-" * 95)
        for r in results:
            wd = r["weakest_dimension"]
            ws = r["weakest_score"]
            dets = ", ".join(r["dimensions"][wd]["details"][:3])
            print("%-35s %3d/100  %-2s   %-18s %s" % (
                r["file"][:35], r["score"], r["grade"], wd + " " + ws, dets[:30],
            ))
        avg = sum(r["score"] for r in results) / len(results) if results else 0
        print("\n%d scripts scored. Average: %.1f/100" % (len(results), avg))
        return 0

    # ── Resolve target file ──
    if positional:
        filepath = Path(positional[0]).resolve()
    else:
        filepath = Path(__file__).resolve()

    if not filepath.exists():
        print("ERROR: File not found: %s" % filepath)
        return 1

    # ── Score only mode ──
    if score_only:
        result = score_script(filepath)
        print(format_scorecard(result))
        return 0

    # ── Molt mode ──
    backend = detect_backend()
    if backend != "copilot-cli" and not dry_run:
        print("ERROR: Copilot CLI not available. Use --dry-run or --score.")
        return 1

    print("self-molt: target = %s" % filepath.name)
    print("self-molt: mode = %s" % ("surgical" if surgical else "rewrite"))
    if target_dim:
        print("self-molt: forced dimension = %s" % target_dim)

    result = self_molt(
        filepath=filepath,
        dry_run=dry_run,
        verbose=verbose,
        surgical=surgical,
        target_dim=target_dim,
    )

    if result["status"] == "success":
        print("\n✅ SUCCESS: %s molted to gen %d" % (result["file"], result["generation"]))
        print("   Score: %d -> %d (%+d)" % (
            result["score_before"]["score"],
            result["score_after"]["score"],
            result["delta"],
        ))
        print("   Dimension: %s" % result["target_dimension"])
    elif result["status"] == "dry_run":
        print("\n🔍 DRY RUN: would molt %s (gen %d)" % (result["file"], result["generation"]))
        print("   Target: %s" % result["target_dimension"])
    elif result["status"] == "rolled_back":
        print("\n⏪ ROLLED BACK: %s" % result["reason"])
    elif result["status"] == "rejected":
        print("\n🚫 REJECTED: %s" % result["reason"])
    elif result["status"] == "skipped":
        print("\n⏭️  SKIPPED: %s" % result["reason"])
    else:
        print("\n❌ FAILED: %s" % result.get("reason", "unknown"))

    return 0 if result["status"] in ("success", "dry_run", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
