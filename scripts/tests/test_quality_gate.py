#!/usr/bin/env python3
"""Quality gate tests for RappterZoo HTML apps.

Parametrized tests that validate structural quality, scale, systems,
completeness, playability, and polish of any HTML app.

Usage:
    # Gate specific new files
    pytest scripts/tests/test_quality_gate.py -v --new-files apps/educational/physics-playground.html

    # Full suite (all apps in manifest)
    pytest scripts/tests/test_quality_gate.py -v

    # Adjust thresholds
    pytest scripts/tests/test_quality_gate.py -v --gate-threshold 50 --game-threshold 55
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# ──────────────────────────────────────────────
# TestStructural: 6 tests
# ──────────────────────────────────────────────
class TestStructural:
    def test_has_doctype(self, html_file, html_content):
        assert "<!DOCTYPE html>" in html_content or "<!doctype html>" in html_content, \
            f"{html_file.name}: Missing <!DOCTYPE html>"

    def test_has_viewport(self, html_file, html_content):
        assert '<meta name="viewport"' in html_content, \
            f"{html_file.name}: Missing viewport meta tag"

    def test_has_title(self, html_file, html_content):
        match = re.search(r"<title>(.*?)</title>", html_content)
        assert match and len(match.group(1).strip()) > 2, \
            f"{html_file.name}: Missing or empty <title>"

    def test_has_inline_css(self, html_file, html_content):
        assert "<style>" in html_content and "</style>" in html_content, \
            f"{html_file.name}: Missing inline <style> block"

    def test_has_inline_js(self, html_file, html_content):
        assert "<script>" in html_content and "</script>" in html_content, \
            f"{html_file.name}: Missing inline <script> block"

    def test_no_external_deps(self, html_file, html_content):
        ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', html_content)
        # Allow known safe external refs (fonts, etc) but fail on JS/CSS CDN
        bad = [u for u in ext if any(u.endswith(e) for e in ('.js', '.css', '.mjs'))]
        assert len(bad) == 0, \
            f"{html_file.name}: External dependencies found: {bad}"


# ──────────────────────────────────────────────
# TestScale: 3 tests
# ──────────────────────────────────────────────
class TestScale:
    def test_min_lines(self, html_file, html_content):
        lines = html_content.count("\n") + 1
        assert lines >= 100, \
            f"{html_file.name}: Only {lines} lines (minimum 100)"

    def test_min_size(self, html_file, html_content):
        size_kb = len(html_content) / 1024
        assert size_kb >= 5, \
            f"{html_file.name}: Only {size_kb:.1f}KB (minimum 5KB)"

    def test_not_empty_shell(self, html_file, html_content):
        """File must have substantial content, not just boilerplate."""
        # Check for at least some meaningful JS
        script_match = re.search(r"<script>(.*?)</script>", html_content, re.DOTALL)
        assert script_match and len(script_match.group(1).strip()) > 200, \
            f"{html_file.name}: Script content too minimal — appears to be an empty shell"


# ──────────────────────────────────────────────
# TestSystems: 2 tests
# ──────────────────────────────────────────────
class TestSystems:
    def test_has_interactive_system(self, html_file, html_content):
        """Must have canvas, DOM manipulation, or form interaction."""
        has_canvas = bool(re.search(r"canvas|getContext\(['\"]2d['\"]\)|WebGL", html_content, re.IGNORECASE))
        has_dom = bool(re.search(r"getElementById|querySelector|innerHTML|textContent|createElement", html_content))
        has_form = bool(re.search(r"<input|<select|<textarea|<button|<form", html_content, re.IGNORECASE))
        assert has_canvas or has_dom or has_form, \
            f"{html_file.name}: No interactive system (canvas/DOM/form) found"

    def test_has_event_handling(self, html_file, html_content):
        """Must handle user events."""
        has_events = bool(re.search(
            r"addEventListener|onclick|onchange|onkeydown|onmousedown|oninput|ontouchstart",
            html_content, re.IGNORECASE
        ))
        assert has_events, \
            f"{html_file.name}: No event handling found"


# ──────────────────────────────────────────────
# TestCompleteness: 2 tests (games only)
# ──────────────────────────────────────────────
class TestCompleteness:
    def test_has_scoring(self, html_file, html_content, is_game):
        if not is_game:
            pytest.skip("Not a game")
        has_score = bool(re.search(
            r"\bscore\b.*[+=]|updateScore|addScore|points|score\s*:|score\s*=",
            html_content, re.IGNORECASE
        ))
        assert has_score, f"{html_file.name}: Game has no scoring system"

    def test_has_game_over(self, html_file, html_content, is_game):
        if not is_game:
            pytest.skip("Not a game")
        has_game_over = bool(re.search(
            r"game.?over|gameOver|game_over|you (died|lose|lost|win|won)|endGame|gameEnd",
            html_content, re.IGNORECASE
        ))
        assert has_game_over, f"{html_file.name}: Game has no game-over condition"


# ──────────────────────────────────────────────
# TestPlayability: 2 tests (games only)
# ──────────────────────────────────────────────
class TestPlayability:
    def test_has_feedback(self, html_file, html_content, is_game):
        if not is_game:
            pytest.skip("Not a game")
        patterns = [
            r"shake|flash|blink|pulse|glow|vibrat",
            r"combo|multiplier|streak",
            r"particle|emitter|explosion|burst",
            r"animation|animate|transition",
            r"sound|audio|play\(",
        ]
        has_feedback = any(re.search(p, html_content, re.IGNORECASE) for p in patterns)
        assert has_feedback, f"{html_file.name}: Game lacks feedback/juice effects"

    def test_has_keyboard_controls(self, html_file, html_content, is_game):
        if not is_game:
            pytest.skip("Not a game")
        has_keys = bool(re.search(
            r"keydown|keyup|keypress|KeyboardEvent|key\s*===?\s*['\"]",
            html_content, re.IGNORECASE
        ))
        has_mouse = bool(re.search(
            r"click|mousedown|mouseup|mousemove|touchstart",
            html_content, re.IGNORECASE
        ))
        assert has_keys or has_mouse, \
            f"{html_file.name}: Game has no keyboard or mouse controls"


# ──────────────────────────────────────────────
# TestPolish: 1 test
# ──────────────────────────────────────────────
class TestPolish:
    def test_has_polish_signal(self, html_file, html_content):
        """At least one visual polish indicator."""
        patterns = [
            r"animation|@keyframes|transition",
            r"gradient|linearGradient",
            r"shadow|boxShadow|text-shadow",
            r"hsl\(|rgba\(",
            r"blur|glow|pulse|ripple",
            r"border-radius|rounded",
        ]
        has_polish = any(re.search(p, html_content, re.IGNORECASE) for p in patterns)
        assert has_polish, f"{html_file.name}: No polish signals found"


# ──────────────────────────────────────────────
# TestQualityGate: 1 test (score threshold)
# ──────────────────────────────────────────────
class TestQualityGate:
    def test_meets_quality_threshold(self, html_file, html_content, is_game, gate_threshold, game_threshold):
        """App must meet minimum quality score."""
        from rank_games import (
            score_structural, score_scale, score_systems,
            score_completeness, score_playability, score_polish
        )
        dimensions = [
            score_structural(html_content),
            score_scale(html_content),
            score_systems(html_content),
            score_completeness(html_content),
            score_playability(html_content),
            score_polish(html_content),
        ]
        raw = sum(d["score"] for d in dimensions)
        raw_max = sum(d["max"] for d in dimensions)
        score = round(raw / raw_max * 100) if raw_max else 0
        threshold = game_threshold if is_game else gate_threshold
        breakdown = ", ".join(str(d["score"]) + "/" + str(d["max"]) for d in dimensions)
        assert score >= threshold, \
            f"{html_file.name}: Score {score} < threshold {threshold}. Breakdown: {breakdown}"


# ──────────────────────────────────────────────
# TestManifestSync: 3 tests (no parametrize)
# ──────────────────────────────────────────────
class TestManifestSync:
    """Verify manifest.json and filesystem are in sync."""

    @pytest.fixture(autouse=True)
    def load_manifest(self):
        manifest_path = Path(__file__).resolve().parent.parent.parent / "apps" / "manifest.json"
        self.manifest = json.loads(manifest_path.read_text())
        self.apps_dir = manifest_path.parent
        self.category_folders = {
            "visual_art": "visual-art",
            "3d_immersive": "3d-immersive",
            "audio_music": "audio-music",
            "generative_art": "generative-art",
            "games_puzzles": "games-puzzles",
            "particle_physics": "particle-physics",
            "creative_tools": "creative-tools",
            "experimental_ai": "experimental-ai",
            "educational_tools": "educational",
        }

    def test_every_manifest_entry_has_file(self):
        """Every app in manifest must have a corresponding HTML file."""
        missing = []
        for cat_key, cat_data in self.manifest.get("categories", {}).items():
            folder = cat_data.get("folder", self.category_folders.get(cat_key, cat_key))
            for app in cat_data.get("apps", []):
                path = self.apps_dir / folder / app["file"]
                if not path.exists():
                    missing.append(f"{folder}/{app['file']}")
        assert len(missing) == 0, f"Manifest entries without files: {missing}"

    def test_counts_match(self):
        """Category count fields must match actual app array lengths."""
        mismatches = []
        for cat_key, cat_data in self.manifest.get("categories", {}).items():
            declared = cat_data.get("count", 0)
            actual = len(cat_data.get("apps", []))
            if declared != actual:
                mismatches.append(f"{cat_key}: declared={declared}, actual={actual}")
        assert len(mismatches) == 0, f"Count mismatches: {mismatches}"

    def test_no_duplicate_files(self):
        """No duplicate filenames within a category."""
        dupes = []
        for cat_key, cat_data in self.manifest.get("categories", {}).items():
            files = [a["file"] for a in cat_data.get("apps", [])]
            seen = set()
            for f in files:
                if f in seen:
                    dupes.append(f"{cat_key}/{f}")
                seen.add(f)
        assert len(dupes) == 0, f"Duplicate files: {dupes}"
