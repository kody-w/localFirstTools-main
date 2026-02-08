"""Tests for runtime_verify.py — all mocked, no network, no browser needed."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime_verify import (
    check_canvas_renders,
    check_dead_code,
    check_error_resilience,
    check_interaction_wired,
    check_js_syntax,
    check_not_skeleton,
    check_playwright_installed,
    check_state_coherence,
    discover_manifest_apps,
    run_browser_check,
    start_local_server,
    verify_app,
)


# ---------------------------------------------------------------------------
# Fixtures: sample HTML content
# ---------------------------------------------------------------------------

HEALTHY_GAME = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Healthy Game</title>
    <style>
        body { margin: 0; background: #111; }
        canvas { display: block; }
    </style>
</head>
<body>
<canvas id="game"></canvas>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
canvas.width = 800;
canvas.height = 600;

let gameState = 'menu';
let score = 0;
let player = { x: 400, y: 500, vx: 0, vy: 0, speed: 5 };
let enemies = [];
let particles = [];
let keys = {};
let lastTime = 0;
let combo = 0;
let shakeAmount = 0;

function init() {
    gameState = 'playing';
    score = 0;
    enemies = [];
    spawnEnemy();
}

function spawnEnemy() {
    enemies.push({
        x: Math.random() * canvas.width,
        y: -50,
        vy: 2 + Math.random() * 3,
        type: Math.random() > 0.5 ? 'fast' : 'slow',
        health: 3,
    });
}

function update(dt) {
    if (gameState !== 'playing') return;

    if (keys['ArrowLeft']) player.x -= player.speed * dt;
    if (keys['ArrowRight']) player.x += player.speed * dt;
    if (keys['ArrowUp']) player.y -= player.speed * dt;
    if (keys['ArrowDown']) player.y += player.speed * dt;

    for (let e of enemies) {
        e.y += e.vy * dt;
        if (checkCollision(player, e)) {
            gameState = 'gameover';
            shakeAmount = 20;
        }
    }

    enemies = enemies.filter(e => e.y < canvas.height + 100);
    particles = particles.filter(p => p.life > 0);
    for (let p of particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.life -= dt;
        p.alpha = p.life / p.maxLife;
    }

    if (Math.random() < 0.02 * dt) spawnEnemy();
    score += dt;
    shakeAmount *= 0.9;
}

function checkCollision(a, b) {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return Math.sqrt(dx*dx + dy*dy) < 30;
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    let ox = (Math.random() - 0.5) * shakeAmount;
    let oy = (Math.random() - 0.5) * shakeAmount;
    ctx.save();
    ctx.translate(ox, oy);

    ctx.fillStyle = '#0ff';
    ctx.fillRect(player.x - 15, player.y - 15, 30, 30);

    for (let e of enemies) {
        ctx.fillStyle = e.type === 'fast' ? '#f55' : '#fa0';
        ctx.beginPath();
        ctx.arc(e.x, e.y, 15, 0, Math.PI * 2);
        ctx.fill();
    }

    for (let p of particles) {
        ctx.globalAlpha = p.alpha;
        ctx.fillStyle = p.color;
        ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    }
    ctx.globalAlpha = 1;

    ctx.fillStyle = '#fff';
    ctx.font = '20px monospace';
    ctx.fillText('Score: ' + Math.floor(score), 10, 30);

    ctx.restore();

    if (gameState === 'gameover') {
        ctx.fillStyle = 'rgba(0,0,0,0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '40px monospace';
        ctx.fillText('GAME OVER', 280, 280);
        ctx.font = '20px monospace';
        ctx.fillText('Press R to restart', 300, 330);
    }

    if (gameState === 'menu') {
        ctx.fillStyle = '#fff';
        ctx.font = '40px monospace';
        ctx.fillText('HEALTHY GAME', 250, 280);
        ctx.font = '20px monospace';
        ctx.fillText('Press SPACE to start', 290, 330);
    }
}

function gameLoop(time) {
    let dt = Math.min((time - lastTime) / 16.67, 3);
    lastTime = time;
    update(dt);
    draw();
    requestAnimationFrame(gameLoop);
}

addEventListener('keydown', e => {
    keys[e.key] = true;
    if (e.key === ' ' && gameState === 'menu') init();
    if (e.key === 'r' && gameState === 'gameover') init();
});
addEventListener('keyup', e => { keys[e.key] = false; });

try {
    requestAnimationFrame(gameLoop);
} catch(err) {
    console.error('Game loop failed:', err);
}
</script>
</body>
</html>"""

