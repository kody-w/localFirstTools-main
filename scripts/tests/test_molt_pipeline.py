"""
Tests for the molt pipeline (scripts/molt_pipeline.py).

All LLM calls are mocked -- no network needed.
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

# ─── Setup imports ────────────────────────────────────────────────────────────

scripts_dir = str(ROOT / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import importlib
import molt_pipeline
importlib.reload(molt_pipeline)
import rank_games
importlib.reload(rank_games)

# ─── Test Data ────────────────────────────────────────────────────────────────

MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width">
<title>Minimal</title>
</head><body><p>Hello</p></body></html>"""

RICH_HTML = """\
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rich Game</title>
<style>
  body { margin: 0; background: linear-gradient(#1a1a2e, #16213e); color: #fff; }
  canvas { display: block; }
  .hud { position: fixed; top: 10px; left: 10px; font-family: monospace; }
  @keyframes pulse { 0% { opacity: 1; } 100% { opacity: 0.5; } }
  @media (max-width: 600px) { .hud { font-size: 12px; } }
</style>
</head><body>
<canvas id="c" width="800" height="600"></canvas>
<div class="hud" role="status" aria-label="Score display">Score: <span id="score">0</span></div>
<script>
  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');
  const audioCtx = new AudioContext();
  let gameState = 'playing';
  let score = 0;
  let particles = [];
  let combo = 0;
  let level = 1;
  const enemies = [{type:'basic'},{type:'fast'},{type:'boss'}];

  class Enemy { constructor(type) { this.type = type; } }
  class Particle { constructor(x,y) { this.x=x; this.y=y; } }

  function playSound(freq) {
    const osc = audioCtx.createOscillator();
    osc.frequency.value = freq;
    osc.connect(audioCtx.destination);
    osc.start(); osc.stop(audioCtx.currentTime + 0.1);
  }
  function playSound2(f) { playSound(f*2); }
  function playSound3(f) { playSound(f*3); }
  function playSound4(f) { playSound(f*4); }
  function playSound5(f) { playSound(f*5); }

  function checkCollision(a, b) { return Math.abs(a.x-b.x) < 10; }
  function shake() { canvas.style.transform = 'translateX(2px)'; }

  function update(dt) {
    if (gameState === 'paused') return;
    score += dt * combo;
    localStorage.setItem('highScore', Math.max(score, localStorage.getItem('highScore')||0));
  }

  function draw() {
    ctx.clearRect(0, 0, 800, 600);
    particles.forEach(p => ctx.fillRect(p.x, p.y, 2, 2));
  }

  document.addEventListener('keydown', e => { if(e.key==='p') gameState='paused'; });
  document.addEventListener('keyup', e => { if(e.key==='p') gameState='playing'; });
  document.addEventListener('mousedown', e => { });
  addEventListener('touchstart', e => { });

  function gameLoop(ts) {
    const dt = 16;
    update(dt);
    draw();
    requestAnimationFrame(gameLoop);
  }
  function restart() { score = 0; gameState = 'playing'; }
  requestAnimationFrame(gameLoop);
</script>
</body></html>"""

