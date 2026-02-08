#!/usr/bin/env python3
"""Tests for RappterZoo content graph compiler."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from compile_graph import (
    UnionFind,
    build_nodes,
    detect_edges,
    build_components,
    compile_graph,
    deep_copy_component,
    merge_graphs,
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
                    "title": "Sky Realms",
                    "file": "sky-realms.html",
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
}

MOCK_RANKINGS = {
    "rankings": [
        {"file": "sky-realms.html", "score": 94, "grade": "S", "category": "games_puzzles",
         "category_folder": "games-puzzles", "path": "apps/games-puzzles/sky-realms.html",
         "dimensions": {"playability": {"score": 23, "max": 25}}},
        {"file": "puzzle-quest.html", "score": 55, "grade": "C", "category": "games_puzzles",
         "category_folder": "games-puzzles", "path": "apps/games-puzzles/puzzle-quest.html",
         "dimensions": {"playability": {"score": 12, "max": 25}}},
        {"file": "fractal-explorer.html", "score": 65, "grade": "B", "category": "generative_art",
         "category_folder": "generative-art", "path": "apps/generative-art/fractal-explorer.html",
         "dimensions": {"playability": {"score": 8, "max": 25}}},
        {"file": "synth-pad.html", "score": 48, "grade": "C", "category": "audio_music",
         "category_folder": "audio-music", "path": "apps/audio-music/synth-pad.html",
         "dimensions": {"playability": {"score": 6, "max": 25}}},
        {"file": "broken-demo.html", "score": 12, "grade": "F", "category": "games_puzzles",
         "category_folder": "games-puzzles", "path": "apps/games-puzzles/broken-demo.html",
         "dimensions": {"playability": {"score": 1, "max": 25}}},
    ],
}

MOCK_COMMUNITY = {
    "meta": {"totalPlayers": 5, "totalComments": 6, "totalRatings": 10},
    "players": [
        {"id": "p001", "username": "NeonWolf", "color": "#00e5ff", "favoriteCategory": "games_puzzles"},
        {"id": "p002", "username": "CyberHawk", "color": "#ff6e40", "favoriteCategory": "games_puzzles"},
        {"id": "p003", "username": "PixelMage", "color": "#ff4500", "favoriteCategory": "generative_art"},
        {"id": "p004", "username": "ShadowFox", "color": "#9c27b0", "favoriteCategory": "audio_music"},
        {"id": "p005", "username": "VoidPilot", "color": "#64ffda", "favoriteCategory": "generative_art"},
    ],
    "comments": {
        "sky-realms": [
            {
                "id": "c001", "author": "NeonWolf", "authorId": "p001",
                "text": "Best game in the arcade, reminds me of Puzzle Quest",
                "upvotes": 42, "downvotes": 0, "parentId": None,
                "children": [
                    {"id": "c002", "author": "CyberHawk", "authorId": "p002",
                     "text": "Agreed, the flight mechanics are incredible",
                     "upvotes": 18, "downvotes": 0, "parentId": "c001", "children": []},
                ],
            },
        ],
        "puzzle-quest": [
            {
                "id": "c003", "author": "NeonWolf", "authorId": "p001",
                "text": "The later puzzles are devious — check out Fractal Explorer too",
                "upvotes": 15, "downvotes": 1, "parentId": None,
                "children": [],
            },
        ],
        "fractal-explorer": [
            {
                "id": "c004", "author": "PixelMage", "authorId": "p003",
                "text": "Zoomed in for 20 minutes and the detail never stopped",
                "upvotes": 22, "downvotes": 0, "parentId": None,
                "children": [],
            },
        ],
        "synth-pad": [
            {
                "id": "c005", "author": "ShadowFox", "authorId": "p004",
                "text": "Made an actual beat in 5 minutes",
                "upvotes": 10, "downvotes": 0, "parentId": None,
                "children": [],
            },
        ],
    },
    "ratings": {
        "sky-realms": [
            {"playerId": "p001", "username": "NeonWolf", "stars": 5},
            {"playerId": "p002", "username": "CyberHawk", "stars": 5},
            {"playerId": "p003", "username": "PixelMage", "stars": 4},
        ],
        "puzzle-quest": [
            {"playerId": "p001", "username": "NeonWolf", "stars": 4},
            {"playerId": "p004", "username": "ShadowFox", "stars": 3},
        ],
        "fractal-explorer": [
            {"playerId": "p003", "username": "PixelMage", "stars": 5},
            {"playerId": "p005", "username": "VoidPilot", "stars": 4},
        ],
        "synth-pad": [
            {"playerId": "p004", "username": "ShadowFox", "stars": 4},
        ],
        "broken-demo": [
            {"playerId": "p002", "username": "CyberHawk", "stars": 1},
        ],
    },
}

MOCK_LORE = {
    "reviewed_apps": {
        "sky-realms.html": {"title": "Sky Realms", "episodes": [1], "scores": [94], "grades": ["S"]},
        "broken-demo.html": {"title": "Broken Demo", "episodes": [1], "scores": [12], "grades": ["F"]},
    },
    "category_counts": {"games_puzzles": 2},
    "total_reviewed": 2,
    "episode_summaries": [{"ep": 1, "title": "Ep 1", "apps_reviewed": ["sky-realms.html", "broken-demo.html"]}],
}


# ── UnionFind Tests ──

class TestUnionFind:
    def test_initial_state(self):
        uf = UnionFind()
        assert uf.find("a") == "a"
        assert uf.find("b") == "b"

    def test_union(self):
        uf = UnionFind()
        uf.union("a", "b")
        assert uf.find("a") == uf.find("b")

    def test_transitive_union(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        assert uf.find("a") == uf.find("c")

    def test_separate_components(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("c", "d")
        assert uf.find("a") != uf.find("c")

    def test_components(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        uf.union("d", "e")
        comps = uf.components()
        assert len(comps) == 2
        # Find the component containing 'a'
        comp_a = next(c for c in comps if "a" in c)
        assert set(comp_a) == {"a", "b", "c"}
        comp_d = next(c for c in comps if "d" in c)
        assert set(comp_d) == {"d", "e"}

    def test_single_node(self):
        uf = UnionFind()
        uf.add("alone")
        comps = uf.components()
        assert any("alone" in c for c in comps)

    def test_merge_existing_components(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("c", "d")
        # Now merge the two components
        uf.union("b", "c")
        assert uf.find("a") == uf.find("d")
        comps = uf.components()
        comp = next(c for c in comps if "a" in c)
        assert set(comp) == {"a", "b", "c", "d"}


# ── Node Building Tests ──

class TestBuildNodes:
    def test_creates_node_per_app(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        assert len(nodes) == 5

    def test_node_has_manifest_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["sky-realms.html"]
        assert node["manifest"]["title"] == "Sky Realms"
        assert node["manifest"]["category"] == "games_puzzles"
        assert node["manifest"]["folder"] == "games-puzzles"
        assert "3d" in node["manifest"]["tags"]

    def test_node_has_ranking_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["sky-realms.html"]
        assert node["ranking"]["score"] == 94
        assert node["ranking"]["grade"] == "S"

    def test_node_has_community_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["sky-realms.html"]
        assert len(node["community"]["comments"]) == 1
        assert node["community"]["comments"][0]["author"] == "NeonWolf"
        assert len(node["community"]["ratings"]) == 3
        assert node["community"]["avg_rating"] == pytest.approx(4.67, abs=0.1)

    def test_node_has_lore_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["sky-realms.html"]
        assert node["lore"]["episodes"] == [1]
        assert node["lore"]["scores"] == [94]

    def test_node_without_lore(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["puzzle-quest.html"]
        assert node["lore"] is None

    def test_node_has_url(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        node = nodes["sky-realms.html"]
        assert node["manifest"]["url"].endswith("/apps/games-puzzles/sky-realms.html")

    def test_handles_missing_rankings(self):
        nodes = build_nodes(MOCK_MANIFEST, None, MOCK_COMMUNITY, None)
        node = nodes["sky-realms.html"]
        assert node["ranking"] is None

    def test_handles_missing_community(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, None, None)
        node = nodes["sky-realms.html"]
        assert node["community"]["comments"] == []
        assert node["community"]["ratings"] == []


# ── Edge Detection Tests ──

class TestDetectEdges:
    def test_shared_player_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        # NeonWolf rated both sky-realms and puzzle-quest → shared_player edge
        shared_player = [e for e in edges if e["type"] == "shared_player"]
        pairs = [(e["source"], e["target"]) for e in shared_player]
        # NeonWolf connects sky-realms and puzzle-quest
        has_neon = any(
            ("sky-realms.html" in (s, t) and "puzzle-quest.html" in (s, t))
            for s, t in pairs
        )
        assert has_neon, f"Expected NeonWolf edge between sky-realms and puzzle-quest, got: {pairs}"

    def test_comment_mention_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        # NeonWolf's comment on sky-realms mentions "Puzzle Quest"
        mentions = [e for e in edges if e["type"] == "comment_mention"]
        pairs = [(e["source"], e["target"]) for e in mentions]
        has_mention = any(
            ("sky-realms.html" in (s, t) and "puzzle-quest.html" in (s, t))
            for s, t in pairs
        )
        assert has_mention, f"Expected mention edge sky-realms→puzzle-quest, got: {pairs}"

    def test_comment_mention_fractal(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        mentions = [e for e in edges if e["type"] == "comment_mention"]
        pairs = [(e["source"], e["target"]) for e in mentions]
        # NeonWolf on puzzle-quest mentions "Fractal Explorer"
        has_mention = any(
            ("puzzle-quest.html" in (s, t) and "fractal-explorer.html" in (s, t))
            for s, t in pairs
        )
        assert has_mention, f"Expected mention edge puzzle-quest→fractal-explorer, got: {pairs}"

    def test_shared_tag_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        tag_edges = [e for e in edges if e["type"] == "shared_tags"]
        # Requires 3+ shared tags. No pair in mock data shares 3+ tags.
        # sky-realms [3d, game, canvas] and puzzle-quest [puzzle, game] share only "game"
        # sky-realms and fractal [fractal, canvas, animation] share only "canvas"
        assert len(tag_edges) == 0

    def test_no_same_category_edges(self):
        """same_category edges are intentionally disabled (too noisy)."""
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        cat_edges = [e for e in edges if e["type"] == "same_category"]
        assert len(cat_edges) == 0

    def test_edge_has_weight(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        for e in edges:
            assert "weight" in e
            assert e["weight"] > 0

    def test_no_self_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        for e in edges:
            assert e["source"] != e["target"], f"Self-edge found: {e}"


# ── Component Building Tests ──

class TestBuildComponents:
    def test_builds_connected_components(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        assert len(components) >= 1

    def test_connected_nodes_same_component(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        # sky-realms and puzzle-quest are connected (shared player, comment mention, same category)
        sky_comp = next(c for c in components if "sky-realms.html" in c["nodes"])
        assert "puzzle-quest.html" in sky_comp["nodes"]

    def test_component_has_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        for comp in components:
            if len(comp["nodes"]) > 1:
                assert len(comp["edges"]) > 0

    def test_component_has_id(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        for comp in components:
            assert "id" in comp
            assert comp["id"].startswith("graph-")


# ── Deep Copy Tests ──

class TestDeepCopyComponent:
    def test_deep_copies_node_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        comp = next(c for c in components if "sky-realms.html" in c["nodes"])
        result = deep_copy_component(comp, nodes)
        # Verify it's a deep copy — modifying result shouldn't affect original
        result["nodes"]["sky-realms.html"]["manifest"]["title"] = "MODIFIED"
        assert nodes["sky-realms.html"]["manifest"]["title"] == "Sky Realms"

    def test_includes_all_node_data(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        comp = next(c for c in components if "sky-realms.html" in c["nodes"])
        result = deep_copy_component(comp, nodes)
        sky = result["nodes"]["sky-realms.html"]
        assert "manifest" in sky
        assert "ranking" in sky
        assert "community" in sky
        assert "lore" in sky

    def test_includes_shared_players(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        comp = next(c for c in components if "sky-realms.html" in c["nodes"])
        result = deep_copy_component(comp, nodes)
        assert "players" in result
        # NeonWolf should be in the shared players
        player_names = [p["username"] for p in result["players"]]
        assert "NeonWolf" in player_names


# ── Graph Merge Tests ──

class TestMergeGraphs:
    def test_merging_creates_single_graph(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        if len(components) >= 2:
            merged = merge_graphs(components[0], components[1], nodes)
            all_nodes = set(components[0]["nodes"]) | set(components[1]["nodes"])
            assert set(merged["nodes"]) == all_nodes

    def test_merge_preserves_edges(self):
        nodes = build_nodes(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        edges = detect_edges(nodes, MOCK_COMMUNITY)
        components = build_components(nodes, edges)
        if len(components) >= 2:
            total_edges = len(components[0]["edges"]) + len(components[1]["edges"])
            merged = merge_graphs(components[0], components[1], nodes)
            assert len(merged["edges"]) >= total_edges


# ── Full Compile Tests ──

class TestCompileGraph:
    def test_compile_produces_valid_output(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        assert "meta" in result
        assert "graphs" in result
        assert "nodes" in result

    def test_compile_meta(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        assert result["meta"]["total_nodes"] == 5
        assert result["meta"]["total_graphs"] >= 1
        assert "generated" in result["meta"]

    def test_all_nodes_in_output(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        assert len(result["nodes"]) == 5

    def test_every_node_in_a_graph(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        all_graph_nodes = set()
        for g in result["graphs"]:
            all_graph_nodes.update(g["nodes"].keys())
        assert all_graph_nodes == set(result["nodes"].keys())

    def test_graphs_are_deep_copies(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        # Modify a graph node — shouldn't affect the slim top-level nodes
        g = result["graphs"][0]
        first_key = list(g["nodes"].keys())[0]
        original_title = result["nodes"][first_key]["manifest"]["title"]
        g["nodes"][first_key]["manifest"]["title"] = "HACKED"
        assert result["nodes"][first_key]["manifest"]["title"] == original_title

    def test_slim_nodes_have_graph_id(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        for filename, node in result["nodes"].items():
            assert "graph" in node
            assert node["graph"] is not None
            assert node["graph"].startswith("graph-")

    def test_output_is_json_serializable(self):
        result = compile_graph(MOCK_MANIFEST, MOCK_RANKINGS, MOCK_COMMUNITY, MOCK_LORE)
        serialized = json.dumps(result)
        assert len(serialized) > 0
        roundtrip = json.loads(serialized)
        assert roundtrip["meta"]["total_nodes"] == 5
