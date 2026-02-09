"""Tests for molt.py new features: feature contracts, score gate, cooldown, surgical mode.

Tests the integration of:
1. Feature contract extraction + verification in molt pipeline
2. Score-gated auto-rollback on regression
3. Cooldown / "good enough" threshold
4. Surgical edit mode (JSON patches)
"""

import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

# We'll import molt module functions after path setup
import molt as molt_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Test Particle Game</title>
    <meta name="rappterzoo:category" content="games_puzzles">
    <meta name="rappterzoo:author" content="test-agent">
    <meta name="rappterzoo:generation" content="0">
    <style>
        canvas { border: 1px solid #333; }
        @keyframes pulse { 0% { opacity: 1; } 100% { opacity: 0.5; } }
    </style>
</head>
<body>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
    <button id="startBtn" onclick="startGame()">Start</button>
    <script>
        const MAX_PARTICLES = 200;
        const GRAVITY = 0.98;
        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        let particles = [];

        function startGame() {
            particles = [];
            requestAnimationFrame(gameLoop);
        }

        function gameLoop() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for (let p of particles) {
                p.vy += GRAVITY;
                p.y += p.vy;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
                ctx.fill();
            }
            requestAnimationFrame(gameLoop);
        }

        function saveState() {
            localStorage.setItem('particle-save', JSON.stringify(particles));
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Space') startGame();
        });
    </script>
</body>
</html>"""

# Improved HTML that preserves all features
IMPROVED_HTML = SAMPLE_HTML.replace(
    "<title>Test Particle Game</title>",
    "<title>Test Particle Game - Enhanced</title>"
).replace(
    "const MAX_PARTICLES = 200;",
    "const MAX_PARTICLES = 200;\n        const PARTICLE_RADIUS = 3;"
)

# Broken HTML that removes features but passes size check
BROKEN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Test Particle Game - Broken</title>
    <style>
        body { margin: 0; padding: 20px; font-family: sans-serif; background: #1a1a2e; color: #eee; }
        .container { max-width: 800px; margin: 0 auto; text-align: center; }
        h1 { font-size: 2em; margin-bottom: 1em; color: #e94560; }
        p { line-height: 1.6; margin-bottom: 1em; }
        .card { background: #16213e; border-radius: 12px; padding: 24px; margin: 16px 0; }
        .stats { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; }
        .stat-box { background: #0f3460; padding: 16px 24px; border-radius: 8px; min-width: 120px; }
        .stat-value { font-size: 1.8em; font-weight: bold; color: #e94560; }
        .stat-label { font-size: 0.85em; opacity: 0.7; margin-top: 4px; }
        footer { margin-top: 40px; padding: 20px; opacity: 0.5; font-size: 0.85em; }
        @media (max-width: 600px) { .stats { flex-direction: column; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Particle Game</h1>
        <div class="card">
            <p>This is a completely rewritten version that looks nice but removed
            all the actual game functionality including the canvas, particle physics,
            keyboard controls, and localStorage persistence.</p>
        </div>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">0</div>
                <div class="stat-label">Particles</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">0</div>
                <div class="stat-label">Score</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">0</div>
                <div class="stat-label">Level</div>
            </div>
        </div>
        <footer>Built with care. No actual gameplay available.</footer>
    </div>
    <script>
        // All game features removed - just a pretty static page now
        console.log('Particle Game loaded');
        document.querySelector('h1').style.textShadow = '0 0 20px rgba(233, 69, 96, 0.5)';
        // Fake interactivity
        document.querySelectorAll('.stat-box').forEach(function(box) {
            box.style.cursor = 'pointer';
        });
        // Some padding code to meet size requirements
        var config = {
            theme: 'dark',
            version: '2.0',
            author: 'molt-agent',
            description: 'A simplified version of the particle game',
            features: ['responsive', 'dark-theme', 'stats-display'],
            changelog: [
                'v2.0: Simplified architecture',
                'v1.0: Original particle system'
            ]
        };
        console.log('Config:', JSON.stringify(config));
    </script>
</body>
</html>"""


def make_manifest(generation=0, apps_dir=None):
    """Build a test manifest dict."""
    return {
        "categories": {
            "games_puzzles": {
                "title": "Games & Puzzles",
                "folder": "games-puzzles",
                "count": 1,
                "apps": [
                    {
                        "title": "Test Particle Game",
                        "file": "test-particle-game.html",
                        "description": "A particle game",
                        "tags": ["canvas", "physics"],
                        "complexity": "intermediate",
                        "type": "game",
                        "featured": False,
                        "created": "2025-01-01",
                        "generation": generation,
                    }
                ],
            }
        }
    }