BROKEN_GAME_SYNTAX = """<!DOCTYPE html>
<html><head><title>Broken Syntax</title>
<meta name="viewport" content="width=device-width">
</head><body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

function update() {
    if (true {
        let x = [1, 2, 3;
        console.log(x);
    }

function draw() {
    ctx.clearRect(0, 0, 800, 600);
}

requestAnimationFrame(function loop() {
    update();
    draw();
    requestAnimationFrame(loop);
});
</script>
</body></html>"""

SKELETON_APP = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skeleton</title>
    <style>canvas { border: 1px solid #ccc; }</style>
</head>
<body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
// TODO: implement game
</script>
</body>
</html>"""

DEAD_CODE_APP = """<!DOCTYPE html>
<html><head><title>Dead Code</title>
<meta name="viewport" content="width=device-width">
</head><body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

function unusedFunctionA() { return 42; }
function unusedFunctionB() { return "hello"; }
function unusedFunctionC() { return [1,2,3]; }
function unusedFunctionD() { return {x: 1}; }

function draw() {
    ctx.clearRect(0, 0, 800, 600);
    ctx.fillRect(10, 10, 50, 50);
}

function init() {
    draw();
    requestAnimationFrame(init);
}

init();
</script>
</body></html>"""

NO_CANVAS_DRAWS = """<!DOCTYPE html>
<html><head><title>No Draws</title>
<meta name="viewport" content="width=device-width">
</head><body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
canvas.width = 800;
canvas.height = 600;
// Canvas created but nothing ever drawn
let gameState = 'running';
addEventListener('keydown', e => {
    gameState = 'paused';
});
</script>
</body></html>"""


# ---------------------------------------------------------------------------
# Tests: JS Syntax Balance
# ---------------------------------------------------------------------------
class TestJsSyntax:
    def test_healthy_syntax(self):
        result = check_js_syntax(HEALTHY_GAME)
        assert result["pass"] is True
        assert result["score"] >= 70
        assert result["js_size"] > 0

    def test_broken_syntax(self):
        result = check_js_syntax(BROKEN_GAME_SYNTAX)
        assert result["score"] < 100
        assert len(result["issues"]) > 0

    def test_no_javascript(self):
        result = check_js_syntax("<html><body>Hello</body></html>")
        assert result["pass"] is False
        assert result["reason"] == "no-javascript"

    def test_balanced_brackets(self):
        html = "<script>function f() { if (true) { return [1,2]; } }</script>"
        result = check_js_syntax(html)
        assert result["pass"] is True
        assert result["score"] == 100


# ---------------------------------------------------------------------------
# Tests: Canvas Rendering
# ---------------------------------------------------------------------------
class TestCanvasRenders:
    def test_healthy_canvas(self):
        result = check_canvas_renders(HEALTHY_GAME)
        assert result["pass"] is True
        assert result["applicable"] is True
        assert len(result["draw_calls"]) >= 2

    def test_no_canvas_app(self):
        result = check_canvas_renders("<html><body><div>Hello</div></body></html>")
        assert result["pass"] is True
        assert result["applicable"] is False

    def test_canvas_no_draws(self):
        result = check_canvas_renders(NO_CANVAS_DRAWS)
        assert result["pass"] is False
        assert result["score"] < 50

    def test_full_render_pipeline(self):
        html = """<canvas id="c"></canvas><script>
        const canvas = document.getElementById('c');
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0,0,800,600);
        ctx.fillRect(10,10,50,50);
        ctx.drawImage(img, 0, 0);
        ctx.beginPath(); ctx.arc(50,50,10,0,6.28); ctx.fill();
        requestAnimationFrame(loop);
        </script>"""
        result = check_canvas_renders(html)
        assert result["pass"] is True
        assert "full-render-pipeline" in result["details"]


# ---------------------------------------------------------------------------
# Tests: Interaction Wiring
# ---------------------------------------------------------------------------
class TestInteractionWired:
    def test_healthy_interaction(self):
        result = check_interaction_wired(HEALTHY_GAME)
        assert result["pass"] is True
        assert "keydown" in result["listeners"]
        assert "keyup" in result["listeners"]
        assert result["state_modifications"] > 0

    def test_no_listeners(self):
        html = "<html><body><script>let x = 1; x++;</script></body></html>"
        result = check_interaction_wired(html)
        assert result["pass"] is False
        assert result["score"] <= 20

    def test_inline_handlers(self):
        html = '<html><body><button onclick="start()">Go</button><script>function start(){}</script></body></html>'
        result = check_interaction_wired(html)
        assert result["pass"] is True
        assert result["reason"] == "inline-handlers-only"


# ---------------------------------------------------------------------------
# Tests: Skeleton Detection
# ---------------------------------------------------------------------------
class TestNotSkeleton:
    def test_healthy_not_skeleton(self):
        result = check_not_skeleton(HEALTHY_GAME)
        assert result["pass"] is True
        assert result["score"] >= 50
        assert result["function_count"] >= 5

    def test_skeleton_detected(self):
        result = check_not_skeleton(SKELETON_APP)
        assert result["pass"] is False
        assert result["js_lines"] < 10

    def test_logic_density(self):
        result = check_not_skeleton(HEALTHY_GAME)
        assert result["logic_density"] > 0.05


# ---------------------------------------------------------------------------
# Tests: Dead Code
# ---------------------------------------------------------------------------
class TestDeadCode:
    def test_healthy_code(self):
        result = check_dead_code(HEALTHY_GAME)
        assert result["pass"] is True
        assert result["alive_ratio"] >= 0.5

    def test_dead_code_detected(self):
        result = check_dead_code(DEAD_CODE_APP)
        assert len(result["dead_functions"]) > 0
        # Should detect unusedFunctionA/B/C/D
        assert any("unused" in f.lower() for f in result["dead_functions"])

    def test_no_functions(self):
        html = "<script>let x = 1; x++; console.log(x);</script>"
        result = check_dead_code(html)
        assert result["pass"] is True
        assert result["reason"] == "no-named-functions"


# ---------------------------------------------------------------------------
# Tests: State Coherence
# ---------------------------------------------------------------------------
class TestStateCoherence:
    def test_healthy_state(self):
        result = check_state_coherence(HEALTHY_GAME)
        assert result["pass"] is True
        assert result["coherence_ratio"] > 0.5

    def test_write_only_vars(self):
        html = """<script>
        let neverRead = 42;
        let alsoNeverRead = 'hello';
        let usedVar = 10;
        console.log(usedVar);
        </script>"""
        result = check_state_coherence(html)
        assert "neverRead" in result["write_only_vars"] or "alsoNeverRead" in result["write_only_vars"]


# ---------------------------------------------------------------------------
# Tests: Error Resilience
# ---------------------------------------------------------------------------
class TestErrorResilience:
    def test_has_try_catch(self):
        result = check_error_resilience(HEALTHY_GAME)
        assert "try-catch" in result["details"]
        assert result["score"] > 0

    def test_small_app_pass(self):
        html = "<script>let x = 1; x++;</script>"
        result = check_error_resilience(html)
        assert result["pass"] is True
        assert "small-app-pass" in result["details"]

    def test_no_error_handling_large(self):
        # Large app with no error handling
        html = "<script>" + "let x = 1;\n" * 500 + "</script>"
        result = check_error_resilience(html)
        assert "no-error-handling" in result["details"]


# ---------------------------------------------------------------------------
# Tests: Composite Verification
# ---------------------------------------------------------------------------
class TestVerifyApp:
    def test_healthy_app(self, tmp_path):
        f = tmp_path / "healthy.html"
        f.write_text(HEALTHY_GAME)
        result = verify_app(f)
        assert result["verdict"] == "healthy"
        assert result["health_score"] >= 70

    def test_skeleton_app(self, tmp_path):
        f = tmp_path / "skeleton.html"
        f.write_text(SKELETON_APP)
        result = verify_app(f)
        # Skeleton apps are detected as broken because js_lines < 10
        # triggers the critical failure override in verify_app
        assert result["verdict"] == "broken"
        assert result["checks"]["not_skeleton"]["js_lines"] < 10

    def test_tiny_file(self, tmp_path):
        f = tmp_path / "tiny.html"
        f.write_text("<html>hi</html>")
        result = verify_app(f)
        assert result["verdict"] == "broken"
        assert result["reason"] == "file-too-small"

    def test_result_structure(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text(HEALTHY_GAME)
        result = verify_app(f)
        assert "file" in result
        assert "health_score" in result
        assert "verdict" in result
        assert "checks" in result
        assert "js_syntax" in result["checks"]
        assert "canvas_renders" in result["checks"]
        assert "interaction_wired" in result["checks"]
        assert "not_skeleton" in result["checks"]
        assert "dead_code" in result["checks"]
        assert "state_coherence" in result["checks"]
        assert "error_resilience" in result["checks"]


# ===========================================================================
# Tests: Browser-Based Runtime Verification (all mocked)
# ===========================================================================

class TestCheckPlaywrightInstalled:
    def test_installed(self):
        mock_result = MagicMock(returncode=0)
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            assert check_playwright_installed() is True

    def test_not_installed(self):
        mock_result = MagicMock(returncode=1)
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            assert check_playwright_installed() is False

    def test_node_not_found(self):
        with patch("runtime_verify.subprocess.run", side_effect=FileNotFoundError):
            assert check_playwright_installed() is False

    def test_timeout(self):
        import subprocess
        with patch("runtime_verify.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 15)):
            assert check_playwright_installed() is False


class TestRunBrowserCheck:
    """Tests for run_browser_check — mocked subprocess calls."""

    PASSING_HARNESS_OUTPUT = json.dumps({
        "url": "http://127.0.0.1:8080/apps/games-puzzles/test.html",
        "pass": True,
        "passCount": 7,
        "totalChecks": 7,
        "checks": {
            "boot": {"pass": True, "errors": []},
            "canvas": {"pass": True, "applicable": True, "pixelCount": 5000},
            "gameLoop": {"pass": True, "rafCalls": 120},
            "noExternalReqs": {"pass": True, "externalUrls": []},
            "inputResponse": {"pass": True, "applicable": True},
            "noErrors": {"pass": True, "errorCount": 0, "errors": []},
            "loadTime": {"pass": True, "ms": 350},
        },
        "errors": [],
        "timestamp": "2026-02-07T00:00:00.000Z",
    })

    FAILING_HARNESS_OUTPUT = json.dumps({
        "url": "http://127.0.0.1:8080/apps/games-puzzles/broken.html",
        "pass": False,
        "passCount": 3,
        "totalChecks": 7,
        "checks": {
            "boot": {"pass": False, "errors": ["ReferenceError: foo is not defined"]},
            "canvas": {"pass": False, "applicable": True, "pixelCount": 0},
            "gameLoop": {"pass": True, "rafCalls": 60},
            "noExternalReqs": {"pass": True, "externalUrls": []},
            "inputResponse": {"pass": False, "applicable": True},
            "noErrors": {"pass": False, "errorCount": 1, "errors": ["ReferenceError: foo is not defined"]},
            "loadTime": {"pass": True, "ms": 200},
        },
        "errors": [],
        "timestamp": "2026-02-07T00:00:00.000Z",
    })

    def test_passing_result(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html></html>")
        mock_result = MagicMock(
            stdout=self.PASSING_HARNESS_OUTPUT,
            stderr="",
            returncode=0,
        )
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is True
        assert result["passCount"] == 7
        assert result["checks"]["boot"]["pass"] is True
        assert result["checks"]["canvas"]["pixelCount"] == 5000

    def test_failing_result(self, tmp_path):
        f = tmp_path / "broken.html"
        f.write_text("<html></html>")
        mock_result = MagicMock(
            stdout=self.FAILING_HARNESS_OUTPUT,
            stderr="",
            returncode=0,
        )
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is False
        assert result["passCount"] == 3
        assert result["checks"]["boot"]["pass"] is False

    def test_subprocess_timeout(self, tmp_path):
        import subprocess
        f = tmp_path / "slow.html"
        f.write_text("<html></html>")
        with patch("runtime_verify.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 25)):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is False
        assert "subprocess-timeout" in result["errors"]

    def test_node_not_found(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html></html>")
        with patch("runtime_verify.subprocess.run", side_effect=FileNotFoundError):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is False
        assert "node-not-found" in result["errors"]

    def test_empty_stdout(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html></html>")
        mock_result = MagicMock(stdout="", stderr="some error", returncode=1)
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is False
        assert any("some error" in e for e in result["errors"])

    def test_bad_json(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html></html>")
        mock_result = MagicMock(stdout="not json at all", stderr="", returncode=0)
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            result = run_browser_check(f, port=8080)
        assert result["pass"] is False
        assert any("json-parse-error" in e for e in result["errors"])

    def test_result_includes_file_info(self, tmp_path):
        f = tmp_path / "my-game.html"
        f.write_text("<html></html>")
        mock_result = MagicMock(
            stdout=self.PASSING_HARNESS_OUTPUT,
            stderr="",
            returncode=0,
        )
        with patch("runtime_verify.subprocess.run", return_value=mock_result):
            result = run_browser_check(f, port=8080)
        assert result["file"] == "my-game.html"
        assert result["path"] == str(f)


class TestDiscoverManifestApps:
    def test_discovers_apps(self, tmp_path):
        """Test discovery with a minimal manifest."""
        manifest = {
            "categories": {
                "games_puzzles": {
                    "folder": "games-puzzles",
                    "apps": [
                        {"file": "test-game.html"},
                        {"file": "missing-game.html"},
                    ],
                },
            },
        }
        # Create the apps directory structure
        apps_dir = tmp_path / "apps"
        games_dir = apps_dir / "games-puzzles"
        games_dir.mkdir(parents=True)
        (games_dir / "test-game.html").write_text("<html></html>")

        manifest_path = apps_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with patch("runtime_verify.MANIFEST", manifest_path), \
             patch("runtime_verify.APPS_DIR", apps_dir):
            files = discover_manifest_apps()

        assert len(files) == 1
        assert files[0].name == "test-game.html"

    def test_filter_by_category(self, tmp_path):
        manifest = {
            "categories": {
                "games_puzzles": {
                    "folder": "games-puzzles",
                    "apps": [{"file": "game.html"}],
                },
                "visual_art": {
                    "folder": "visual-art",
                    "apps": [{"file": "art.html"}],
                },
            },
        }
        apps_dir = tmp_path / "apps"
        (apps_dir / "games-puzzles").mkdir(parents=True)
        (apps_dir / "games-puzzles" / "game.html").write_text("<html></html>")
        (apps_dir / "visual-art").mkdir(parents=True)
        (apps_dir / "visual-art" / "art.html").write_text("<html></html>")
        manifest_path = apps_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with patch("runtime_verify.MANIFEST", manifest_path), \
             patch("runtime_verify.APPS_DIR", apps_dir):
            files = discover_manifest_apps(category="games_puzzles")

        assert len(files) == 1
        assert files[0].name == "game.html"

    def test_no_manifest(self, tmp_path):
        missing = tmp_path / "no-such-manifest.json"
        with patch("runtime_verify.MANIFEST", missing):
            assert discover_manifest_apps() == []


class TestStartLocalServer:
    def test_server_starts_and_serves(self, tmp_path):
        """Test that start_local_server actually starts and stops cleanly."""
        (tmp_path / "test.html").write_text("<html>hello</html>")
        server, port = start_local_server(tmp_path)
        assert port > 0
        assert port < 65536
        server.shutdown()


class TestBrowserReportPrinting:
    """Test that print_browser_report doesn't crash on various inputs."""

    def test_empty_results(self, capsys):
        from runtime_verify import print_browser_report
        print_browser_report([])
        out = capsys.readouterr().out
        assert "No results" in out

    def test_mixed_results(self, capsys):
        from runtime_verify import print_browser_report
        results = [
            {"file": "good.html", "pass": True, "passCount": 7, "totalChecks": 7,
             "checks": {"loadTime": {"pass": True, "ms": 100}}},
            {"file": "bad.html", "pass": False, "passCount": 3, "totalChecks": 7,
             "checks": {"boot": {"pass": False}, "canvas": {"pass": False}},
             "errors": []},
        ]
        print_browser_report(results)
        out = capsys.readouterr().out
        assert "Pass: 1" in out
        assert "Fail: 1" in out
        assert "good.html" in out
        assert "bad.html" in out
