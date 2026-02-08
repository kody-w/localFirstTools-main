"""
Tests for the Buzzsaw v3 pipeline (scripts/buzzsaw_pipeline.py).

All functions tested with dependency injection — no network, no disk I/O.
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import pytest
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_MANIFEST = {
    "categories": {
        "games_puzzles": {
            "name": "Games & Puzzles",
            "folder": "games-puzzles",
            "count": 3,
            "apps": [
                {"title": "Recursion", "file": "recursion.html", "description": "Nested game", "tags": ["game"]},
                {"title": "Flesh Machine", "file": "flesh-machine.html", "description": "Bio horror", "tags": ["game"]},
                {"title": "The Trial", "file": "the-trial.html", "description": "Kafka court", "tags": ["game"]},
            ],
        },
        "visual_art": {
            "name": "Visual Art",
            "folder": "visual-art",
            "count": 1,
            "apps": [
                {"title": "Pixel Paint", "file": "pixel-paint.html", "description": "Pixel editor", "tags": ["art"]},
            ],
        },
        "3d_immersive": {
            "name": "3D Immersive",
            "folder": "3d-immersive",
            "count": 2,
            "apps": [
                {"title": "Voxel World", "file": "voxel-world.html", "description": "3D voxels", "tags": ["3d"]},
                {"title": "Planet Gen", "file": "planet-gen.html", "description": "Planets", "tags": ["3d"]},
            ],
        },
        "audio_music": {
            "name": "Audio & Music",
            "folder": "audio-music",
            "count": 0,
            "apps": [],
        },
    },
    "meta": {"version": "1.0", "lastUpdated": "2025-01-01"},
}


SAMPLE_RANKINGS = {
    "categories": {
        "games_puzzles": {
            "apps": [
                {"file": "recursion.html", "title": "Recursion", "score": 92, "grade": "A+"},
                {"file": "flesh-machine.html", "title": "Flesh Machine", "score": 88, "grade": "A"},
                {"file": "the-trial.html", "title": "The Trial", "score": 75, "grade": "B"},
            ],
        },
        "visual_art": {
            "apps": [
                {"file": "pixel-paint.html", "title": "Pixel Paint", "score": 60, "grade": "C"},
            ],
        },
    },
}


MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head><title>Test</title>
<meta name="viewport" content="width=device-width">
<style>body{margin:0}</style>
</head><body>
<script>
const x = document.getElementById('test');
x.addEventListener('click', () => {});
localStorage.setItem('test', 'value');
</script>
</body></html>"""

# Make it 600 lines and >20KB for validation
BIG_GAME_HTML = "<!DOCTYPE html>\n<html><head><title>Big Game</title>\n" + \
    '<meta name="viewport" content="width=device-width">\n' + \
    "<style>\nbody { margin: 0; background: #000; }\n" + \
    "canvas { display: block; }\n" + \
    "\n".join(f".class-{i} {{ color: hsl({i}, 50%, 50%); }}" for i in range(200)) + \
    "\n</style>\n</head>\n<body>\n<canvas id='c'></canvas>\n<script>\n" + \
    "const canvas = document.getElementById('c');\n" + \
    "const ctx = canvas.getContext('2d');\n" + \
    "document.addEventListener('keydown', e => {});\n" + \
    "localStorage.setItem('save', JSON.stringify({score: 0}));\n" + \
    "function gameLoop() { requestAnimationFrame(gameLoop); }\n" + \
    "\n".join(f"// game logic line {i}\nlet variable{i} = {i};" for i in range(300)) + \
    "\ngameLoop();\n</script>\n</body>\n</html>"


# ─── Deduplication Tests ──────────────────────────────────────────────────────

