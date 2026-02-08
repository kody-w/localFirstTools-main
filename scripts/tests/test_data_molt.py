#!/usr/bin/env python3
"""Tests for the universal data molt engine.

Tests discovery, staleness analysis, routing, validation, archiving,
and generation tracking for ANY content type in the ecosystem.
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Fixtures ──

@pytest.fixture
def temp_ecosystem(tmp_path):
    """Create a minimal ecosystem with various data file types."""
    apps = tmp_path / "apps"
    apps.mkdir()

    # manifest.json
    manifest = {
        "categories": {
            "games_puzzles": {
                "title": "Games & Puzzles",
                "folder": "games-puzzles",
                "color": "#ff0000",
                "count": 2,
                "apps": [
                    {"title": "Test Game", "file": "test-game.html", "description": "A test",
                     "tags": ["game"], "complexity": "simple", "type": "game",
                     "featured": False, "created": "2026-01-01"},
                    {"title": "Puzzle App", "file": "puzzle-app.html", "description": "A puzzle",
                     "tags": ["puzzle"], "complexity": "intermediate", "type": "game",
                     "featured": False, "created": "2026-01-15"},
                ]
            }
        },
        "meta": {"version": "1.0", "lastUpdated": "2026-02-08"}
    }
    (apps / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # rankings.json
    rankings = {
        "generated": "2026-02-01T00:00:00",
        "total_apps": 2,
        "apps": {
            "test-game.html": {"score": 75, "grade": "B", "playability": 18},
            "puzzle-app.html": {"score": 42, "grade": "C", "playability": 10},
        },
        "summary": {"median_score": 58}
    }
    (apps / "rankings.json").write_text(json.dumps(rankings, indent=2))

    # community.json (stale — duplicate comments)
    community = {
        "meta": {"totalPlayers": 5, "generated": "2026-01-15T00:00:00"},
        "apps": {
            "test-game.html": {
                "ratings": {"ratings": [4, 5, 4], "avg": 4.33, "count": 3},
                "comments": [
                    {"author": "Player1", "text": "Great game!", "upvotes": 10},
                    {"author": "Player2", "text": "Great game!", "upvotes": 5},
                ]
            }
        }
    }
    (apps / "community.json").write_text(json.dumps(community, indent=2))

    # broadcasts/feed.json (stale — duplicate dialogue)
    broadcasts = apps / "broadcasts"
    broadcasts.mkdir()
    feed = {
        "meta": {"showTitle": "RappterZooNation", "totalEpisodes": 1,
                 "generated": "2026-01-20T00:00:00"},
        "episodes": [{
            "id": "ep-001", "number": 1, "title": "Episode 1",
            "segments": [
                {"type": "intro", "host": "Rapptr", "text": "Welcome to the show!"},
                {"type": "intro", "host": "ZooKeeper", "text": "Median score: 58."},
                {"type": "review", "app": {"title": "Test Game", "file": "test-game.html"},
                 "dialogue": [
                     {"host": "Rapptr", "text": "This game is amazing and I love it."},
                     {"host": "ZooKeeper", "text": "Score of 75. Solid B-grade."},
                     {"host": "Rapptr", "text": "This game is amazing and I love it."},
                 ]},
                {"type": "outro", "host": "Rapptr", "text": "That's a wrap!"},
            ]
        }]
    }
    (broadcasts / "feed.json").write_text(json.dumps(feed, indent=2))
    (broadcasts / "lore.json").write_text(json.dumps({"reviewed_apps": {}, "episode_summaries": []}, indent=2))

    # content-graph.json (stale — missing an app)
    graph = {
        "meta": {"total_nodes": 1, "generated": "2026-01-10T00:00:00"},
        "nodes": [{"id": "test-game.html", "title": "Test Game"}],
        "edges": []
    }
    (apps / "content-graph.json").write_text(json.dumps(graph, indent=2))

    # A novel file type the engine has never seen
    (apps / "leaderboard.json").write_text(json.dumps({
        "format": "leaderboard-v1",
        "entries": [{"player": "Bot1", "score": 999}]
    }, indent=2))

    # molter-state.json
    (apps / "molter-state.json").write_text(json.dumps({"frame": 10}, indent=2))

    # Create HTML app stubs
    gp = apps / "games-puzzles"
    gp.mkdir()
    (gp / "test-game.html").write_text("<!DOCTYPE html><title>Test Game</title>")
    (gp / "puzzle-app.html").write_text("<!DOCTYPE html><title>Puzzle App</title>")

    # Archive dir
    (apps / "archive" / "data").mkdir(parents=True)

    return tmp_path


# ── Discovery Tests ──

class TestDiscovery:
    """The engine should find all data files regardless of type."""

    def test_discovers_json_files(self, temp_ecosystem):
        from data_molt import discover_data_files
        files = discover_data_files(temp_ecosystem / "apps")
        paths = {str(f.relative_to(temp_ecosystem / "apps")) for f in files}
        assert "manifest.json" in paths
        assert "rankings.json" in paths
        assert "community.json" in paths
        assert "content-graph.json" in paths
        assert "broadcasts/feed.json" in paths
        assert "broadcasts/lore.json" in paths
        assert "leaderboard.json" in paths

    def test_excludes_html_files(self, temp_ecosystem):
        """HTML files are handled by the HTML molt system, not data molt."""
        from data_molt import discover_data_files
        files = discover_data_files(temp_ecosystem / "apps")
        for f in files:
            assert f.suffix != ".html", f"Should not discover HTML: {f}"

    def test_excludes_archive(self, temp_ecosystem):
        """Archived versions should not be discovered for molting."""
        from data_molt import discover_data_files
        # Put a file in archive
        archive_file = temp_ecosystem / "apps" / "archive" / "data" / "old.json"
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        archive_file.write_text("{}")
        files = discover_data_files(temp_ecosystem / "apps")
        for f in files:
            assert "archive" not in f.parts, f"Should skip archive: {f}"

    def test_discovers_unknown_formats(self, temp_ecosystem):
        """Engine should find files it's never seen before."""
        novel = temp_ecosystem / "apps" / "experiment.toml"
        novel.write_text("[section]\nkey = 'value'")
        from data_molt import discover_data_files
        files = discover_data_files(temp_ecosystem / "apps")
        extensions = {f.suffix for f in files}
        assert ".toml" in extensions


