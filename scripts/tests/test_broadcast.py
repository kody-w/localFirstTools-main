#!/usr/bin/env python3
"""Tests for RappterZooNation broadcast generation."""

import json
import random
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_broadcast import (
    build_app_index,
    select_episode_apps,
    generate_review_dialogue,
    generate_roast_dialogue,
    generate_episode,
    estimate_duration,
    get_app_stem,
    HOSTS,
    RAPPTR_INTROS,
    ZOOKEEPER_INTROS,
    RAPPTR_TAG_REACTIONS,
    ZOOKEEPER_TAG_REACTIONS,
)


# ── Fixtures ──

MOCK_MANIFEST = {
    "categories": {
        "games_puzzles": {
            "title": "Games & Puzzles",
            "folder": "games-puzzles",
            "color": "#ff0000",
            "count": 3,
            "apps": [
                {
                    "title": "Sky Realms: Aether Wing",
                    "file": "sky-realms-game.html",
                    "description": "Epic 3D flight game",
                    "tags": ["3d", "game", "canvas"],
                    "complexity": "advanced",
                    "type": "game",
                    "featured": True,
                    "created": "2026-01-15",
                },
                {
                    "title": "Puzzle Quest",
                    "file": "puzzle-quest.html",
                    "description": "Brain-bending puzzle game",
                    "tags": ["puzzle", "game"],
                    "complexity": "intermediate",
                    "type": "game",
                    "featured": False,
                    "created": "2026-01-20",
                },
                {
                    "title": "Broken Demo",
                    "file": "broken-demo.html",
                    "description": "A barely working demo",
                    "tags": ["game"],
                    "complexity": "simple",
                    "type": "game",
                    "featured": False,
                    "created": "2026-01-10",
                },
            ],
        },
        "generative_art": {
            "title": "Generative Art",
            "folder": "generative-art",
            "color": "#00ff00",
            "count": 1,
            "apps": [
                {
                    "title": "Fractal Explorer",
                    "file": "fractal-explorer.html",
                    "description": "Dive into infinite fractal patterns",
                    "tags": ["fractal", "canvas", "animation"],
                    "complexity": "advanced",
                    "type": "visual",
                    "featured": True,
                    "created": "2026-01-18",
                },
            ],
        },
        "audio_music": {
            "title": "Audio & Music",
            "folder": "audio-music",
            "color": "#0000ff",
            "count": 1,
            "apps": [
                {
                    "title": "Synth Pad",
                    "file": "synth-pad.html",
                    "description": "Web Audio synthesizer",
                    "tags": ["synth", "audio", "music"],
                    "complexity": "intermediate",
                    "type": "audio",
                    "featured": False,
                    "created": "2026-01-22",
                },
            ],
        },
    },
    "meta": {"version": "1.0", "lastUpdated": "2026-02-07"},
}

MOCK_RANKINGS = {
    "summary": {"avg_score": 55.0, "median_score": 50},
    "rankings": [
        {
            "file": "sky-realms-game.html",
            "title": "Sky Realms: Aether Wing",
            "score": 94,
            "grade": "S",
            "category": "games_puzzles",
            "category_folder": "games-puzzles",
            "path": "apps/games-puzzles/sky-realms-game.html",
            "dimensions": {"playability": {"score": 23, "max": 25}},
        },
        {
            "file": "fractal-explorer.html",
            "title": "Fractal Explorer",
            "score": 65,
            "grade": "B",
            "category": "generative_art",
            "category_folder": "generative-art",
            "path": "apps/generative-art/fractal-explorer.html",
            "dimensions": {"playability": {"score": 8, "max": 25}},
        },
        {
            "file": "puzzle-quest.html",
            "title": "Puzzle Quest",
            "score": 55,
            "grade": "C",
            "category": "games_puzzles",
            "category_folder": "games-puzzles",
            "path": "apps/games-puzzles/puzzle-quest.html",
            "dimensions": {"playability": {"score": 12, "max": 25}},
        },
        {
            "file": "synth-pad.html",
            "title": "Synth Pad",
            "score": 48,
            "grade": "C",
            "category": "audio_music",
            "category_folder": "audio-music",
            "path": "apps/audio-music/synth-pad.html",
            "dimensions": {"playability": {"score": 6, "max": 25}},
        },
        {
            "file": "broken-demo.html",
            "title": "Broken Demo",
            "score": 12,
            "grade": "F",
            "category": "games_puzzles",
            "category_folder": "games-puzzles",
            "path": "apps/games-puzzles/broken-demo.html",
            "dimensions": {"playability": {"score": 1, "max": 25}},
        },
    ],
}

