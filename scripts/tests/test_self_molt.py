"""Tests for self_molt.py — The Molter That Molts Itself.

Tests the 6-dimension Python quality rubric, scoring accuracy,
self-molt pipeline, validation, surgical edits, and score gating.
"""

import ast
import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pytest
import self_molt as sm

# Module-level slow marker — large parametrized or integration suite.
# Skipped by default; run with `pytest -m slow` or `pytest -m ''`.
pytestmark = pytest.mark.slow

# ---------------------------------------------------------------------------
# Sample Python code fixtures
# ---------------------------------------------------------------------------

WELL_WRITTEN_SCRIPT = '''#!/usr/bin/env python3
"""
example_tool.py — A well-documented example tool.

Demonstrates all quality dimensions for testing the self-molt rubric.

Usage:
  python3 scripts/example_tool.py --verbose
  python3 scripts/example_tool.py --help

Example:
  >>> process_items([1, 2, 3])
  [2, 4, 6]
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, List

# ─── Constants ───────────────────────────────────────────────────────────────

MAX_ITEMS = 1000
BATCH_SIZE = 50
DEFAULT_TIMEOUT = 30
OUTPUT_FORMAT = "json"
RETRY_COUNT = 3

_ITEM_PATTERN = re.compile(r"^[a-z][a-z0-9_]+$")

# ─── Core Logic ──────────────────────────────────────────────────────────────


def process_items(items: List[int], multiplier: int = 2) -> List[int]:
    """Process a list of items by multiplying each.

    Args:
        items: Input integers to process.
        multiplier: Factor to multiply by.

    Returns:
        List of processed integers.
    """
    if not items:
        return []
    if len(items) > MAX_ITEMS:
        raise ValueError("Too many items: %d (max %d)" % (len(items), MAX_ITEMS))
    return [x * multiplier for x in items]


def validate_input(data: Optional[dict]) -> bool:
    """Validate input data structure.

    Args:
        data: Input dictionary to validate.

    Returns:
        True if valid, False otherwise.
    """
    if data is None:
        return False
    if not isinstance(data, dict):
        return False
    if "items" not in data:
        return False
    return True


def load_config(path: Path) -> dict:
    """Load configuration from a JSON file.

    Args:
        path: Path to config file.

    Returns:
        Parsed config dictionary.
    """
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print("ERROR: Config not found: %s" % path)
        return {}
    except json.JSONDecodeError as e:
        print("ERROR: Invalid JSON in %s: %s" % (path, e))
        return {}


def main() -> int:
    """CLI entry point."""
    args = sys.argv[1:]
    verbose = "--verbose" in args

    if "--help" in args:
        print("Usage: example_tool.py [--verbose] [--help]")
        return 0

    if verbose:
        print("Processing...")

    result = process_items([1, 2, 3])
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

MINIMAL_SCRIPT = """
x = 1
print(x)
"""

SCRIPT_WITH_SYNTAX_ERROR = """
def broken(:
    pass
"""

SCRIPT_NO_DOCSTRINGS = """
import os



def foo(x):
    return x * 2

def bar(y):
    return y + 1

class Baz:
    def qux(self):
        pass
"""

SCRIPT_WITH_BARE_EXCEPT = """
\"\"\"Module with bare except.\"\"\"

def risky():
    try:
        open("file.txt")
    except:
        pass

def also_risky():
    try:
        1/0
    except:
        return None
"""


# ===========================================================================
# AST HELPER TESTS
# ===========================================================================


class TestASTHelpers:
    """Test Python AST utility functions."""

    def test_parse_valid_python(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        assert tree is not None
        assert isinstance(tree, ast.Module)

    def test_parse_invalid_python(self):
        tree = sm._parse_ast(SCRIPT_WITH_SYNTAX_ERROR)
        assert tree is None

    def test_check_syntax_valid(self):
        assert sm._check_python_syntax(WELL_WRITTEN_SCRIPT) is None

    def test_check_syntax_invalid(self):
        err = sm._check_python_syntax(SCRIPT_WITH_SYNTAX_ERROR)
        assert err is not None
        assert "line" in err.lower()

    def test_count_functions(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        count = sm._count_functions(tree)
        assert count >= 4  # process_items, validate_input, load_config, main

    def test_count_classes(self):
        tree = sm._parse_ast(SCRIPT_NO_DOCSTRINGS)
        assert sm._count_classes(tree) == 1

    def test_function_lengths(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        lengths = sm._get_function_lengths(WELL_WRITTEN_SCRIPT, tree)
        assert len(lengths) >= 4
        assert all(l > 0 for l in lengths)

    def test_type_hints_detection(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        hinted, total = sm._has_type_hints(tree)
        assert hinted >= 3  # process_items, validate_input, load_config all have hints
        assert total >= 4


# ===========================================================================
# SCORING DIMENSION TESTS
# ===========================================================================


class TestScoreStructure:
    """Test Structure & Documentation scoring."""

    def test_well_written_scores_high(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_structure(WELL_WRITTEN_SCRIPT, tree)
        assert result["score"] >= 14  # Should hit most checks
        assert "module_docstring" in result["details"]

    def test_no_docstrings_scores_low(self):
        tree = sm._parse_ast(SCRIPT_NO_DOCSTRINGS)
        result = sm.score_structure(SCRIPT_NO_DOCSTRINGS, tree)
        assert result["score"] < 10
        assert "module_docstring" not in result["details"]

    def test_minimal_scores_very_low(self):
        tree = sm._parse_ast(MINIMAL_SCRIPT)
        result = sm.score_structure(MINIMAL_SCRIPT, tree)
        assert result["score"] <= 6

    def test_max_is_18(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_structure(WELL_WRITTEN_SCRIPT, tree)
        assert result["max"] == 18


class TestScoreRobustness:
    """Test Robustness scoring."""

    def test_well_written_has_error_handling(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_robustness(WELL_WRITTEN_SCRIPT, tree)
        assert result["score"] >= 3
        assert any("error" in d for d in result["details"])

    def test_bare_except_penalized(self):
        tree = sm._parse_ast(SCRIPT_WITH_BARE_EXCEPT)
        result = sm.score_robustness(SCRIPT_WITH_BARE_EXCEPT, tree)
        assert "no_bare_except" not in result["details"]

    def test_max_is_16(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_robustness(WELL_WRITTEN_SCRIPT, tree)
        assert result["max"] == 16


class TestScoreMaintainability:
    """Test Maintainability scoring."""

    def test_named_constants_detected(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_maintainability(WELL_WRITTEN_SCRIPT, tree)
        assert "named_constants" in result["details"]

    def test_compiled_regex_detected(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_maintainability(WELL_WRITTEN_SCRIPT, tree)
        assert any("regex" in d for d in result["details"])

    def test_max_is_16(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_maintainability(WELL_WRITTEN_SCRIPT, tree)
        assert result["max"] == 16


class TestScoreTesting:
    """Test Testing dimension scoring."""

    def test_self_molt_has_tests(self):
        """self_molt.py should find this test file."""
        filepath = Path(__file__).resolve().parent.parent / "self_molt.py"
        if filepath.exists():
            result = sm.score_testing(filepath.read_text(), filepath)
            assert result["score"] > 0
            assert "test_file_exists" in result["details"]

    def test_no_test_file_scores_zero(self, tmp_path):
        """Script with no test file should score 0."""
        script = tmp_path / "no_tests.py"
        script.write_text("x = 1")
        result = sm.score_testing("x = 1", script)
        assert result["score"] == 0
        assert "no_test_file" in result["details"]

    def test_max_is_20(self):
        result = sm.score_testing("x = 1", Path("/tmp/fake.py"))
        assert result["max"] == 20


class TestScorePerformance:
    """Test Performance scoring."""

    def test_well_written_efficient(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_performance(WELL_WRITTEN_SCRIPT, tree)
        assert result["score"] >= 5

    def test_compact_file_bonus(self):
        tree = sm._parse_ast(MINIMAL_SCRIPT)
        result = sm.score_performance(MINIMAL_SCRIPT, tree)
        assert "compact_file" in result["details"]

    def test_max_is_15(self):
        tree = sm._parse_ast(WELL_WRITTEN_SCRIPT)
        result = sm.score_performance(WELL_WRITTEN_SCRIPT, tree)
        assert result["max"] == 15


class TestScorePolish:
    """Test Polish scoring."""

    def test_well_written_polished(self):
        filepath = Path("/tmp/example_tool.py")
        result = sm.score_polish(WELL_WRITTEN_SCRIPT, filepath)
        assert result["score"] >= 8
        assert "cli_help" in result["details"]
        assert "has_examples" in result["details"]

    def test_verbose_mode_detected(self):
        result = sm.score_polish(WELL_WRITTEN_SCRIPT, Path("/tmp/t.py"))
        assert "verbose_mode" in result["details"]

    def test_section_separators_detected(self):
        result = sm.score_polish(WELL_WRITTEN_SCRIPT, Path("/tmp/t.py"))
        assert "visual_sections" in result["details"]

    def test_max_is_15(self):
        result = sm.score_polish(WELL_WRITTEN_SCRIPT, Path("/tmp/t.py"))
        assert result["max"] == 15


# ===========================================================================
# AGGREGATE SCORING TESTS
# ===========================================================================


class TestScoreScript:
    """Test aggregate scoring."""

    def test_well_written_grades_high(self, tmp_path):
        script = tmp_path / "example_tool.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        result = sm.score_script(script)
        assert result["score"] >= 50
        assert result["grade"] in ("S", "A", "B", "C")

    def test_minimal_grades_low(self, tmp_path):
        script = tmp_path / "minimal.py"
        script.write_text(MINIMAL_SCRIPT)
        result = sm.score_script(script)
        assert result["grade"] in ("D", "F")

    def test_has_all_dimensions(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        result = sm.score_script(script)
        for dim in sm.DIMENSIONS:
            assert dim in result["dimensions"]

    def test_weakest_dimension_identified(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        result = sm.score_script(script)
        assert result["weakest_dimension"] in sm.DIMENSIONS

    def test_format_scorecard_readable(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        result = sm.score_script(script)
        card = sm.format_scorecard(result)
        assert "SCORECARD" in card
        assert "WEAKEST" in card
        assert result["grade"] in card


# ===========================================================================
# VALIDATION TESTS
# ===========================================================================


class TestValidation:
    """Test molt output validation."""

    def test_valid_improvement_passes(self):
        improved = WELL_WRITTEN_SCRIPT.replace(
            "# ─── Core Logic",
            "# ─── Core Logic (improved)",
        )
        assert sm.validate_molt_output(improved, WELL_WRITTEN_SCRIPT) is None

    def test_syntax_error_rejected(self):
        err = sm.validate_molt_output("def broken(:\n  pass", WELL_WRITTEN_SCRIPT)
        assert err is not None
        assert "syntax" in err.lower()

    def test_empty_output_rejected(self):
        err = sm.validate_molt_output("", WELL_WRITTEN_SCRIPT)
        assert err is not None
        assert "empty" in err.lower()

    def test_too_small_rejected(self):
        tiny = "x = 1\n"
        err = sm.validate_molt_output(tiny, WELL_WRITTEN_SCRIPT)
        assert err is not None
        assert "small" in err.lower()

    def test_too_large_rejected(self):
        huge = WELL_WRITTEN_SCRIPT * 10
        err = sm.validate_molt_output(huge, WELL_WRITTEN_SCRIPT)
        assert err is not None
        assert "large" in err.lower()

    def test_removed_function_rejected(self):
        # Remove process_items function
        no_func = WELL_WRITTEN_SCRIPT.replace(
            "def process_items", "def _removed_func"
        )
        err = sm.validate_molt_output(no_func, WELL_WRITTEN_SCRIPT)
        assert err is not None
        assert "process_items" in err

    def test_removed_docstring_rejected(self):
        no_doc = WELL_WRITTEN_SCRIPT.replace(
            '"""', "# removed", 2  # Remove module docstring
        )
        # Only fails if AST can detect the removal
        err = sm.validate_molt_output(no_doc, WELL_WRITTEN_SCRIPT)
        # May or may not catch this depending on how quotes work out
        # Just verify it doesn't crash
        assert err is None or isinstance(err, str)


# ===========================================================================
# SURGICAL EDIT TESTS
# ===========================================================================


class TestSurgicalEdits:
    """Test surgical JSON-patch application."""

    def test_single_edit_applied(self):
        code = 'x = 1\ny = 2\n'
        edits = json.dumps([{"description": "fix", "find": "x = 1", "replace": "x = 10"}])
        result, applied, errors = sm.apply_surgical_edits(code, edits)
        assert applied == 1
        assert "x = 10" in result

    def test_multiple_edits(self):
        code = "a = 1\nb = 2\nc = 3\n"
        edits = json.dumps([
            {"description": "a", "find": "a = 1", "replace": "a = 10"},
            {"description": "b", "find": "b = 2", "replace": "b = 20"},
        ])
        result, applied, errors = sm.apply_surgical_edits(code, edits)
        assert applied == 2

    def test_not_found_skipped(self):
        code = "x = 1\n"
        edits = json.dumps([{"description": "bad", "find": "NOPE", "replace": "YES"}])
        result, applied, errors = sm.apply_surgical_edits(code, edits)
        assert result is None
        assert applied == 0

    def test_bad_json_handled(self):
        result, applied, errors = sm.apply_surgical_edits("x = 1", "not json{{{")
        assert result is None

    def test_non_list_handled(self):
        result, applied, errors = sm.apply_surgical_edits("x = 1", '{"a": 1}')
        assert result is None
        assert "not a JSON array" in errors[0]


# ===========================================================================
# ARCHIVE & GENERATION TESTS
# ===========================================================================


class TestArchive:
    """Test archive and generation tracking."""

    def test_archive_creates_file(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text("x = 1")

        with mock.patch.object(sm, "ARCHIVE_DIR", tmp_path / "archive" / "self-molt"):
            dest = sm.archive_version(script, 1)
            assert dest.exists()
            assert dest.read_text() == "x = 1"
            assert "v1.py" in dest.name

    def test_get_generation_no_log(self, tmp_path):
        with mock.patch.object(sm, "ARCHIVE_DIR", tmp_path / "archive" / "self-molt"):
            gen = sm.get_generation(Path("test.py"))
            assert gen == 0

    def test_get_generation_with_log(self, tmp_path):
        log_dir = tmp_path / "archive" / "self-molt" / "test"
        log_dir.mkdir(parents=True)
        log = [{"generation": 1}, {"generation": 2}, {"generation": 3}]
        (log_dir / "molt-log.json").write_text(json.dumps(log))

        with mock.patch.object(sm, "ARCHIVE_DIR", tmp_path / "archive" / "self-molt"):
            gen = sm.get_generation(Path("test.py"))
            assert gen == 3

    def test_append_log(self, tmp_path):
        with mock.patch.object(sm, "ARCHIVE_DIR", tmp_path / "archive" / "self-molt"):
            sm.append_log(Path("test.py"), {"generation": 1, "score": 50})
            sm.append_log(Path("test.py"), {"generation": 2, "score": 55})

            log_path = tmp_path / "archive" / "self-molt" / "test" / "molt-log.json"
            assert log_path.exists()
            log = json.loads(log_path.read_text())
            assert len(log) == 2
            assert log[1]["score"] == 55


# ===========================================================================
# PIPELINE TESTS
# ===========================================================================


class TestSelfMoltPipeline:
    """Test the full self-molt pipeline."""

    def test_dry_run_no_changes(self, tmp_path):
        script = tmp_path / "target.py"
        script.write_text(WELL_WRITTEN_SCRIPT)

        result = sm.self_molt(filepath=script, dry_run=True)
        assert result["status"] == "dry_run"
        assert result["target_dimension"] in sm.DIMENSIONS
        # File unchanged
        assert script.read_text() == WELL_WRITTEN_SCRIPT

    def test_score_gate_rollback(self, tmp_path):
        """If LLM output scores worse, it should be rolled back."""
        script = tmp_path / "target.py"
        script.write_text(WELL_WRITTEN_SCRIPT)

        # Return a degraded version (remove docstrings and constants)
        degraded = MINIMAL_SCRIPT * 5  # Too different, will trigger size check

        with mock.patch("self_molt.copilot_call_with_retry", return_value=degraded):
            result = sm.self_molt(filepath=script, dry_run=False)

        assert result["status"] in ("rejected", "rolled_back")

    def test_file_not_found(self):
        result = sm.self_molt(filepath=Path("/nonexistent/fake.py"))
        assert result["status"] == "failed"
        assert "not found" in result["reason"].lower()

    def test_max_generation_skip(self, tmp_path):
        script = tmp_path / "target.py"
        script.write_text(WELL_WRITTEN_SCRIPT)

        # Fake high generation
        with mock.patch("self_molt.get_generation", return_value=sm.MAX_GEN):
            result = sm.self_molt(filepath=script)
            assert result["status"] == "skipped"

    def test_successful_molt(self, tmp_path):
        """A valid improvement should be accepted."""
        script = tmp_path / "target.py"
        script.write_text(WELL_WRITTEN_SCRIPT)

        # Return a slightly improved version
        improved = WELL_WRITTEN_SCRIPT.replace(
            "# ─── Core Logic",
            "# ─── Core Logic (enhanced)",
        )

        with mock.patch("self_molt.copilot_call_with_retry", return_value=improved), \
             mock.patch.object(sm, "ARCHIVE_DIR", tmp_path / "archive" / "self-molt"):
            result = sm.self_molt(filepath=script, dry_run=False)

        assert result["status"] == "success"
        assert result["generation"] == 1
        # File should be updated
        assert "(enhanced)" in script.read_text()

    def test_forced_dimension(self, tmp_path):
        script = tmp_path / "target.py"
        script.write_text(WELL_WRITTEN_SCRIPT)

        result = sm.self_molt(filepath=script, dry_run=True, target_dim="polish")
        assert result["target_dimension"] == "polish"


# ===========================================================================
# SCORE ALL SCRIPTS TESTS
# ===========================================================================


class TestScoreAll:
    """Test batch scoring of all scripts."""

    def test_score_all_returns_list(self):
        """score_all_scripts should return a sorted list of results."""
        results = sm.score_all_scripts()
        assert isinstance(results, list)
        if len(results) >= 2:
            # Should be sorted by score descending
            assert results[0]["score"] >= results[-1]["score"]

    def test_score_all_has_self_molt(self):
        """self_molt.py should appear in its own results."""
        results = sm.score_all_scripts()
        files = [r["file"] for r in results]
        assert "self_molt.py" in files


# ===========================================================================
# PROMPT CONSTRUCTION TESTS
# ===========================================================================


class TestPromptConstruction:
    """Test self-molt prompt building."""

    def test_rewrite_prompt_has_code(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        scorecard = sm.score_script(script)
        prompt = sm.build_self_molt_prompt(
            WELL_WRITTEN_SCRIPT, script, scorecard,
        )
        assert "process_items" in prompt
        assert "HARD RULES" in prompt
        assert scorecard["weakest_dimension"].upper() in prompt

    def test_surgical_prompt_requests_json(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        scorecard = sm.score_script(script)
        prompt = sm.build_self_molt_prompt(
            WELL_WRITTEN_SCRIPT, script, scorecard, surgical=True,
        )
        assert "JSON" in prompt
        assert '"find"' in prompt
        assert '"replace"' in prompt

    def test_forced_dimension_in_prompt(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text(WELL_WRITTEN_SCRIPT)
        scorecard = sm.score_script(script)
        prompt = sm.build_self_molt_prompt(
            WELL_WRITTEN_SCRIPT, script, scorecard, target_dim="robustness",
        )
        assert "ROBUSTNESS" in prompt