class TestDeduplication:
    def test_get_existing_titles(self):
        from buzzsaw_pipeline import get_existing_titles
        titles = get_existing_titles(SAMPLE_MANIFEST)
        assert "recursion" in titles
        assert "flesh machine" in titles
        assert "pixel paint" in titles
        assert len(titles) == 6

    def test_get_existing_files(self):
        from buzzsaw_pipeline import get_existing_files
        files = get_existing_files(SAMPLE_MANIFEST)
        assert "recursion.html" in files
        assert "flesh-machine.html" in files
        assert len(files) == 6

    def test_is_duplicate_by_title(self):
        from buzzsaw_pipeline import is_duplicate
        assert is_duplicate("Recursion", "new-file.html", SAMPLE_MANIFEST) is True

    def test_is_duplicate_by_title_case_insensitive(self):
        from buzzsaw_pipeline import is_duplicate
        assert is_duplicate("RECURSION", "new-file.html", SAMPLE_MANIFEST) is True
        assert is_duplicate("recursion", "new-file.html", SAMPLE_MANIFEST) is True

    def test_is_duplicate_by_filename(self):
        from buzzsaw_pipeline import is_duplicate
        assert is_duplicate("New Game", "recursion.html", SAMPLE_MANIFEST) is True

    def test_not_duplicate(self):
        from buzzsaw_pipeline import is_duplicate
        assert is_duplicate("Brand New Game", "brand-new.html", SAMPLE_MANIFEST) is False

    def test_deduplicate_concepts(self):
        from buzzsaw_pipeline import deduplicate_concepts
        concepts = [
            {"title": "Recursion", "filename": "recursion.html"},
            {"title": "Brand New Game", "filename": "brand-new.html"},
            {"title": "Flesh Machine", "filename": "fm2.html"},
            {"title": "Another New", "filename": "another-new.html"},
        ]
        result = deduplicate_concepts(concepts, SAMPLE_MANIFEST)
        assert len(result) == 2
        assert result[0]["title"] == "Brand New Game"
        assert result[1]["title"] == "Another New"

    def test_deduplicate_removes_self_dupes(self):
        """Concepts that duplicate each other should also be deduped."""
        from buzzsaw_pipeline import deduplicate_concepts
        concepts = [
            {"title": "Same Game", "filename": "same-game.html"},
            {"title": "Same Game", "filename": "same-game-2.html"},
        ]
        result = deduplicate_concepts(concepts, SAMPLE_MANIFEST)
        assert len(result) == 1

    def test_deduplicate_empty_manifest(self):
        from buzzsaw_pipeline import deduplicate_concepts
        empty = {"categories": {}, "meta": {}}
        concepts = [{"title": "Game A", "filename": "a.html"}]
        result = deduplicate_concepts(concepts, empty)
        assert len(result) == 1


# ─── Quality Gate Tests ───────────────────────────────────────────────────────

class TestQualityGate:
    def test_score_app_returns_expected_keys(self, tmp_path):
        from buzzsaw_pipeline import score_app
        f = tmp_path / "games-puzzles" / "test.html"
        f.parent.mkdir(parents=True)
        f.write_text(BIG_GAME_HTML)
        result = score_app(f)
        assert "score" in result
        assert "passed" in result
        assert "threshold" in result
        assert isinstance(result["score"], (int, float))

    def test_quality_gate_passes_good_file(self, tmp_path):
        from buzzsaw_pipeline import quality_gate
        f = tmp_path / "test.html"
        f.write_text(BIG_GAME_HTML)
        passed, report = quality_gate(f, threshold=20)
        assert passed is True
        assert report["score"] >= 20

    def test_quality_gate_fails_low_threshold(self, tmp_path):
        from buzzsaw_pipeline import quality_gate
        f = tmp_path / "test.html"
        f.write_text(MINIMAL_HTML)
        passed, report = quality_gate(f, threshold=99)
        assert passed is False

    def test_quality_gate_batch(self, tmp_path):
        from buzzsaw_pipeline import quality_gate_batch
        good = tmp_path / "good.html"
        good.write_text(BIG_GAME_HTML)
        bad = tmp_path / "bad.html"
        bad.write_text("<html><body>tiny</body></html>")
        result = quality_gate_batch([good, bad], threshold=20)
        assert len(result["passed"]) == 1
        assert len(result["failed"]) == 1


# ─── Category Balancing Tests ─────────────────────────────────────────────────

class TestCategoryBalance:
    def test_get_category_counts(self):
        from buzzsaw_pipeline import get_category_counts
        counts = get_category_counts(SAMPLE_MANIFEST)
        assert counts["games_puzzles"] == 3
        assert counts["visual_art"] == 1
        assert counts["audio_music"] == 0

    def test_get_underserved_categories(self):
        from buzzsaw_pipeline import get_underserved_categories
        underserved = get_underserved_categories(SAMPLE_MANIFEST, top_n=2)
        assert len(underserved) == 2
        # audio_music has 0, visual_art has 1
        assert underserved[0][0] == "audio_music"
        assert underserved[0][1] == 0
        assert underserved[1][0] == "visual_art"
        assert underserved[1][1] == 1

    def test_suggest_distribution_favors_underserved(self):
        from buzzsaw_pipeline import suggest_category_distribution
        dist = suggest_category_distribution(10, SAMPLE_MANIFEST)
        # audio_music (0 apps) should get the most
        assert dist.get("audio_music", 0) >= dist.get("games_puzzles", 0)

    def test_suggest_distribution_total_matches(self):
        from buzzsaw_pipeline import suggest_category_distribution
        dist = suggest_category_distribution(10, SAMPLE_MANIFEST)
        assert sum(dist.values()) == 10

    def test_suggest_distribution_single_game(self):
        from buzzsaw_pipeline import suggest_category_distribution
        dist = suggest_category_distribution(1, SAMPLE_MANIFEST)
        assert sum(dist.values()) == 1

    def test_suggest_distribution_empty_manifest(self):
        from buzzsaw_pipeline import suggest_category_distribution
        empty = {"categories": {}, "meta": {}}
        dist = suggest_category_distribution(5, empty)
        assert sum(dist.values()) == 5