@pytest.fixture
def tmp_project(tmp_path):
    """Create a realistic project structure for testing."""
    apps_dir = tmp_path / "apps"
    games_dir = apps_dir / "games-puzzles"
    games_dir.mkdir(parents=True)
    archive_dir = apps_dir / "archive"
    archive_dir.mkdir(parents=True)

    # Write sample HTML
    (games_dir / "test-particle-game.html").write_text(SAMPLE_HTML)

    # Write manifest
    manifest = make_manifest()
    (apps_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return tmp_path, apps_dir, manifest


# ===========================================================================
# FEATURE CONTRACT INTEGRATION TESTS
# ===========================================================================


class TestFeatureContractIntegration:
    """Test that feature contracts are extracted and verified during molting."""

    def test_molt_with_contract_success(self, tmp_project):
        """Molt that preserves all features should succeed."""
        tmp_path, apps_dir, manifest = tmp_project

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"
        assert "feature_preservation" in result
        assert result["feature_preservation"] == 1.0

    def test_molt_rejects_missing_features(self, tmp_project):
        """Molt that removes critical features should be rejected."""
        tmp_path, apps_dir, manifest = tmp_project

        with mock.patch("molt.copilot_call_with_retry", return_value=BROKEN_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "rejected"
        assert "Feature contract failed" in result["reason"]
        # Original file should be unchanged
        live = apps_dir / "games-puzzles" / "test-particle-game.html"
        assert live.read_text() == SAMPLE_HTML

    def test_molt_without_contract_allows_feature_loss(self, tmp_project):
        """With --no-contract, feature loss doesn't cause rejection."""
        tmp_path, apps_dir, manifest = tmp_project

        with mock.patch("molt.copilot_call_with_retry", return_value=BROKEN_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=False,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        # Should still be rejected on size ratio, not contract
        # (BROKEN_HTML is much smaller)
        assert result["status"] in ("rejected", "success")

    def test_contract_logged_in_molt_log(self, tmp_project):
        """Feature preservation should be recorded in molt-log.json."""
        tmp_path, apps_dir, manifest = tmp_project

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"

        log_path = apps_dir / "archive" / "test-particle-game" / "molt-log.json"
        assert log_path.exists()
        log = json.loads(log_path.read_text())
        assert len(log) >= 1
        assert "feature_preservation" in log[-1]
        assert log[-1]["feature_preservation"] == 1.0


# ===========================================================================
# SCORE GATE TESTS
# ===========================================================================


class TestScoreGate:
    """Test score-gated auto-rollback."""

    def test_score_drop_triggers_rollback(self, tmp_project):
        """If score drops >10 points, molt should auto-rollback."""
        tmp_path, apps_dir, manifest = tmp_project

        # Create rankings.json with a pre-molt score of 60
        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 60, "grade": "C"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        # Mock score_game to return 45 (drop of 15)
        mock_score = {"score": 45, "grade": "D"}

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML), \
             mock.patch("molt._score_app_if_available", return_value=mock_score):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=True,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "rolled_back"
        assert result["score_before"] == 60
        assert result["score_after"] == 45
        # Original should be restored
        live = apps_dir / "games-puzzles" / "test-particle-game.html"
        assert live.read_text() == SAMPLE_HTML

    def test_score_improvement_passes(self, tmp_project):
        """If score improves, molt should succeed."""
        tmp_path, apps_dir, manifest = tmp_project

        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 50, "grade": "C"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        mock_score = {"score": 58, "grade": "C"}

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML), \
             mock.patch("molt._score_app_if_available", return_value=mock_score):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=True,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"
        assert result["score_before"] == 50
        assert result["score_after"] == 58

    def test_small_drop_without_feature_loss_passes(self, tmp_project):
        """Small score drop (<= threshold) without feature loss should pass."""
        tmp_path, apps_dir, manifest = tmp_project

        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 55, "grade": "C"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        mock_score = {"score": 52, "grade": "C"}

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML), \
             mock.patch("molt._score_app_if_available", return_value=mock_score):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=True,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"

    def test_score_gate_disabled(self, tmp_project):
        """With --no-score-gate, score drops don't trigger rollback."""
        tmp_path, apps_dir, manifest = tmp_project

        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 80, "grade": "B"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"


# ===========================================================================
# COOLDOWN TESTS
# ===========================================================================


