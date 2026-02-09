"""
Tests for the molting generations pipeline (scripts/molt.py).

All LLM calls are mocked -- no network needed.
"""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# We need to set up paths before importing molt
ROOT = Path(__file__).resolve().parent.parent.parent


# ─── Fixtures ─────────────────────────────────────────────────────────────────


SAMPLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Memory Training Game</title>
<meta name="description" content="A memory card matching game">
<style>
  body { margin: 0; font-family: sans-serif; background: #1a1a2e; color: white; }
  .card { width: 100px; height: 100px; background: #333; border-radius: 8px; cursor: pointer; }
</style>
</head>
<body>
<h1>Memory Training Game</h1>
<div id="grid"></div>
<script>
  const cards = [];
  function init() {
    const grid = document.getElementById('grid');
    for (let i = 0; i < 16; i++) {
      const card = document.createElement('div');
      card.className = 'card';
      card.addEventListener('click', () => flip(i));
      grid.appendChild(card);
      cards.push(card);
    }
  }
  function flip(index) {
    cards[index].classList.toggle('flipped');
  }
  init();
</script>
</body>
</html>"""

IMPROVED_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Memory Training Game</title>
<meta name="description" content="A memory card matching game">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, sans-serif; background: #1a1a2e; color: #fff; }
  .card { width: 100px; height: 100px; background: #333; border-radius: 8px; cursor: pointer; }
  .card:focus { outline: 2px solid #4dabf7; }
</style>
</head>
<body>
<h1>Memory Training Game</h1>
<main id="grid" role="grid" aria-label="Memory card grid"></main>
<script>
  const cards = [];
  function init() {
    const grid = document.getElementById('grid');
    for (let i = 0; i < 16; i++) {
      const card = document.createElement('div');
      card.className = 'card';
      card.setAttribute('role', 'gridcell');
      card.setAttribute('tabindex', '0');
      card.addEventListener('click', () => flip(i));
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') flip(i);
      });
      grid.appendChild(card);
      cards.push(card);
    }
  }
  function flip(index) {
    cards[index].classList.toggle('flipped');
  }
  init();
</script>
</body>
</html>"""

SAMPLE_MANIFEST = {
    "categories": {
        "games_puzzles": {
            "title": "Games & Puzzles",
            "folder": "games-puzzles",
            "color": "#f59e0b",
            "count": 2,
            "apps": [
                {
                    "title": "Memory Training Game",
                    "file": "memory-training-game.html",
                    "description": "A memory card matching game",
                    "tags": ["game", "interactive"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2025-12-27",
                },
                {
                    "title": "Snake Game",
                    "file": "snake-game.html",
                    "description": "Classic snake game",
                    "tags": ["game", "canvas"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2025-12-27",
                },
            ],
        },
        "visual_art": {
            "title": "Visual Art & Design",
            "folder": "visual-art",
            "color": "#ff6b9d",
            "count": 1,
            "apps": [
                {
                    "title": "Pixel Painter",
                    "file": "pixel-painter.html",
                    "description": "Draw pixel art",
                    "tags": ["canvas", "creative"],
                    "complexity": "simple",
                    "type": "drawing",
                    "featured": False,
                    "created": "2025-12-27",
                },
            ],
        },
    },
    "meta": {"version": "1.0", "lastUpdated": "2025-12-27"},
}


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project structure mimicking the real repo."""
    apps_dir = tmp_path / "apps"
    games_dir = apps_dir / "games-puzzles"
    visual_dir = apps_dir / "visual-art"
    archive_dir = apps_dir / "archive"

    games_dir.mkdir(parents=True)
    visual_dir.mkdir(parents=True)

    # Write sample app
    (games_dir / "memory-training-game.html").write_text(SAMPLE_HTML)
    (games_dir / "snake-game.html").write_text(SAMPLE_HTML)
    (visual_dir / "pixel-painter.html").write_text(SAMPLE_HTML)

    # Write manifest
    (apps_dir / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST, indent=2))

    return tmp_path


# ─── Import molt module with patched paths ────────────────────────────────────


def _import_molt():
    """Import molt module."""
    import importlib
    import sys

    # Add scripts to path if not already there
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import molt
    return molt


molt_mod = _import_molt()


# ─── Prompt Construction Tests ────────────────────────────────────────────────


class TestBuildMoltPrompt:
    """Test generation-aware prompt construction."""

    def test_gen1_structural_focus(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=1)
        assert "GENERATION 1" in prompt
        assert "structural" in prompt.lower() or "Structural" in prompt
        assert "DOCTYPE" in prompt
        assert "semantic" in prompt.lower()

    def test_gen2_accessibility_focus(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=2)
        assert "GENERATION 2" in prompt
        assert "accessibility" in prompt.lower() or "Accessibility" in prompt
        assert "ARIA" in prompt or "aria" in prompt

    def test_gen3_performance_focus(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=3)
        assert "GENERATION 3" in prompt
        assert "performance" in prompt.lower() or "Performance" in prompt

    def test_gen4_polish_focus(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=4)
        assert "GENERATION 4" in prompt
        assert "polish" in prompt.lower() or "Polish" in prompt

    def test_gen5_refinement_focus(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=5)
        assert "GENERATION 5" in prompt
        assert "refine" in prompt.lower() or "Refine" in prompt

    def test_prompt_includes_html_content(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=1)
        assert "Memory Training Game" in prompt

    def test_prompt_includes_hard_rules(self):
        prompt = molt_mod.build_molt_prompt(SAMPLE_HTML, "test.html", generation=1)
        assert "Do NOT add new features" in prompt or "Do not add new features" in prompt.lower() or "NOT add new features" in prompt
        assert "self-contained" in prompt.lower()


# ─── Validation Tests ─────────────────────────────────────────────────────────


class TestValidateMoltOutput:
    """Test HTML output validation."""

    def test_valid_html_passes(self):
        result = molt_mod.validate_molt_output(IMPROVED_HTML, len(SAMPLE_HTML))
        assert result is True or result is None or isinstance(result, str) is False
        # Should not return an error string
        errors = molt_mod.validate_molt_output(IMPROVED_HTML, len(SAMPLE_HTML))
        assert errors is None

    def test_missing_doctype_fails(self):
        bad_html = "<html><head><title>Test</title></head><body></body></html>"
        errors = molt_mod.validate_molt_output(bad_html, 1000)
        assert errors is not None
        assert "doctype" in errors.lower() or "DOCTYPE" in errors

    def test_missing_title_fails(self):
        bad_html = "<!DOCTYPE html><html><head></head><body></body></html>"
        errors = molt_mod.validate_molt_output(bad_html, 1000)
        assert errors is not None
        assert "title" in errors.lower()

    def test_external_script_fails(self):
        bad_html = '<!DOCTYPE html><html><head><title>T</title><script src="https://cdn.example.com/lib.js"></script></head><body></body></html>'
        errors = molt_mod.validate_molt_output(bad_html, 1000)
        assert errors is not None
        assert "external" in errors.lower()

    def test_external_stylesheet_fails(self):
        bad_html = '<!DOCTYPE html><html><head><title>T</title><link rel="stylesheet" href="https://cdn.example.com/style.css"></head><body></body></html>'
        errors = molt_mod.validate_molt_output(bad_html, 1000)
        assert errors is not None
        assert "external" in errors.lower()

    def test_too_small_output_fails(self):
        tiny_html = "<!DOCTYPE html><html><head><title>T</title></head><body>x</body></html>"
        errors = molt_mod.validate_molt_output(tiny_html, 50000)
        assert errors is not None
        assert "small" in errors.lower()

    def test_too_large_output_fails(self):
        huge_html = "<!DOCTYPE html><html><head><title>T</title></head><body>" + "x" * 100000 + "</body></html>"
        errors = molt_mod.validate_molt_output(huge_html, 1000)
        assert errors is not None
        assert "large" in errors.lower()

    def test_none_input_fails(self):
        errors = molt_mod.validate_molt_output(None, 1000)
        assert errors is not None

    def test_empty_input_fails(self):
        errors = molt_mod.validate_molt_output("", 1000)
        assert errors is not None

    def test_js_syntax_error_fails(self):
        """Molt output with JS syntax errors should be rejected."""
        bad_html = '<!DOCTYPE html><html><head><title>T</title></head><body><script>if (true) { // }</script></body></html>'
        errors = molt_mod.validate_molt_output(bad_html, len(bad_html))
        assert errors is not None
        assert "syntax" in errors.lower() or "JavaScript" in errors

    def test_valid_js_passes(self):
        """Molt output with valid JS should pass."""
        good_html = '<!DOCTYPE html><html><head><title>T</title></head><body><script>const x = 1; if (x) { console.log(x); }</script></body></html>'
        errors = molt_mod.validate_molt_output(good_html, len(good_html))
        assert errors is None

    def test_unbalanced_braces_fails(self):
        """Extra closing brace should be caught."""
        bad_html = '<!DOCTYPE html><html><head><title>T</title></head><body><script>function f() { } }</script></body></html>'
        errors = molt_mod.validate_molt_output(bad_html, len(bad_html))
        assert errors is not None

    def test_shader_script_skipped(self):
        """Shader scripts should not be checked for JS syntax."""
        shader_html = '<!DOCTYPE html><html><head><title>T</title></head><body><script type="x-shader/x-vertex">attribute vec4 pos;</script><script>const x = 1;</script></body></html>'
        errors = molt_mod.validate_molt_output(shader_html, len(shader_html))
        assert errors is None


class TestBugPreventionPrompt:
    """Verify the molt prompt includes bug prevention rules."""

    def test_prompt_warns_about_css_var(self):
        prompt = molt_mod.build_molt_prompt("<html></html>", "test.html", 1)
        assert "var(--" in prompt or "CSS var" in prompt.lower()

    def test_prompt_warns_about_commented_braces(self):
        prompt = molt_mod.build_molt_prompt("<html></html>", "test.html", 1)
        assert "comment" in prompt.lower() and "brace" in prompt.lower()

    def test_prompt_warns_about_template_literals(self):
        prompt = molt_mod.build_molt_prompt("<html></html>", "test.html", 1)
        assert "//" in prompt and "${" in prompt

    def test_prompt_warns_about_optional_chaining(self):
        prompt = molt_mod.build_molt_prompt("<html></html>", "test.html", 1)
        assert "optional chaining" in prompt.lower() or "?." in prompt

    def test_prompt_warns_about_script_escaping(self):
        prompt = molt_mod.build_molt_prompt("<html></html>", "test.html", 1)
        assert "script" in prompt.lower() and "escape" in prompt.lower() or "<\\/script>" in prompt


# ─── Archive Tests ────────────────────────────────────────────────────────────


class TestArchiveOperations:
    """Test archive directory creation and file archiving."""

    def test_archive_creates_directory(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        assert not archive_dir.exists()

        src = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"
        molt_mod.archive_file(src, archive_dir, generation=1)

        assert archive_dir.exists()
        assert (archive_dir / "v1.html").exists()

    def test_archive_copies_content(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        src = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"

        molt_mod.archive_file(src, archive_dir, generation=1)

        archived = (archive_dir / "v1.html").read_text()
        assert archived == SAMPLE_HTML

    def test_archive_multiple_generations(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        src = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"

        molt_mod.archive_file(src, archive_dir, generation=1)
        molt_mod.archive_file(src, archive_dir, generation=2)

        assert (archive_dir / "v1.html").exists()
        assert (archive_dir / "v2.html").exists()


# ─── Molt Log Tests ──────────────────────────────────────────────────────────


class TestMoltLog:
    """Test audit log creation and appending."""

    def test_log_creation(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        archive_dir.mkdir(parents=True)

        entry = {
            "generation": 1,
            "date": "2026-02-07",
            "previousSize": 1000,
            "newSize": 900,
            "previousSha256": "abc",
            "newSha256": "def",
            "focus": "structural",
        }
        molt_mod.append_molt_log(archive_dir, entry)

        log_path = archive_dir / "molt-log.json"
        assert log_path.exists()
        log = json.loads(log_path.read_text())
        assert len(log) == 1
        assert log[0]["generation"] == 1

    def test_log_append(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        archive_dir.mkdir(parents=True)

        for gen in [1, 2, 3]:
            entry = {
                "generation": gen,
                "date": "2026-02-07",
                "previousSize": 1000,
                "newSize": 900,
                "previousSha256": "abc",
                "newSha256": "def",
                "focus": "structural",
            }
            molt_mod.append_molt_log(archive_dir, entry)

        log = json.loads((archive_dir / "molt-log.json").read_text())
        assert len(log) == 3
        assert [e["generation"] for e in log] == [1, 2, 3]

    def test_log_has_sha256(self, tmp_project):
        archive_dir = tmp_project / "apps" / "archive" / "memory-training-game"
        archive_dir.mkdir(parents=True)

        sha = hashlib.sha256(SAMPLE_HTML.encode()).hexdigest()
        entry = {
            "generation": 1,
            "date": "2026-02-07",
            "previousSize": len(SAMPLE_HTML),
            "newSize": len(IMPROVED_HTML),
            "previousSha256": sha,
            "newSha256": hashlib.sha256(IMPROVED_HTML.encode()).hexdigest(),
            "focus": "structural",
        }
        molt_mod.append_molt_log(archive_dir, entry)

        log = json.loads((archive_dir / "molt-log.json").read_text())
        assert log[0]["previousSha256"] == sha


# ─── Manifest Update Tests ───────────────────────────────────────────────────


class TestManifestUpdates:
    """Test backward-compatible manifest field additions."""

    def test_update_adds_generation(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        app_entry = manifest["categories"]["games_puzzles"]["apps"][0]

        molt_mod.update_manifest_entry(app_entry, generation=1, size=900)

        assert app_entry["generation"] == 1
        assert "lastMolted" in app_entry
        assert "moltHistory" in app_entry

    def test_update_preserves_existing_fields(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        app_entry = manifest["categories"]["games_puzzles"]["apps"][0]
        original_title = app_entry["title"]

        molt_mod.update_manifest_entry(app_entry, generation=1, size=900)

        assert app_entry["title"] == original_title
        assert app_entry["file"] == "memory-training-game.html"
        assert app_entry["tags"] == ["game", "interactive"]

    def test_update_appends_history(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        app_entry = manifest["categories"]["games_puzzles"]["apps"][0]

        molt_mod.update_manifest_entry(app_entry, generation=1, size=900)
        molt_mod.update_manifest_entry(app_entry, generation=2, size=850)

        assert app_entry["generation"] == 2
        assert len(app_entry["moltHistory"]) == 2
        assert app_entry["moltHistory"][0]["gen"] == 1
        assert app_entry["moltHistory"][1]["gen"] == 2


# ─── Path Resolution Tests ───────────────────────────────────────────────────


class TestResolveAppPath:
    """Test finding an app file from a bare filename or category-qualified path."""

    def test_bare_filename(self, tmp_project):
        path, cat_key, app_entry = molt_mod.resolve_app(
            "memory-training-game.html",
            _manifest=SAMPLE_MANIFEST,
            _apps_dir=tmp_project / "apps",
        )
        assert path.name == "memory-training-game.html"
        assert cat_key == "games_puzzles"

    def test_bare_filename_without_extension(self, tmp_project):
        path, cat_key, app_entry = molt_mod.resolve_app(
            "memory-training-game",
            _manifest=SAMPLE_MANIFEST,
            _apps_dir=tmp_project / "apps",
        )
        assert path.name == "memory-training-game.html"

    def test_not_found_raises(self, tmp_project):
        with pytest.raises(FileNotFoundError):
            molt_mod.resolve_app(
                "nonexistent.html",
                _manifest=SAMPLE_MANIFEST,
                _apps_dir=tmp_project / "apps",
            )


# ─── HTML Parsing Tests ──────────────────────────────────────────────────────


class TestParseHtml:
    """Test HTML extraction from LLM output."""

    def test_clean_html(self):
        from scripts.copilot_utils import parse_llm_html
        result = parse_llm_html(IMPROVED_HTML)
        assert "<!DOCTYPE html>" in result

    def test_code_fenced_html(self):
        from scripts.copilot_utils import parse_llm_html
        wrapped = "Here is the improved HTML:\n\n```html\n" + IMPROVED_HTML + "\n```\n"
        result = parse_llm_html(wrapped)
        assert "<!DOCTYPE html>" in result

    def test_ansi_codes_stripped(self):
        from scripts.copilot_utils import parse_llm_html
        ansi = "\x1b[32m" + IMPROVED_HTML + "\x1b[0m"
        result = parse_llm_html(ansi)
        assert "\x1b" not in result
        assert "<!DOCTYPE html>" in result

    def test_copilot_preamble_stripped(self):
        from scripts.copilot_utils import parse_llm_html
        with_stats = IMPROVED_HTML + "\n\nTask complete\nTotal usage est: $0.04"
        result = parse_llm_html(with_stats)
        assert "Task complete" not in result
        assert "<!DOCTYPE html>" in result

    def test_none_input(self):
        from scripts.copilot_utils import parse_llm_html
        assert parse_llm_html(None) is None

    def test_empty_input(self):
        from scripts.copilot_utils import parse_llm_html
        assert parse_llm_html("") is None


# ─── Generation Focus Tests ──────────────────────────────────────────────────


class TestGenerationFocus:
    """Test that generation numbers map to the right focus areas."""

    def test_focus_areas(self):
        assert molt_mod.get_generation_focus(1) == "structural"
        assert molt_mod.get_generation_focus(2) == "accessibility"
        assert molt_mod.get_generation_focus(3) == "performance"
        assert molt_mod.get_generation_focus(4) == "polish"
        assert molt_mod.get_generation_focus(5) == "refinement"

    def test_high_generation_wraps_to_refinement(self):
        assert molt_mod.get_generation_focus(6) == "refinement"
        assert molt_mod.get_generation_focus(10) == "refinement"


# ─── End-to-End Tests (Mocked Copilot) ───────────────────────────────────────


class TestEndToEnd:
    """End-to-end molt pipeline tests with mocked Copilot calls."""

    def test_dry_run_no_changes(self, tmp_project):
        """Dry run should not modify any files."""
        original = (tmp_project / "apps" / "games-puzzles" / "memory-training-game.html").read_text()

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=True,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

        assert result["status"] == "dry_run"
        current = (tmp_project / "apps" / "games-puzzles" / "memory-training-game.html").read_text()
        assert current == original
        assert not (tmp_project / "apps" / "archive" / "memory-training-game").exists()

    def test_successful_molt(self, tmp_project):
        """Successful molt should archive, replace, and update manifest."""
        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=False,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

        assert result["status"] == "success"
        assert result["generation"] == 1

        # Check archive was created
        archive = tmp_project / "apps" / "archive" / "memory-training-game" / "v1.html"
        assert archive.exists()
        assert archive.read_text() == SAMPLE_HTML

        # Check live file was replaced
        live = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"
        assert live.read_text() == IMPROVED_HTML

        # Check molt log
        log_path = tmp_project / "apps" / "archive" / "memory-training-game" / "molt-log.json"
        assert log_path.exists()
        log = json.loads(log_path.read_text())
        assert len(log) == 1
        assert log[0]["generation"] == 1

    def test_rejection_on_validation_failure(self, tmp_project):
        """If LLM output fails validation, original should be preserved."""
        bad_output = "<html><body>No DOCTYPE, no title</body></html>"

        with mock.patch("molt.copilot_call_with_retry", return_value=bad_output):
            result = molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=False,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

        assert result["status"] == "rejected"

        # Original should be unchanged
        live = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"
        assert live.read_text() == SAMPLE_HTML

    def test_failure_on_copilot_error(self, tmp_project):
        """If Copilot returns None, molt should fail gracefully."""
        with mock.patch("molt.copilot_call_with_retry", return_value=None):
            result = molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=False,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

        assert result["status"] == "failed"

        # Original should be unchanged
        live = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"
        assert live.read_text() == SAMPLE_HTML

    def test_max_generation_cap(self, tmp_project):
        """Should refuse to molt beyond max generations."""
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        app = manifest["categories"]["games_puzzles"]["apps"][0]
        app["generation"] = 5

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=False,
                max_gen=5,
                _manifest=manifest,
                _apps_dir=tmp_project / "apps",
            )

        assert result["status"] == "skipped"
        assert "max" in result["reason"].lower()

    def test_file_too_large(self, tmp_project):
        """Should refuse to molt files over 100KB."""
        large_html = "<!DOCTYPE html><html><head><title>T</title></head><body>" + "x" * 110000 + "</body></html>"
        (tmp_project / "apps" / "games-puzzles" / "memory-training-game.html").write_text(large_html)

        result = molt_mod.molt_app(
            "memory-training-game.html",
            dry_run=False,
            _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
            _apps_dir=tmp_project / "apps",
        )

        assert result["status"] == "skipped"
        assert "size" in result["reason"].lower() or "large" in result["reason"].lower()


# ─── Status Display Tests ────────────────────────────────────────────────────


class TestStatus:
    """Test generation status reporting."""

    def test_status_returns_all_apps(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        status = molt_mod.get_status(manifest)
        assert len(status) == 3  # 2 games + 1 visual

    def test_status_shows_generation(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 2
        status = molt_mod.get_status(manifest)
        mem_game = [s for s in status if s["file"] == "memory-training-game.html"][0]
        assert mem_game["generation"] == 2

    def test_status_default_generation_zero(self):
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        status = molt_mod.get_status(manifest)
        for s in status:
            assert s["generation"] == 0


# ─── Rollback Tests ──────────────────────────────────────────────────────────


class TestRollback:
    """Test generation rollback."""

    def test_rollback_restores_archived_version(self, tmp_project):
        # First, do a successful molt to create an archive
        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            molt_mod.molt_app(
                "memory-training-game.html",
                dry_run=False,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

        # Now live file is IMPROVED_HTML, archive has SAMPLE_HTML as v1
        live = tmp_project / "apps" / "games-puzzles" / "memory-training-game.html"
        assert live.read_text() == IMPROVED_HTML

        # Rollback to v1
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 1
        result = molt_mod.rollback_app(
            "memory-training-game",
            target_gen=1,
            _manifest=manifest,
            _apps_dir=tmp_project / "apps",
        )

        assert result["status"] == "rolled_back"
        assert live.read_text() == SAMPLE_HTML

    def test_rollback_nonexistent_version_fails(self, tmp_project):
        result = molt_mod.rollback_app(
            "memory-training-game",
            target_gen=5,
            _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
            _apps_dir=tmp_project / "apps",
        )
        assert result["status"] == "failed"
