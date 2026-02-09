"""Tests for feature_contract.py — Feature Contract Extraction & Verification.

Tests that the contract system correctly:
1. Extracts features from HTML source (event listeners, localStorage, canvas, etc.)
2. Verifies features are preserved after a molt
3. Detects missing features and reports them
4. Handles edge cases (empty HTML, minified code, template literals)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pytest
import feature_contract as fc

# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

RICH_APP_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Test Game</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="rappterzoo:category" content="games_puzzles">
    <meta name="rappterzoo:author" content="test-agent">
    <meta name="rappterzoo:generation" content="2">
    <style>
        canvas { border: 1px solid #333; }
        .btn { transition: opacity 0.3s ease; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @keyframes slideIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
    </style>
</head>
<body>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
    <button id="startBtn" onclick="startGame()">Start</button>
    <button id="pauseBtn" onclick="togglePause()">Pause</button>
    <input id="speedSlider" type="range" min="1" max="10" value="5">
    <select id="difficultySelect">
        <option value="easy">Easy</option>
        <option value="hard">Hard</option>
    </select>
    <script>
        const MAX_PARTICLES = 200;
        const GRAVITY = 0.98;
        const FRICTION = 0.995;
        const BOUNCE_DAMPING = 0.7;

        const canvas = document.getElementById('gameCanvas');
        const ctx = canvas.getContext('2d');
        let audioCtx = new AudioContext();
        let particles = [];
        let score = 0;
        let paused = false;

        function startGame() {
            score = 0;
            particles = [];
            requestAnimationFrame(gameLoop);
        }

        function togglePause() {
            paused = !paused;
            if (!paused) requestAnimationFrame(gameLoop);
        }

        function gameLoop(timestamp) {
            if (paused) return;
            updateParticles();
            drawParticles();
            requestAnimationFrame(gameLoop);
        }

        function updateParticles() {
            for (let p of particles) {
                p.vy += GRAVITY;
                p.vx *= FRICTION;
                p.x += p.vx;
                p.y += p.vy;
            }
        }

        function drawParticles() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for (let p of particles) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        function saveProgress() {
            localStorage.setItem('game-save', JSON.stringify({ score, particles: particles.length }));
            localStorage.setItem('game-settings', JSON.stringify({ difficulty: 'easy' }));
        }

        function loadProgress() {
            const save = localStorage.getItem('game-save');
            const settings = localStorage.getItem('game-settings');
            if (save) {
                const data = JSON.parse(save);
                score = data.score;
            }
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft') moveLeft();
            if (e.key === 'ArrowRight') moveRight();
            if (e.key === 'Space') jump();
            if (e.key === 'Escape') togglePause();
        });

        canvas.addEventListener('click', function(e) {
            spawnParticle(e.offsetX, e.offsetY);
        });

        window.addEventListener('resize', function() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });

        const moveLeft = () => { /* move logic */ };
        const moveRight = () => { /* move logic */ };
        var jump = function() { /* jump logic */ };

        function spawnParticle(x, y) {
            if (particles.length < MAX_PARTICLES) {
                particles.push({ x, y, vx: Math.random() * 2 - 1, vy: -5, radius: 3 });
            }
        }

        setInterval(saveProgress, 30000);
        loadProgress();
    </script>
</body>
</html>"""

MINIMAL_HTML = """<!DOCTYPE html>
<html><head><title>Minimal</title></head>
<body><p>Hello</p></body></html>"""

EMPTY_HTML = ""


# ===========================================================================
# EXTRACTION TESTS
# ===========================================================================