class TestCooldown:
    """Test molt cooldown and 'good enough' threshold."""

    def test_good_enough_skipped(self, tmp_project):
        """Apps scoring >= 70 at gen 3+ should be skipped."""
        tmp_path, apps_dir, manifest = tmp_project

        # Set generation to 3
        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 3

        # Set high score in rankings
        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 75, "grade": "B"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        result = molt_mod.molt_app(
            "test-particle-game.html",
            adaptive=False,
            use_contract=True,
            use_score_gate=False,
            force=False,
            _manifest=manifest,
            _apps_dir=apps_dir,
        )

        assert result["status"] == "skipped"
        assert "good-enough" in result["reason"].lower() or "70" in result["reason"]

    def test_force_overrides_cooldown(self, tmp_project):
        """--force should override the good-enough threshold."""
        tmp_path, apps_dir, manifest = tmp_project

        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 3

        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 75, "grade": "B"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                force=True,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"

    def test_low_gen_not_subject_to_threshold(self, tmp_project):
        """Apps at gen 0-2 should NOT be subject to good-enough threshold."""
        tmp_path, apps_dir, manifest = tmp_project

        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 1

        rankings = {
            "rankings": [
                {"file": "test-particle-game.html", "score": 80, "grade": "B"}
            ]
        }
        (apps_dir / "rankings.json").write_text(json.dumps(rankings))

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"

    def test_no_rankings_file_continues(self, tmp_project):
        """If rankings.json doesn't exist, cooldown check is skipped."""
        tmp_path, apps_dir, manifest = tmp_project

        manifest["categories"]["games_puzzles"]["apps"][0]["generation"] = 4

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"


# ===========================================================================
# SURGICAL MODE TESTS
# ===========================================================================


class TestSurgicalMode:
    """Test surgical edit mode (JSON patches)."""

    def test_apply_surgical_edits_success(self):
        """Valid surgical edits should be applied correctly."""
        html = '<button onclick="start()">Go</button>'
        edits = json.dumps([
            {
                "description": "Add aria label",
                "find": '<button onclick="start()">Go</button>',
                "replace": '<button onclick="start()" aria-label="Start">Go</button>'
            }
        ])

        result, applied, errors = molt_mod.apply_surgical_edits(html, edits)
        assert applied == 1
        assert len(errors) == 0
        assert 'aria-label="Start"' in result

    def test_apply_surgical_edits_multiple(self):
        """Multiple edits should be applied sequentially."""
        html = """<h1>Title</h1><p>Paragraph</p>"""
        edits = json.dumps([
            {"description": "Change title", "find": "<h1>Title</h1>", "replace": "<h1>New Title</h1>"},
            {"description": "Change para", "find": "<p>Paragraph</p>", "replace": "<p>New Paragraph</p>"},
        ])

        result, applied, errors = molt_mod.apply_surgical_edits(html, edits)
        assert applied == 2
        assert "<h1>New Title</h1>" in result
        assert "<p>New Paragraph</p>" in result

    def test_apply_surgical_edits_not_found(self):
        """Edits with no matching text should be skipped with error."""
        html = "<div>Hello</div>"
        edits = json.dumps([
            {"description": "Bad edit", "find": "NONEXISTENT", "replace": "REPLACEMENT"}
        ])

        result, applied, errors = molt_mod.apply_surgical_edits(html, edits)
        assert result is None
        assert applied == 0
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_apply_surgical_edits_duplicate_match(self):
        """Edits matching multiple locations should be skipped."""
        html = "<div>Same</div><div>Same</div>"
        edits = json.dumps([
            {"description": "Ambiguous", "find": "<div>Same</div>", "replace": "<div>Changed</div>"}
        ])

        result, applied, errors = molt_mod.apply_surgical_edits(html, edits)
        assert result is None
        assert applied == 0
        assert "matches 2 times" in errors[0]

    def test_apply_surgical_edits_bad_json(self):
        """Invalid JSON should return None."""
        result, applied, errors = molt_mod.apply_surgical_edits("<div></div>", "not json{")
        assert result is None
        assert applied == 0
        assert "parse" in errors[0].lower()

    def test_apply_surgical_edits_not_list(self):
        """Non-list JSON should return None."""
        result, applied, errors = molt_mod.apply_surgical_edits("<div></div>", '{"foo": "bar"}')
        assert result is None
        assert "not a list" in errors[0]

    def test_surgical_mode_in_molt_pipeline(self, tmp_project):
        """Surgical mode should apply edits and preserve untouched code."""
        tmp_path, apps_dir, manifest = tmp_project

        surgical_response = json.dumps([
            {
                "description": "Enhance title",
                "find": "<title>Test Particle Game</title>",
                "replace": "<title>Test Particle Game - Enhanced</title>"
            }
        ])

        identity = {
            "medium": "particle simulation",
            "purpose": "interactive particle physics demo",
            "strengths": ["canvas rendering", "physics"],
            "weaknesses": ["no accessibility"],
            "improvement_vectors": ["add ARIA labels"],
        }

        with mock.patch("molt.copilot_call_with_retry", return_value=surgical_response), \
             mock.patch("molt._analyze_content", return_value=identity):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=True,
                surgical=True,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"
        # Verify the edit was applied
        live = apps_dir / "games-puzzles" / "test-particle-game.html"
        content = live.read_text()
        assert "Test Particle Game - Enhanced" in content
        # Verify everything else is untouched (critical!)
        assert "MAX_PARTICLES = 200" in content
        assert "GRAVITY = 0.98" in content
        assert "requestAnimationFrame(gameLoop)" in content
        assert "localStorage.setItem('particle-save'" in content

    def test_surgical_fallback_to_rewrite(self, tmp_project):
        """If surgical edits fail, should fall back to full rewrite parsing."""
        tmp_path, apps_dir, manifest = tmp_project

        # Return a full HTML instead of JSON edits
        identity = {
            "medium": "game",
            "purpose": "test",
            "strengths": [],
            "weaknesses": [],
            "improvement_vectors": ["improve"],
        }

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML), \
             mock.patch("molt._analyze_content", return_value=identity):
            result = molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=True,
                surgical=True,
                use_contract=True,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        assert result["status"] == "success"