# ─── Feedback Loop Tests ─────────────────────────────────────────────────────

class TestFeedbackLoop:
    def test_get_top_apps(self, tmp_path):
        from buzzsaw_pipeline import get_top_apps
        rankings_file = tmp_path / "rankings.json"
        rankings_file.write_text(json.dumps(SAMPLE_RANKINGS))
        top = get_top_apps(n=3, rankings_path=rankings_file)
        assert len(top) == 3
        assert top[0]["title"] == "Recursion"
        assert top[0]["score"] == 92
        assert top[1]["title"] == "Flesh Machine"

    def test_get_top_apps_filtered_by_category(self, tmp_path):
        from buzzsaw_pipeline import get_top_apps
        rankings_file = tmp_path / "rankings.json"
        rankings_file.write_text(json.dumps(SAMPLE_RANKINGS))
        top = get_top_apps(n=5, category="visual_art", rankings_path=rankings_file)
        assert len(top) == 1
        assert top[0]["title"] == "Pixel Paint"

    def test_get_top_apps_missing_file(self):
        from buzzsaw_pipeline import get_top_apps
        top = get_top_apps(rankings_path="/nonexistent/rankings.json")
        assert top == []

    def test_build_feedback_prompt_section(self):
        from buzzsaw_pipeline import build_feedback_prompt_section
        top = [
            {"title": "Recursion", "score": 92, "grade": "A+", "category": "games_puzzles", "file": "recursion.html"},
            {"title": "Flesh Machine", "score": 88, "grade": "A", "category": "games_puzzles", "file": "flesh-machine.html"},
        ]
        section = build_feedback_prompt_section(top)
        assert "Recursion" in section
        assert "92/100" in section
        assert "A+" in section
        assert "70+" in section

    def test_build_feedback_prompt_empty(self):
        from buzzsaw_pipeline import build_feedback_prompt_section
        section = build_feedback_prompt_section([])
        assert section == ""


# ─── Community Injection Tests ────────────────────────────────────────────────

class TestCommunityInjection:
    def test_generate_community_entries_structure(self):
        from buzzsaw_pipeline import generate_community_entries
        apps = [("game.html", "My Game"), ("puzzle.html", "My Puzzle")]
        result = generate_community_entries(apps, num_comments_per_app=2, num_ratings_per_app=3, seed=42)
        assert "comments" in result
        assert "ratings" in result
        assert len(result["comments"]) == 4  # 2 apps * 2 comments
        assert "game.html" in result["ratings"]
        assert "puzzle.html" in result["ratings"]

    def test_community_ratings_valid(self):
        from buzzsaw_pipeline import generate_community_entries
        result = generate_community_entries(
            [("test.html", "Test")], num_ratings_per_app=10, seed=42
        )
        ratings = result["ratings"]["test.html"]
        assert ratings["count"] == 10
        assert 3.0 <= ratings["avg"] <= 5.0
        assert all(3 <= r <= 5 for r in ratings["ratings"])

    def test_community_comments_have_required_fields(self):
        from buzzsaw_pipeline import generate_community_entries
        result = generate_community_entries(
            [("test.html", "Test")], num_comments_per_app=1, seed=42
        )
        comment = result["comments"][0]
        assert "app" in comment
        assert "author" in comment
        assert "text" in comment
        assert "timestamp" in comment
        assert comment["app"] == "test.html"

    def test_community_deterministic_with_seed(self):
        from buzzsaw_pipeline import generate_community_entries
        apps = [("a.html", "Game A")]
        r1 = generate_community_entries(apps, seed=123)
        r2 = generate_community_entries(apps, seed=123)
        assert r1["comments"][0]["text"] == r2["comments"][0]["text"]
        assert r1["ratings"] == r2["ratings"]