class TestExtractFeatures:
    """Test feature extraction from HTML source."""

    def test_extracts_event_listeners(self):
        """Should find all addEventListener calls."""
        contract = fc.extract_features(RICH_APP_HTML)
        listener_types = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "event_listener"
        ]
        assert "keydown" in listener_types
        assert "click" in listener_types
        assert "resize" in listener_types

    def test_extracts_inline_handlers(self):
        """Should find onclick= style handlers."""
        contract = fc.extract_features(RICH_APP_HTML)
        inline_types = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "inline_handler"
        ]
        assert "click" in inline_types

    def test_extracts_localstorage_keys(self):
        """Should find all localStorage key names."""
        contract = fc.extract_features(RICH_APP_HTML)
        ls_keys = [
            f["evidence"] for f in contract["features"]
            if f["type"] == "localstorage"
        ]
        assert "game-save" in ls_keys
        assert "game-settings" in ls_keys

    def test_extracts_animation_loops(self):
        """Should detect requestAnimationFrame and setInterval."""
        contract = fc.extract_features(RICH_APP_HTML)
        loop_types = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "animation_loop"
        ]
        assert "requestAnimationFrame" in loop_types
        assert "setInterval" in loop_types

    def test_extracts_canvas_context(self):
        """Should detect canvas 2d context."""
        contract = fc.extract_features(RICH_APP_HTML)
        canvas = [f for f in contract["features"] if f["type"] == "canvas"]
        assert len(canvas) >= 1
        assert canvas[0]["subtype"] == "2d"

    def test_extracts_audio_context(self):
        """Should detect AudioContext usage."""
        contract = fc.extract_features(RICH_APP_HTML)
        audio = [f for f in contract["features"] if f["type"] == "audio"]
        assert len(audio) >= 1

    def test_extracts_keyboard_shortcuts(self):
        """Should find keyboard shortcut keys."""
        contract = fc.extract_features(RICH_APP_HTML)
        keys = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "keyboard_shortcut"
        ]
        assert "ArrowLeft" in keys
        assert "ArrowRight" in keys
        assert "Space" in keys
        assert "Escape" in keys

    def test_extracts_css_animations(self):
        """Should find @keyframes declarations."""
        contract = fc.extract_features(RICH_APP_HTML)
        anims = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "css_animation"
        ]
        assert "pulse" in anims
        assert "slideIn" in anims

    def test_extracts_css_transitions(self):
        """Should detect CSS transition usage."""
        contract = fc.extract_features(RICH_APP_HTML)
        transitions = [f for f in contract["features"] if f["type"] == "css_transition"]
        assert len(transitions) >= 1

    def test_extracts_ui_elements(self):
        """Should find UI elements with IDs."""
        contract = fc.extract_features(RICH_APP_HTML)
        ui_ids = [
            f["evidence"] for f in contract["features"]
            if f["type"] == "ui_element"
        ]
        assert "gameCanvas" in ui_ids
        assert "startBtn" in ui_ids
        assert "pauseBtn" in ui_ids
        assert "speedSlider" in ui_ids
        assert "difficultySelect" in ui_ids

    def test_extracts_named_functions(self):
        """Should find user-defined function names."""
        contract = fc.extract_features(RICH_APP_HTML)
        funcs = [
            f["evidence"] for f in contract["features"]
            if f["type"] == "function"
        ]
        assert "startGame" in funcs
        assert "togglePause" in funcs
        assert "gameLoop" in funcs
        assert "updateParticles" in funcs
        assert "drawParticles" in funcs
        assert "saveProgress" in funcs
        assert "loadProgress" in funcs
        assert "spawnParticle" in funcs

    def test_extracts_arrow_and_var_functions(self):
        """Should find const fn = () => and var fn = function() patterns."""
        contract = fc.extract_features(RICH_APP_HTML)
        funcs = [
            f["evidence"] for f in contract["features"]
            if f["type"] == "function"
        ]
        assert "moveLeft" in funcs
        assert "moveRight" in funcs
        assert "jump" in funcs

    def test_extracts_tuned_constants(self):
        """Should find ALL_CAPS = number patterns."""
        contract = fc.extract_features(RICH_APP_HTML)
        assert "MAX_PARTICLES" in contract["constants"]
        assert contract["constants"]["MAX_PARTICLES"] == "200"
        assert "GRAVITY" in contract["constants"]
        assert contract["constants"]["GRAVITY"] == "0.98"
        assert "FRICTION" in contract["constants"]
        assert "BOUNCE_DAMPING" in contract["constants"]

    def test_extracts_meta_tags(self):
        """Should find rappterzoo:* meta tags."""
        contract = fc.extract_features(RICH_APP_HTML)
        meta_subtypes = [
            f["subtype"] for f in contract["features"]
            if f["type"] == "meta_tag"
        ]
        assert "category" in meta_subtypes
        assert "author" in meta_subtypes
        assert "generation" in meta_subtypes

    def test_summary_counts(self):
        """Summary should have correct type counts."""
        contract = fc.extract_features(RICH_APP_HTML)
        summary = contract["summary"]
        assert summary.get("event_listener", 0) >= 3
        assert summary.get("localstorage", 0) >= 2
        assert summary.get("function", 0) >= 8

    def test_empty_html(self):
        """Should handle empty HTML gracefully."""
        contract = fc.extract_features(EMPTY_HTML)
        assert contract["features"] == []
        assert contract["constants"] == {}
        assert contract["summary"] == {}

    def test_minimal_html(self):
        """Should handle minimal HTML without crashing."""
        contract = fc.extract_features(MINIMAL_HTML)
        assert isinstance(contract["features"], list)
        assert isinstance(contract["constants"], dict)

    def test_none_input(self):
        """Should handle None input."""
        contract = fc.extract_features(None)
        assert contract["features"] == []


# ===========================================================================
# VERIFICATION TESTS
# ===========================================================================