# ── Staleness Analysis Tests ──

class TestStalenessAnalysis:
    """The engine should detect stale content via LLM."""

    def test_analyze_returns_required_fields(self, temp_ecosystem):
        from data_molt import analyze_staleness
        mock_response = json.dumps({
            "stale": True, "score": 30, "strategy": "regenerate",
            "issues": ["Duplicate comments", "Missing apps"]
        })
        with patch("data_molt.copilot_call", return_value=mock_response):
            result = analyze_staleness(
                temp_ecosystem / "apps" / "community.json",
                ecosystem_context={"total_apps": 2, "frame": 10}
            )
        assert "stale" in result
        assert "score" in result
        assert "strategy" in result
        assert "issues" in result

    def test_fresh_content_not_flagged(self, temp_ecosystem):
        from data_molt import analyze_staleness
        mock_response = json.dumps({
            "stale": False, "score": 90, "strategy": "skip",
            "issues": []
        })
        with patch("data_molt.copilot_call", return_value=mock_response):
            result = analyze_staleness(
                temp_ecosystem / "apps" / "rankings.json",
                ecosystem_context={"total_apps": 2, "frame": 10}
            )
        assert result["stale"] is False
        assert result["strategy"] == "skip"

    def test_analysis_handles_llm_failure(self, temp_ecosystem):
        """If LLM fails, analysis should return conservative defaults."""
        from data_molt import analyze_staleness
        with patch("data_molt.copilot_call", return_value=None):
            result = analyze_staleness(
                temp_ecosystem / "apps" / "community.json",
                ecosystem_context={"total_apps": 2, "frame": 10}
            )
        assert result["strategy"] == "skip"
        assert result["stale"] is False


# ── Routing Tests ──

class TestRouting:
    """The engine should route to existing scripts or LLM rewrite."""

    def test_known_file_routes_to_script(self, temp_ecosystem):
        from data_molt import route_strategy
        strategy = route_strategy(
            temp_ecosystem / "apps" / "community.json",
            {"stale": True, "strategy": "regenerate"}
        )
        assert strategy["method"] == "script"
        assert "generate_community" in strategy["script"]

    def test_known_file_routes_broadcast(self, temp_ecosystem):
        from data_molt import route_strategy
        strategy = route_strategy(
            temp_ecosystem / "apps" / "broadcasts" / "feed.json",
            {"stale": True, "strategy": "regenerate"}
        )
        assert strategy["method"] == "script"
        assert "generate_broadcast" in strategy["script"]

    def test_unknown_file_routes_to_llm(self, temp_ecosystem):
        from data_molt import route_strategy
        strategy = route_strategy(
            temp_ecosystem / "apps" / "leaderboard.json",
            {"stale": True, "strategy": "molt"}
        )
        assert strategy["method"] == "llm"

    def test_skip_strategy_routes_to_none(self, temp_ecosystem):
        from data_molt import route_strategy
        strategy = route_strategy(
            temp_ecosystem / "apps" / "rankings.json",
            {"stale": False, "strategy": "skip"}
        )
        assert strategy["method"] == "skip"

    def test_manifest_is_never_directly_molted(self, temp_ecosystem):
        """manifest.json is source of truth — it should not be overwritten by data molt."""
        from data_molt import route_strategy
        strategy = route_strategy(
            temp_ecosystem / "apps" / "manifest.json",
            {"stale": True, "strategy": "regenerate"}
        )
        assert strategy["method"] == "skip"


# ── Validation Tests ──