MOCK_COMMUNITY = {
    "meta": {"totalPlayers": 10, "totalComments": 5, "totalRatings": 20},
    "players": [],
    "comments": {
        "sky-realms-game": [
            {
                "id": "c001",
                "author": "NeonWolf",
                "authorId": "p001",
                "authorColor": "#00e5ff",
                "text": "Best 3D game in the arcade, no contest",
                "upvotes": 42,
                "downvotes": 0,
                "parentId": None,
                "children": [
                    {
                        "id": "c002",
                        "author": "CyberHawk",
                        "authorId": "p002",
                        "authorColor": "#ff6e40",
                        "text": "Agreed, the flight mechanics are incredible",
                        "upvotes": 18,
                        "downvotes": 0,
                        "parentId": "c001",
                        "children": [],
                    }
                ],
            }
        ],
        "puzzle-quest": [
            {
                "id": "c003",
                "author": "PixelMage",
                "authorId": "p003",
                "authorColor": "#ff4500",
                "text": "The later puzzles are devious",
                "upvotes": 15,
                "downvotes": 1,
                "parentId": None,
                "children": [],
            }
        ],
    },
    "ratings": {
        "sky-realms-game": [
            {"playerId": "p001", "username": "NeonWolf", "stars": 5},
            {"playerId": "p002", "username": "CyberHawk", "stars": 5},
            {"playerId": "p003", "username": "PixelMage", "stars": 4},
        ],
        "puzzle-quest": [
            {"playerId": "p001", "username": "NeonWolf", "stars": 3},
            {"playerId": "p004", "username": "ShadowFox", "stars": 4},
        ],
        "fractal-explorer": [
            {"playerId": "p005", "username": "VoidPilot", "stars": 4},
        ],
    },
}


# ── Tests ──