class TestVerifyFeatures:
    """Test feature contract verification against new HTML."""

    def test_all_features_present_passes(self):
        """When all features are preserved, verification passes."""
        contract = fc.extract_features(RICH_APP_HTML)
        result = fc.verify_features(contract, RICH_APP_HTML)
        assert result["passed"] is True
        assert result["preservation_ratio"] == 1.0
        assert result["missing"] == []

    def test_missing_listener_detected(self):
        """Removing an event listener should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        # Remove the resize listener
        modified = RICH_APP_HTML.replace(
            "window.addEventListener('resize'",
            "// removed resize handler"
        )
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert any("resize" in mid for mid in missing_ids)

    def test_missing_localstorage_detected(self):
        """Removing a localStorage key should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        # Remove all references to game-save
        modified = RICH_APP_HTML.replace("game-save", "")
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert "localstorage-game-save" in missing_ids

    def test_missing_localstorage_fails_critical(self):
        """localStorage is a critical type — missing it should fail."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("game-save", "").replace("game-settings", "")
        result = fc.verify_features(contract, modified)
        assert result["passed"] is False

    def test_missing_canvas_fails_critical(self):
        """Canvas is a critical type — removing it should fail."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("getContext('2d')", "// no canvas")
        result = fc.verify_features(contract, modified)
        assert result["passed"] is False

    def test_missing_function_detected(self):
        """Removing a named function should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("spawnParticle", "createThing")
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert any("spawnParticle" in mid for mid in missing_ids)

    def test_missing_keyboard_shortcut_detected(self):
        """Removing a keyboard shortcut should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("ArrowLeft", "")
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert any("ArrowLeft" in mid for mid in missing_ids)

    def test_missing_css_animation_detected(self):
        """Removing a @keyframes should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("@keyframes pulse", "/* removed */")
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert any("pulse" in mid for mid in missing_ids)

    def test_missing_ui_element_detected(self):
        """Removing a UI element ID should be detected."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace('id="speedSlider"', 'id="speedInput"')
        result = fc.verify_features(contract, modified)
        missing_ids = [m["id"] for m in result["missing"]]
        assert any("speedSlider" in mid for mid in missing_ids)

    def test_preservation_ratio_calculated(self):
        """Preservation ratio should reflect how many features survived."""
        contract = fc.extract_features(RICH_APP_HTML)
        # Remove several features
        modified = RICH_APP_HTML.replace("AudioContext", "").replace(
            "@keyframes pulse", ""
        ).replace("@keyframes slideIn", "")
        result = fc.verify_features(contract, modified)
        assert 0.0 < result["preservation_ratio"] < 1.0
        assert result["preserved"] < result["total"]

    def test_strict_constant_checking(self):
        """In strict mode, constants must have exact values."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("MAX_PARTICLES = 200", "MAX_PARTICLES = 100")
        result = fc.verify_features(contract, modified, strict=True)
        missing_const_names = [c["name"] for c in result["missing_constants"]]
        assert "MAX_PARTICLES" in missing_const_names

    def test_nonstrict_constant_name_only(self):
        """In non-strict mode, constant name just needs to exist."""
        contract = fc.extract_features(RICH_APP_HTML)
        modified = RICH_APP_HTML.replace("MAX_PARTICLES = 200", "MAX_PARTICLES = 100")
        result = fc.verify_features(contract, modified, strict=False)
        missing_const_names = [c["name"] for c in result["missing_constants"]]
        assert "MAX_PARTICLES" not in missing_const_names

    def test_empty_contract_passes(self):
        """Empty contract should trivially pass."""
        result = fc.verify_features({"features": [], "constants": {}}, RICH_APP_HTML)
        assert result["passed"] is True

    def test_none_contract_passes(self):
        """None contract should trivially pass."""
        result = fc.verify_features(None, RICH_APP_HTML)
        assert result["passed"] is True

    def test_empty_new_html_fails(self):
        """Empty new HTML should fail if contract has features."""
        contract = fc.extract_features(RICH_APP_HTML)
        result = fc.verify_features(contract, "")
        assert result["passed"] is False
        assert result["preservation_ratio"] == 0.0

    def test_ninety_percent_threshold(self):
        """Should pass if >=90% features preserved (no critical missing)."""
        # Create a small contract
        html = """<!DOCTYPE html><html><head><title>T</title></head><body>
        <script>
        function alpha() {}
        function beta() {}
        function gamma() {}
        function delta() {}
        function epsilon() {}
        function zeta() {}
        function eta() {}
        function theta() {}
        function iota() {}
        function kappa() {}
        </script></body></html>"""
        contract = fc.extract_features(html)
        funcs = [f for f in contract["features"] if f["type"] == "function"]
        assert len(funcs) == 10

        # Remove 1 of 10 = 90% preserved → should pass
        modified = html.replace("function kappa", "function replaced")
        result = fc.verify_features(contract, modified)
        assert result["passed"] is True

    def test_below_ninety_percent_fails(self):
        """Should fail if <90% features preserved."""
        html = """<!DOCTYPE html><html><head><title>T</title></head><body>
        <script>
        function alpha() {}
        function beta() {}
        function gamma() {}
        function delta() {}
        function epsilon() {}
        function zeta() {}
        function eta() {}
        function theta() {}
        function iota() {}
        function kappa() {}
        </script></body></html>"""
        contract = fc.extract_features(html)
        # Remove 2 of 10 = 80% preserved → should fail
        modified = html.replace("function kappa", "function x").replace(
            "function iota", "function y"
        )
        result = fc.verify_features(contract, modified)
        assert result["passed"] is False


# ===========================================================================
# FORMAT FOR PROMPT TESTS
# ===========================================================================


class TestFormatContractForPrompt:
    """Test formatting contracts for LLM prompts."""

    def test_formats_with_sections(self):
        """Should produce readable grouped output."""
        contract = fc.extract_features(RICH_APP_HTML)
        text = fc.format_contract_for_prompt(contract)
        assert "FEATURE CONTRACT" in text
        assert "Event Listeners" in text
        assert "localStorage Keys" in text
        assert "game-save" in text

    def test_includes_constants(self):
        """Should include tuned constants section."""
        contract = fc.extract_features(RICH_APP_HTML)
        text = fc.format_contract_for_prompt(contract)
        assert "Tuned Constants" in text
        assert "MAX_PARTICLES = 200" in text
        assert "GRAVITY = 0.98" in text

    def test_empty_contract_returns_empty(self):
        """Empty contract should return empty string."""
        text = fc.format_contract_for_prompt({"features": [], "constants": {}})
        assert text == ""

    def test_none_contract_returns_empty(self):
        """None contract should return empty string."""
        text = fc.format_contract_for_prompt(None)
        assert text == ""


# ===========================================================================
# WEBGL DETECTION
# ===========================================================================


class TestWebGLDetection:
    """Test WebGL context detection."""

    def test_detects_webgl(self):
        html = '<script>canvas.getContext("webgl")</script>'
        contract = fc.extract_features(html)
        canvas = [f for f in contract["features"] if f["type"] == "canvas"]
        assert len(canvas) >= 1
        assert canvas[0]["subtype"] == "webgl"

    def test_detects_webgl2(self):
        html = "<script>canvas.getContext('webgl2')</script>"
        contract = fc.extract_features(html)
        canvas = [f for f in contract["features"] if f["type"] == "canvas"]
        assert len(canvas) >= 1


# ===========================================================================
# EDGE CASES
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and unusual HTML patterns."""

    def test_localstorage_bracket_access(self):
        """Should detect localStorage['key'] bracket access."""
        html = """<script>localStorage['my-data'] = JSON.stringify(state);</script>"""
        contract = fc.extract_features(html)
        ls = [f for f in contract["features"] if f["type"] == "localstorage"]
        assert any(f["evidence"] == "my-data" for f in ls)

    def test_new_audio_element(self):
        """Should detect new Audio() constructor."""
        html = "<script>const sound = new Audio('data:audio/wav;base64,...');</script>"
        contract = fc.extract_features(html)
        audio = [f for f in contract["features"] if f["type"] == "audio"]
        assert len(audio) >= 1

    def test_switch_case_keyboard(self):
        """Should detect keyboard shortcuts in switch/case blocks."""
        html = """<script>
        document.addEventListener('keydown', function(e) {
            switch(e.key) {
                case 'w': moveUp(); break;
                case 's': moveDown(); break;
            }
        });
        </script>"""
        contract = fc.extract_features(html)
        keys = [f["subtype"] for f in contract["features"] if f["type"] == "keyboard_shortcut"]
        assert "w" in keys
        assert "s" in keys

    def test_handles_very_large_html(self):
        """Should handle large files without crashing."""
        big_html = RICH_APP_HTML + "\n<!-- padding -->" * 10000
        contract = fc.extract_features(big_html)
        assert len(contract["features"]) > 0

    def test_minified_single_line(self):
        """Should work on minified single-line HTML."""
        html = '<!DOCTYPE html><html><head><title>M</title></head><body><script>const c=document.getElementById("c");const ctx=c.getContext("2d");function draw(){ctx.clearRect(0,0,c.width,c.height);requestAnimationFrame(draw)}localStorage.setItem("save","1");draw()</script></body></html>'
        contract = fc.extract_features(html)
        assert any(f["type"] == "canvas" for f in contract["features"])
        assert any(f["type"] == "animation_loop" for f in contract["features"])
        assert any(f["type"] == "localstorage" for f in contract["features"])
        assert any(f["type"] == "function" for f in contract["features"])