SAMPLE_MANIFEST = {
    "categories": {
        "games_puzzles": {
            "title": "Games & Puzzles",
            "folder": "games-puzzles",
            "color": "#f59e0b",
            "count": 3,
            "apps": [
                {
                    "title": "Time Loop",
                    "file": "time-loop.html",
                    "description": "A time loop game",
                    "tags": ["game"],
                    "complexity": "intermediate",
                    "type": "game",
                    "featured": False,
                    "created": "2025-12-27",
                },
                {
                    "title": "Already Molted",
                    "file": "already-molted.html",
                    "description": "Already improved",
                    "tags": ["game"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2025-12-27",
                    "generation": 2,
                },
                {
                    "title": "Tiny Game",
                    "file": "tiny-game.html",
                    "description": "Very small",
                    "tags": ["game"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2025-12-27",
                },
            ],
        },
        "visual_art": {
            "title": "Visual Art",
            "folder": "visual-art",
            "color": "#ff6b9d",
            "count": 1,
            "apps": [
                {
                    "title": "Pixel Painter",
                    "file": "pixel-painter.html",
                    "description": "Draw pixel art",
                    "tags": ["canvas"],
                    "complexity": "simple",
                    "type": "drawing",
                    "featured": False,
                    "created": "2025-12-27",
                },
            ],
        },
        "experimental_ai": {
            "title": "Experimental AI",
            "folder": "experimental-ai",
            "color": "#9b59b6",
            "count": 1,
            "apps": [
                {
                    "title": "AI Bot",
                    "file": "ai-bot.html",
                    "description": "An AI experiment",
                    "tags": ["ai"],
                    "complexity": "intermediate",
                    "type": "interactive",
                    "featured": False,
                    "created": "2025-12-27",
                },
            ],
        },
    },
    "meta": {"version": "1.0", "lastUpdated": "2025-12-27"},
}

MOCK_SCORE = {
    "score": 60, "grade": "C", "title": "T", "lines": 100,
    "size_bytes": 5000,
    "dimensions": {
        "structural": {"score": 13, "max": 15},
        "scale": {"score": 5, "max": 10},
        "systems": {"score": 15, "max": 20},
        "completeness": {"score": 8, "max": 15},
        "playability": {"score": 10, "max": 25},
        "polish": {"score": 9, "max": 15},
    },
}


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project structure."""
    apps_dir = tmp_path / "apps"
    games_dir = apps_dir / "games-puzzles"
    visual_dir = apps_dir / "visual-art"
    ai_dir = apps_dir / "experimental-ai"

    games_dir.mkdir(parents=True)
    visual_dir.mkdir(parents=True)
    ai_dir.mkdir(parents=True)

    (games_dir / "time-loop.html").write_text(RICH_HTML)
    (games_dir / "already-molted.html").write_text(RICH_HTML)
    (games_dir / "tiny-game.html").write_text(MINIMAL_HTML)
    (visual_dir / "pixel-painter.html").write_text(RICH_HTML)
    (ai_dir / "ai-bot.html").write_text(RICH_HTML)

    (apps_dir / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST, indent=2))

    return tmp_path


# ─── TestScoreSingleApp ──────────────────────────────────────────────────────


class TestScoreSingleApp:
    """Test the score_single_app convenience function."""

    def test_scores_valid_html(self, tmp_path):
        """Returns score dict with all 6 dimensions."""
        f = tmp_path / "test.html"
        f.write_text(RICH_HTML)
        result = rank_games.score_single_app(f)
        assert "score" in result
        assert "grade" in result
        assert "dimensions" in result
        for dim in ["structural", "scale", "systems", "completeness", "playability", "polish"]:
            assert dim in result["dimensions"]

    def test_scores_minimal_html(self, tmp_path):
        """Minimal HTML gets low but valid score."""
        f = tmp_path / "minimal.html"
        f.write_text(MINIMAL_HTML)
        result = rank_games.score_single_app(f)
        assert 0 <= result["score"] <= 100
        assert result["score"] < 30

    def test_scores_rich_html(self, tmp_path):
        """HTML with canvas, game loop, audio gets high systems score."""
        f = tmp_path / "rich.html"
        f.write_text(RICH_HTML)
        result = rank_games.score_single_app(f)
        assert result["dimensions"]["systems"]["score"] >= 10

    def test_score_has_grade(self, tmp_path):
        """Score includes grade letter."""
        f = tmp_path / "test.html"
        f.write_text(RICH_HTML)
        result = rank_games.score_single_app(f)
        assert result["grade"] in ("S", "A", "B", "C", "D", "F")

    def test_score_dimensions_sum(self, tmp_path):
        """Dimension scores sum to total (within rounding)."""
        f = tmp_path / "test.html"
        f.write_text(RICH_HTML)
        result = rank_games.score_single_app(f)
        dim_sum = sum(d["score"] for d in result["dimensions"].values())
        assert dim_sum == result["score"]


# ─── TestPipelineRun ──────────────────────────────────────────────────────────


class TestPipelineRun:
    """Test the run_pipeline function."""

    def test_pipeline_runs_4_generations(self, tmp_project):
        """Calls molt_app 4 times."""
        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=4,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            assert mock_molt.call_count == 4

    def test_pipeline_records_baseline_score(self, tmp_project):
        """Report has baseline_score from initial scoring."""
        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=1,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            assert report["baseline_score"] == 60

    def test_pipeline_records_score_after_each_molt(self, tmp_project):
        """Timeline has 4 entries when running 4 gens."""
        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=4,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            assert len(report["timeline"]) == 4

    def test_pipeline_handles_molt_failure(self, tmp_project):
        """If molt_app returns failed, continues to next gen."""
        call_count = [0]
        def side_effect(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 2:
                return {"status": "failed", "reason": "Copilot error"}
            return {"status": "success", "previousSize": 5000, "newSize": 5200}

        with mock.patch("molt_pipeline.molt_app", side_effect=side_effect), \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=4,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            assert len(report["timeline"]) == 4
            assert report["timeline"][1]["status"] == "failed"
            assert report["generations_succeeded"] == 3

    def test_pipeline_handles_molt_rejection(self, tmp_project):
        """If molt_app returns rejected, continues to next gen."""
        call_count = [0]
        def side_effect(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"status": "rejected", "reason": "Missing DOCTYPE"}
            return {"status": "success", "previousSize": 5000, "newSize": 5200}

        with mock.patch("molt_pipeline.molt_app", side_effect=side_effect), \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=3,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            assert report["timeline"][0]["status"] == "rejected"
            assert report["generations_succeeded"] == 2

    def test_pipeline_writes_report_json(self, tmp_project):
        """pipeline-report.json created in archive."""
        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE):
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=1,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

            report_path = tmp_project / "apps" / "archive" / "time-loop" / "pipeline-report.json"
            assert report_path.exists()
            data = json.loads(report_path.read_text())
            assert data["file"] == "time-loop.html"

    def test_pipeline_saves_manifest(self, tmp_project):
        """Manifest saved when _manifest is not passed."""
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))

        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", return_value=MOCK_SCORE), \
             mock.patch("molt_pipeline.save_manifest") as mock_save, \
             mock.patch("molt_pipeline.load_manifest", return_value=manifest), \
             mock.patch("molt_pipeline.resolve_app") as mock_resolve:

            path = tmp_project / "apps" / "games-puzzles" / "time-loop.html"
            app_entry = manifest["categories"]["games_puzzles"]["apps"][0]
            mock_resolve.return_value = (path, "games_puzzles", app_entry)
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            # _manifest=None triggers load_manifest + save_manifest
            report = molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=1,
                _apps_dir=tmp_project / "apps",
            )

            mock_save.assert_called_once()


# ─── TestPipelineReport ──────────────────────────────────────────────────────


class TestPipelineReport:
    """Test the pipeline report structure."""

    def _make_report(self, tmp_project):
        # score_single_app is called: 1 baseline + (1 before + 1 after) * 4 gens + 1 final = 10
        scores = iter([
            dict(MOCK_SCORE, score=55, grade="C"),  # baseline
            dict(MOCK_SCORE, score=55, grade="C"),  # before gen 1
            dict(MOCK_SCORE, score=60, grade="C"),  # after gen 1
            dict(MOCK_SCORE, score=60, grade="C"),  # before gen 2
            dict(MOCK_SCORE, score=65, grade="B"),  # after gen 2
            dict(MOCK_SCORE, score=65, grade="B"),  # before gen 3
            dict(MOCK_SCORE, score=70, grade="B"),  # after gen 3
            dict(MOCK_SCORE, score=70, grade="B"),  # before gen 4
            dict(MOCK_SCORE, score=72, grade="B"),  # after gen 4
            dict(MOCK_SCORE, score=72, grade="B"),  # final
        ])
        def score_side(*a, **kw):
            return next(scores, dict(MOCK_SCORE, score=72, grade="B"))

        with mock.patch("molt_pipeline.molt_app") as mock_molt, \
             mock.patch("molt_pipeline.score_single_app", side_effect=score_side):
            mock_molt.return_value = {"status": "success", "previousSize": 5000, "newSize": 5200}

            return molt_pipeline.run_pipeline(
                "time-loop.html", num_gens=4,
                _manifest=json.loads(json.dumps(SAMPLE_MANIFEST)),
                _apps_dir=tmp_project / "apps",
            )

    def test_report_has_required_fields(self, tmp_project):
        """Report has file, baseline_score, final_score, total_delta, timeline."""
        report = self._make_report(tmp_project)
        for field in ["file", "baseline_score", "final_score", "total_delta", "timeline"]:
            assert field in report, f"Missing field: {field}"

    def test_report_timeline_entries(self, tmp_project):
        """Each entry has generation, focus, score_before, score_after."""
        report = self._make_report(tmp_project)
        for entry in report["timeline"]:
            for field in ["generation", "focus", "score_before", "score_after"]:
                assert field in entry, f"Missing field in timeline entry: {field}"

    def test_report_total_delta_correct(self, tmp_project):
        """final_score - baseline_score == total_delta."""
        report = self._make_report(tmp_project)
        assert report["total_delta"] == report["final_score"] - report["baseline_score"]

    def test_report_json_serializable(self, tmp_project):
        """Report can be json.dumps'd."""
        report = self._make_report(tmp_project)
        serialized = json.dumps(report)
        assert isinstance(serialized, str)
        roundtrip = json.loads(serialized)
        assert roundtrip["file"] == report["file"]


# ─── TestAppSelection ────────────────────────────────────────────────────────


class TestAppSelection:
    """Test the select_candidates function."""

    def test_select_candidates(self, tmp_project):
        """Finds gen-0 apps in score range."""
        with mock.patch.object(molt_pipeline, "APPS_DIR", tmp_project / "apps"), \
             mock.patch("molt_pipeline.score_single_app") as mock_score:
            # Return scores in the valid range for gen-0 apps
            def score_side(filepath):
                name = Path(filepath).name
                scores_map = {
                    "time-loop.html": 55,
                    "tiny-game.html": 45,
                    "pixel-painter.html": 50,
                    "ai-bot.html": 60,
                }
                s = scores_map.get(name, 50)
                return dict(MOCK_SCORE, score=s, grade="C")
            mock_score.side_effect = score_side

            candidates = molt_pipeline.select_candidates(
                SAMPLE_MANIFEST, apps_dir=tmp_project / "apps",
                score_min=40, score_max=65,
            )

        filenames = [c["file"] for c in candidates]
        assert "time-loop.html" in filenames
        assert "pixel-painter.html" in filenames

    def test_select_excludes_molted(self, tmp_project):
        """Skips apps with generation > 0."""
        with mock.patch.object(molt_pipeline, "APPS_DIR", tmp_project / "apps"), \
             mock.patch("molt_pipeline.score_single_app", return_value=dict(MOCK_SCORE, score=55)):

            candidates = molt_pipeline.select_candidates(
                SAMPLE_MANIFEST, apps_dir=tmp_project / "apps",
                score_min=40, score_max=65,
            )

        filenames = [c["file"] for c in candidates]
        assert "already-molted.html" not in filenames

    def test_select_excludes_oversized(self, tmp_project):
        """Skips apps > max_size."""
        # Write an oversized file
        oversized = tmp_project / "apps" / "games-puzzles" / "time-loop.html"
        oversized.write_text("<!DOCTYPE html>" + "x" * 200_000)

        with mock.patch.object(molt_pipeline, "APPS_DIR", tmp_project / "apps"), \
             mock.patch("molt_pipeline.score_single_app", return_value=dict(MOCK_SCORE, score=55)):

            candidates = molt_pipeline.select_candidates(
                SAMPLE_MANIFEST, apps_dir=tmp_project / "apps",
                score_min=40, score_max=65, max_size=100_000,
            )

        filenames = [c["file"] for c in candidates]
        assert "time-loop.html" not in filenames

    def test_select_returns_diverse_categories(self, tmp_project):
        """Picks from multiple categories."""
        with mock.patch.object(molt_pipeline, "APPS_DIR", tmp_project / "apps"), \
             mock.patch("molt_pipeline.score_single_app", return_value=dict(MOCK_SCORE, score=55)):

            candidates = molt_pipeline.select_candidates(
                SAMPLE_MANIFEST, apps_dir=tmp_project / "apps",
                score_min=40, score_max=65,
            )

        categories = set(c["category"] for c in candidates)
        assert len(categories) >= 2