class TestValidation:
    """Output validation ensures schema is preserved and content is fresh."""

    def test_json_schema_preserved(self, temp_ecosystem):
        from data_molt import validate_data_output
        original = {"meta": {"version": "1.0"}, "items": [1, 2, 3]}
        refreshed = {"meta": {"version": "1.0"}, "items": [4, 5, 6, 7]}
        result = validate_data_output(original, refreshed)
        assert result["valid"] is True

    def test_rejects_wrong_top_level_keys(self, temp_ecosystem):
        from data_molt import validate_data_output
        original = {"meta": {}, "episodes": []}
        refreshed = {"completely": "different", "schema": True}
        result = validate_data_output(original, refreshed)
        assert result["valid"] is False
        assert "schema" in result["reason"].lower() or "key" in result["reason"].lower()

    def test_rejects_empty_output(self, temp_ecosystem):
        from data_molt import validate_data_output
        original = {"meta": {}, "data": [1, 2, 3]}
        result = validate_data_output(original, {})
        assert result["valid"] is False

    def test_rejects_drastically_smaller(self, temp_ecosystem):
        from data_molt import validate_data_output
        original = {"data": list(range(100))}
        refreshed = {"data": [1]}
        result = validate_data_output(original, refreshed)
        assert result["valid"] is False

    def test_accepts_larger_output(self, temp_ecosystem):
        """Refreshed data can be larger (more apps covered)."""
        from data_molt import validate_data_output
        original = {"data": [1, 2]}
        refreshed = {"data": [1, 2, 3, 4, 5]}
        result = validate_data_output(original, refreshed)
        assert result["valid"] is True


# ── Archive Tests ──

class TestArchive:
    """Data files should be archived before overwriting."""

    def test_archives_before_overwrite(self, temp_ecosystem):
        from data_molt import archive_data_file
        src = temp_ecosystem / "apps" / "community.json"
        archive_dir = temp_ecosystem / "apps" / "archive" / "data"
        result = archive_data_file(src, archive_dir, generation=1)
        assert result.exists()
        assert "community" in result.name
        assert "v1" in result.name

    def test_increments_generation(self, temp_ecosystem):
        from data_molt import archive_data_file
        src = temp_ecosystem / "apps" / "community.json"
        archive_dir = temp_ecosystem / "apps" / "archive" / "data"
        v1 = archive_data_file(src, archive_dir, generation=1)
        v2 = archive_data_file(src, archive_dir, generation=2)
        assert v1 != v2
        assert "v1" in v1.name
        assert "v2" in v2.name


# ── Generation Tracking Tests ──

class TestGenerationTracking:
    """Track data molt generations in state file."""

    def test_tracks_molt_in_state(self, temp_ecosystem):
        from data_molt import track_data_molt
        state_file = temp_ecosystem / "apps" / "data-molt-state.json"
        track_data_molt(state_file, "community.json", generation=1,
                        strategy="regenerate", issues=["stale comments"])
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "community.json" in state["files"]
        assert state["files"]["community.json"]["generation"] == 1

    def test_increments_existing_generation(self, temp_ecosystem):
        from data_molt import track_data_molt
        state_file = temp_ecosystem / "apps" / "data-molt-state.json"
        track_data_molt(state_file, "community.json", generation=1,
                        strategy="regenerate", issues=["stale"])
        track_data_molt(state_file, "community.json", generation=2,
                        strategy="regenerate", issues=["still stale"])
        state = json.loads(state_file.read_text())
        assert state["files"]["community.json"]["generation"] == 2
        assert len(state["files"]["community.json"]["history"]) == 2


# ── Integration Tests ──

class TestIntegration:
    """End-to-end flow with mocked LLM."""

    def test_full_pipeline_skip_fresh(self, temp_ecosystem):
        """Fresh files should be skipped entirely."""
        from data_molt import molt_data_file
        analysis = {"stale": False, "score": 95, "strategy": "skip", "issues": []}
        with patch("data_molt.analyze_staleness", return_value=analysis):
            result = molt_data_file(
                temp_ecosystem / "apps" / "rankings.json",
                temp_ecosystem / "apps",
                ecosystem_context={"total_apps": 2, "frame": 10}
            )
        assert result["action"] == "skipped"

    def test_full_pipeline_llm_molt_unknown(self, temp_ecosystem):
        """Unknown files should be molted via LLM inline rewrite."""
        from data_molt import molt_data_file
        analysis = {"stale": True, "score": 20, "strategy": "molt",
                    "issues": ["Only 1 entry, outdated"]}
        refreshed = json.dumps({
            "format": "leaderboard-v1",
            "entries": [
                {"player": "NeonWolf", "score": 1500},
                {"player": "PixelStorm", "score": 1200},
            ]
        })
        with patch("data_molt.analyze_staleness", return_value=analysis), \
             patch("data_molt.copilot_call", return_value=refreshed):
            result = molt_data_file(
                temp_ecosystem / "apps" / "leaderboard.json",
                temp_ecosystem / "apps",
                ecosystem_context={"total_apps": 2, "frame": 10}
            )
        assert result["action"] == "molted"
        # Verify the file was updated
        updated = json.loads((temp_ecosystem / "apps" / "leaderboard.json").read_text())
        assert len(updated["entries"]) == 2