class TestBuildAppIndex:
    def test_indexes_all_apps(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        assert len(index) == 5

    def test_merges_scores(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        assert index["sky-realms-game.html"]["score"] == 94
        assert index["sky-realms-game.html"]["grade"] == "S"
        assert index["sky-realms-game.html"]["playability"] == 23

    def test_merges_community(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        comm = index["sky-realms-game.html"]["community"]
        assert comm["totalRatings"] == 3
        assert comm["avgRating"] == pytest.approx(4.7, abs=0.1)
        assert comm["totalComments"] == 2
        assert len(comm["topComments"]) == 2
        assert comm["topComments"][0]["author"] == "NeonWolf"

    def test_builds_urls(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        assert app["url"].endswith("/apps/games-puzzles/sky-realms-game.html")
        assert app["path"] == "apps/games-puzzles/sky-realms-game.html"

    def test_handles_missing_rankings(self):
        index = build_app_index(MOCK_MANIFEST, None, MOCK_COMMUNITY)
        assert index["sky-realms-game.html"]["score"] == 0

    def test_handles_missing_community(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, None)
        comm = index["sky-realms-game.html"]["community"]
        assert comm["totalRatings"] == 0

    def test_category_and_folder(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        assert index["sky-realms-game.html"]["category"] == "games_puzzles"
        assert index["sky-realms-game.html"]["folder"] == "games-puzzles"
        assert index["fractal-explorer.html"]["category"] == "generative_art"


class TestSelectEpisodeApps:
    def test_selects_3_to_5_apps(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        apps = select_episode_apps(index, rng, 1)
        assert 3 <= len(apps) <= 5

    def test_no_duplicates(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        apps = select_episode_apps(index, rng, 1)
        files = [a["file"] for a in apps]
        assert len(files) == len(set(files))

    def test_includes_top_scorer(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        apps = select_episode_apps(index, rng, 1)
        scores = [a["score"] for a in apps]
        assert 94 in scores  # Sky Realms

    def test_includes_low_scorer(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        apps = select_episode_apps(index, rng, 1)
        # Last app should be lowest
        assert apps[-1]["score"] <= apps[0]["score"]

    def test_deterministic_with_seed(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        apps1 = select_episode_apps(index, random.Random(42), 1)
        apps2 = select_episode_apps(index, random.Random(42), 1)
        assert [a["file"] for a in apps1] == [a["file"] for a in apps2]


class TestDialogueGeneration:
    def test_review_has_dialogue(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        rng = random.Random(42)
        dialogue = generate_review_dialogue(app, rng)
        assert len(dialogue) >= 4

    def test_both_hosts_speak(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        rng = random.Random(42)
        dialogue = generate_review_dialogue(app, rng)
        hosts = {d["host"] for d in dialogue}
        assert "Rapptr" in hosts
        assert "ZooKeeper" in hosts

    def test_rapptr_opens(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        rng = random.Random(42)
        dialogue = generate_review_dialogue(app, rng)
        assert dialogue[0]["host"] == "Rapptr"

    def test_references_app_title(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        rng = random.Random(42)
        dialogue = generate_review_dialogue(app, rng)
        all_text = " ".join(d["text"] for d in dialogue)
        assert "Sky Realms" in all_text or "94" in all_text

    def test_references_community(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["sky-realms-game.html"]
        rng = random.Random(42)
        dialogue = generate_review_dialogue(app, rng)
        all_text = " ".join(d["text"] for d in dialogue)
        assert "NeonWolf" in all_text or "4.7" in all_text or "3 rating" in all_text

    def test_roast_dialogue(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        app = index["broken-demo.html"]
        rng = random.Random(42)
        dialogue = generate_roast_dialogue(app, rng)
        assert len(dialogue) >= 3
        all_text = " ".join(d["text"] for d in dialogue)
        assert "12" in all_text  # score


class TestEpisodeGeneration:
    def test_generates_complete_episode(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        assert ep is not None
        assert ep["id"] == "ep-001"
        assert ep["number"] == 1
        assert ep["frame"] == 1
        assert "title" in ep
        assert "segments" in ep
        assert "duration" in ep

    def test_has_intro_and_outro(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        types = [s["type"] for s in ep["segments"]]
        assert "intro" in types
        assert "outro" in types

    def test_has_reviews(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        reviews = [s for s in ep["segments"] if s["type"] == "review"]
        assert len(reviews) >= 1

    def test_review_has_app_data(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        review = next(s for s in ep["segments"] if s["type"] == "review")
        app = review["app"]
        assert "title" in app
        assert "file" in app
        assert "url" in app
        assert "score" in app
        assert "grade" in app
        assert "community" in app

    def test_has_roast_segment(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        roasts = [s for s in ep["segments"] if s["type"] == "roast"]
        assert len(roasts) >= 1

    def test_episode_duration_format(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        rng = random.Random(42)
        ep = generate_episode(index, rng, 1, 1, MOCK_RANKINGS["summary"])
        assert ":" in ep["duration"]
        parts = ep["duration"].split(":")
        assert len(parts) == 2

    def test_deterministic(self):
        index = build_app_index(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY)
        ep1 = generate_episode(index, random.Random(42), 1, 1, MOCK_RANKINGS["summary"])
        ep2 = generate_episode(index, random.Random(42), 1, 1, MOCK_RANKINGS["summary"])
        assert ep1["title"] == ep2["title"]
        assert len(ep1["segments"]) == len(ep2["segments"])


class TestEstimateDuration:
    def test_empty_segments(self):
        assert estimate_duration([]) == "0:00"

    def test_with_dialogue(self):
        segments = [
            {"dialogue": [{"text": " ".join(["word"] * 150)}]},  # 150 words = ~1 min
        ]
        dur = estimate_duration(segments)
        m, s = dur.split(":")
        assert int(m) >= 1

    def test_solo_text(self):
        segments = [
            {"text": " ".join(["word"] * 75)},  # 75 words = ~30 sec
        ]
        dur = estimate_duration(segments)
        assert dur == "0:30"


class TestGetAppStem:
    def test_strips_html(self):
        assert get_app_stem("sky-realms-game.html") == "sky-realms-game"

    def test_handles_spaces(self):
        assert get_app_stem("star wars galaxies.html") == "star wars galaxies"


class TestHostDefinitions:
    def test_both_hosts_defined(self):
        assert "Rapptr" in HOSTS
        assert "ZooKeeper" in HOSTS

    def test_hosts_have_colors(self):
        assert HOSTS["Rapptr"]["color"] == "#00e5ff"
        assert HOSTS["ZooKeeper"]["color"] == "#ff6e40"

    def test_rapptr_has_tag_reactions(self):
        assert len(RAPPTR_TAG_REACTIONS) > 5
        for tag, reactions in RAPPTR_TAG_REACTIONS.items():
            assert len(reactions) >= 2, f"Rapptr needs more reactions for '{tag}'"

    def test_zookeeper_has_tag_reactions(self):
        assert len(ZOOKEEPER_TAG_REACTIONS) > 5
        for tag, reactions in ZOOKEEPER_TAG_REACTIONS.items():
            assert len(reactions) >= 2, f"ZooKeeper needs more reactions for '{tag}'"

    def test_tag_parity(self):
        """Both hosts should react to the same tags."""
        rapptr_tags = set(RAPPTR_TAG_REACTIONS.keys())
        zoo_tags = set(ZOOKEEPER_TAG_REACTIONS.keys())
        assert rapptr_tags == zoo_tags


class TestVocabularyPools:
    def test_rapptr_intros_use_title(self):
        for template in RAPPTR_INTROS:
            assert "{title}" in template

    def test_zookeeper_intros_use_score(self):
        for template in ZOOKEEPER_INTROS:
            assert "{score}" in template or "{title}" in template