# ─── Validation Tests ─────────────────────────────────────────────────────────

class TestValidation:
    def test_validate_good_file(self, tmp_path):
        from buzzsaw_pipeline import validate_html_file
        f = tmp_path / "good.html"
        f.write_text(BIG_GAME_HTML)
        result = validate_html_file(f)
        assert result["passed"] is True
        assert len(result["failures"]) == 0

    def test_validate_missing_file(self, tmp_path):
        from buzzsaw_pipeline import validate_html_file
        result = validate_html_file(tmp_path / "nonexistent.html")
        assert result["passed"] is False
        assert "does not exist" in result["failures"][0]

    def test_validate_small_file(self, tmp_path):
        from buzzsaw_pipeline import validate_html_file
        f = tmp_path / "small.html"
        f.write_text("<!DOCTYPE html><html><body>tiny</body></html>")
        result = validate_html_file(f)
        assert result["passed"] is False
        assert any("too small" in f.lower() for f in result["failures"])

    def test_validate_no_doctype(self, tmp_path):
        from buzzsaw_pipeline import validate_html_file
        content = "<html><body>" + "x\n" * 600 + "localStorage.setItem('a','b');</body></html>"
        f = tmp_path / "no-doctype.html"
        f.write_text(content)
        result = validate_html_file(f)
        assert any("DOCTYPE" in f for f in result["failures"])

    def test_validate_external_deps(self, tmp_path):
        from buzzsaw_pipeline import validate_html_file
        content = '<!DOCTYPE html>\n<html><head>\n' + \
            '<script src="https://cdn.example.com/lib.js"></script>\n' + \
            "</head><body>\n" + "x\n" * 600 + \
            "localStorage.setItem('a','b');\n</body></html>"
        f = tmp_path / "ext.html"
        f.write_text(content)
        result = validate_html_file(f)
        assert any("External" in f for f in result["failures"])

    def test_build_fix_prompt(self):
        from buzzsaw_pipeline import build_fix_prompt
        failures = ["Missing localStorage usage", "File too small: 1000 bytes"]
        prompt = build_fix_prompt("/tmp/test.html", failures)
        assert "localStorage" in prompt
        assert "too small" in prompt.lower() or "File too small" in prompt


# ─── Manifest Helper Tests ────────────────────────────────────────────────────

class TestManifestHelpers:
    def test_make_manifest_entry(self):
        from buzzsaw_pipeline import make_manifest_entry
        entry = make_manifest_entry(
            "Test Game", "test-game.html",
            description="A test game",
            tags=["canvas", "game"],
        )
        assert entry["title"] == "Test Game"
        assert entry["file"] == "test-game.html"
        assert entry["created"] == date.today().isoformat()
        assert entry["complexity"] == "advanced"
        assert entry["type"] == "game"

    def test_add_apps_to_manifest(self):
        from buzzsaw_pipeline import add_apps_to_manifest, make_manifest_entry
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))  # deep copy
        entries = [
            make_manifest_entry("New Game", "new-game.html", description="A new game"),
        ]
        with mock.patch("buzzsaw_pipeline.save_manifest"):
            result = add_apps_to_manifest(entries, "games_puzzles", manifest)
        apps = result["categories"]["games_puzzles"]["apps"]
        assert len(apps) == 4
        assert apps[-1]["title"] == "New Game"
        assert result["categories"]["games_puzzles"]["count"] == 4

    def test_add_apps_skips_existing(self):
        from buzzsaw_pipeline import add_apps_to_manifest, make_manifest_entry
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        entries = [
            make_manifest_entry("Recursion", "recursion.html"),  # already exists
        ]
        with mock.patch("buzzsaw_pipeline.save_manifest"):
            result = add_apps_to_manifest(entries, "games_puzzles", manifest)
        assert len(result["categories"]["games_puzzles"]["apps"]) == 3  # unchanged

    def test_add_apps_multiple(self):
        from buzzsaw_pipeline import add_apps_to_manifest, make_manifest_entry
        manifest = json.loads(json.dumps(SAMPLE_MANIFEST))
        entries = [
            make_manifest_entry("Game A", "game-a.html"),
            make_manifest_entry("Game B", "game-b.html"),
            make_manifest_entry("Game C", "game-c.html"),
        ]
        with mock.patch("buzzsaw_pipeline.save_manifest"):
            result = add_apps_to_manifest(entries, "games_puzzles", manifest)
        assert len(result["categories"]["games_puzzles"]["apps"]) == 6
        assert result["categories"]["games_puzzles"]["count"] == 6