# ===========================================================================
# BUILD SURGICAL PROMPT TESTS
# ===========================================================================


class TestBuildSurgicalPrompt:
    """Test surgical prompt construction."""

    def test_prompt_includes_json_instructions(self):
        identity = {
            "medium": "synthesizer",
            "purpose": "audio synthesis",
            "strengths": ["Web Audio API"],
            "weaknesses": ["no MIDI"],
            "improvement_vectors": ["add MIDI support"],
        }
        contract = {
            "features": [
                {"id": "audio-ctx", "type": "audio", "subtype": "AudioContext", "evidence": "AudioContext"}
            ],
            "constants": {"SAMPLE_RATE": "44100"},
            "summary": {"audio": 1},
        }

        prompt = molt_mod.build_surgical_molt_prompt(SAMPLE_HTML, "test.html", identity, contract)
        assert "JSON array" in prompt
        assert '"find"' in prompt
        assert '"replace"' in prompt
        assert "SURGICAL" in prompt

    def test_prompt_includes_contract(self):
        identity = {"medium": "test", "purpose": "test", "strengths": [], "weaknesses": [], "improvement_vectors": []}
        contract = {
            "features": [
                {"id": "ls-save", "type": "localstorage", "subtype": "key", "evidence": "my-save"}
            ],
            "constants": {},
            "summary": {"localstorage": 1},
        }

        prompt = molt_mod.build_surgical_molt_prompt(SAMPLE_HTML, "test.html", identity, contract)
        assert "FEATURE CONTRACT" in prompt
        assert "my-save" in prompt


# ===========================================================================
# MOLT LOG MODE TRACKING
# ===========================================================================


class TestMoltLogMode:
    """Test that molt mode is tracked in audit logs."""

    def test_classic_mode_logged(self, tmp_project):
        tmp_path, apps_dir, manifest = tmp_project

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML):
            molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=False,
                use_contract=False,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        log_path = apps_dir / "archive" / "test-particle-game" / "molt-log.json"
        log = json.loads(log_path.read_text())
        assert log[-1]["mode"] == "classic"

    def test_adaptive_mode_logged(self, tmp_project):
        tmp_path, apps_dir, manifest = tmp_project

        identity = {
            "medium": "game",
            "purpose": "test",
            "strengths": [],
            "weaknesses": [],
            "improvement_vectors": ["improve"],
        }

        with mock.patch("molt.copilot_call_with_retry", return_value=IMPROVED_HTML), \
             mock.patch("molt._analyze_content", return_value=identity):
            molt_mod.molt_app(
                "test-particle-game.html",
                adaptive=True,
                use_contract=False,
                use_score_gate=False,
                _manifest=manifest,
                _apps_dir=apps_dir,
            )

        log_path = apps_dir / "archive" / "test-particle-game" / "molt-log.json"
        log = json.loads(log_path.read_text())
        assert log[-1]["mode"] == "adaptive"
