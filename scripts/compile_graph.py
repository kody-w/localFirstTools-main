#!/usr/bin/env python3
"""RappterZoo Content Graph Compiler.

Scans all posts and builds a graph of content relationships. Each post becomes
a node with deep-copied manifest, ranking, community, and lore data. Edges
connect posts that share players, reference each other in comments, share
categories, or have portal/parent links. Connected components form graphs —
self-contained objects that carry everything related to the posts within them.

Usage:
    python3 scripts/compile_graph.py                 # Compile content-graph.json
    python3 scripts/compile_graph.py --verbose        # Show details
    python3 scripts/compile_graph.py --push           # Compile + commit + push
    python3 scripts/compile_graph.py --stats          # Print graph statistics only

Output: apps/content-graph.json
"""

import copy
import json
import sys
import subprocess
from collections import defaultdict
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
RANKINGS = APPS_DIR / "rankings.json"
COMMUNITY = APPS_DIR / "community.json"
LORE_FILE = APPS_DIR / "broadcasts" / "lore.json"
OUTPUT = APPS_DIR / "content-graph.json"

SITE_BASE = "https://kody-w.github.io/localFirstTools-main"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

# Edge weights — higher = stronger connection
EDGE_WEIGHTS = {
    "comment_mention": 5,     # Comment explicitly names another app
    "shared_player": 2,       # Same player engaged with both apps
    "same_category": 1,       # Same category folder
    "shared_tags": 3,         # 2+ shared tags
    "portal_link": 10,        # rappterzoo:portals meta tag (strongest)
    "parent_link": 8,         # rappterzoo:parent meta tag
    "shared_lore": 4,         # Both reviewed in same podcast episode
}

# Minimum shared tags to create an edge
MIN_SHARED_TAGS = 3

# Max shared-player edges per player to avoid combinatorial explosion
MAX_PLAYER_EDGES = 10


def log(msg):
    if VERBOSE:
        print(f"  [graph] {msg}")


def load_json(path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def stem(filename):
    """Get stem key (filename without .html)."""
    return Path(filename).stem


# ── Union-Find ──────────────────────────────────────────────────

class UnionFind:
    """Disjoint set for building connected components."""

    def __init__(self):
        self.parent = {}
        self.rank = {}

    def add(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x):
        self.add(x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, x, y):
        self.add(x)
        self.add(y)
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        # union by rank
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def components(self):
        """Return list of sets, each set is a connected component."""
        groups = defaultdict(set)
        for x in self.parent:
            groups[self.find(x)].add(x)
        return list(groups.values())


# ── Node Building ──────────────────────────────────────────────

def build_nodes(manifest, rankings, community, lore):
    """Build a node dict keyed by filename with all post data."""
    nodes = {}

    # Build title→file index for cross-reference detection
    title_to_file = {}

    # Index rankings by file
    ranking_index = {}
    if rankings:
        for entry in rankings.get("rankings", []):
            ranking_index[entry["file"]] = entry

    # Index community by stem
    comments_index = {}
    ratings_index = {}
    if community:
        comments_index = community.get("comments", {})
        ratings_index = community.get("ratings", {})

    # Index lore by file
    lore_index = {}
    if lore:
        lore_index = lore.get("reviewed_apps", {})

    # Build nodes from manifest
    for cat_key, cat_data in manifest.get("categories", {}).items():
        folder = cat_data.get("folder", cat_key.replace("_", "-"))
        for app in cat_data.get("apps", []):
            filename = app["file"]
            app_stem = stem(filename)
            title = app.get("title", filename)
            title_to_file[title.lower()] = filename

            # Community data
            app_comments = copy.deepcopy(comments_index.get(app_stem, []))
            app_ratings = copy.deepcopy(ratings_index.get(app_stem, []))
            stars = [r.get("stars", 3) for r in app_ratings]
            avg_rating = sum(stars) / len(stars) if stars else 0

            # Ranking data
            rank_data = ranking_index.get(filename)

            # Lore data
            app_lore = lore_index.get(filename)

            nodes[filename] = {
                "manifest": {
                    "title": title,
                    "file": filename,
                    "category": cat_key,
                    "folder": folder,
                    "category_title": cat_data.get("title", cat_key),
                    "description": app.get("description", ""),
                    "tags": app.get("tags", []),
                    "complexity": app.get("complexity", "intermediate"),
                    "type": app.get("type", "interactive"),
                    "path": f"apps/{folder}/{filename}",
                    "url": f"{SITE_BASE}/apps/{folder}/{filename}",
                    "created": app.get("created", ""),
                },
                "ranking": {
                    "score": rank_data.get("score", 0),
                    "grade": rank_data.get("grade", "?"),
                    "playability": rank_data.get("dimensions", {}).get("playability", {}).get("score", 0),
                    "dimensions": rank_data.get("dimensions", {}),
                } if rank_data else None,
                "community": {
                    "comments": app_comments,
                    "ratings": app_ratings,
                    "avg_rating": round(avg_rating, 2),
                    "total_ratings": len(app_ratings),
                    "total_comments": _count_comments(app_comments),
                    "commenters": list({c.get("authorId", "") for c in _flatten_comments(app_comments)}),
                    "raters": [r.get("playerId", "") for r in app_ratings],
                },
                "lore": copy.deepcopy(app_lore) if app_lore else None,
            }

    # Store title index on module level for edge detection
    build_nodes._title_to_file = title_to_file

    return nodes


def _flatten_comments(comments):
    """Flatten nested comment tree into a flat list."""
    flat = []
    for c in comments:
        flat.append(c)
        flat.extend(_flatten_comments(c.get("children", [])))
    return flat


def _count_comments(comments):
    """Count total comments including children."""
    return len(_flatten_comments(comments))


# ── Edge Detection ──────────────────────────────────────────────

def detect_edges(nodes, community):
    """Detect all edges between nodes."""
    edges = []
    filenames = list(nodes.keys())
    title_to_file = getattr(build_nodes, '_title_to_file', {})

    # Build player→apps index for shared player detection
    player_apps = defaultdict(set)  # playerId → set of filenames
    for filename, node in nodes.items():
        for rater_id in node["community"].get("raters", []):
            if rater_id:
                player_apps[rater_id].add(filename)
        for commenter_id in node["community"].get("commenters", []):
            if commenter_id:
                player_apps[commenter_id].add(filename)

    seen_edges = set()

    def add_edge(src, tgt, etype, weight=None, data=None):
        if src == tgt:
            return
        key = (min(src, tgt), max(src, tgt), etype)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({
            "source": src,
            "target": tgt,
            "type": etype,
            "weight": weight or EDGE_WEIGHTS.get(etype, 1),
            "data": data or {},
        })

    # 1. Shared player edges (capped per player to avoid combinatorial explosion)
    for player_id, apps in player_apps.items():
        apps = sorted(apps)
        pairs = 0
        for i in range(len(apps)):
            for j in range(i + 1, len(apps)):
                if pairs >= MAX_PLAYER_EDGES:
                    break
                add_edge(apps[i], apps[j], "shared_player",
                         data={"player": player_id})
                pairs += 1
            if pairs >= MAX_PLAYER_EDGES:
                break

    # 2. Comment mention edges — scan comment text for other app titles
    for filename, node in nodes.items():
        all_comments = _flatten_comments(node["community"].get("comments", []))
        for comment in all_comments:
            text = comment.get("text", "").lower()
            for title, target_file in title_to_file.items():
                if target_file != filename and title in text and len(title) > 3:
                    add_edge(filename, target_file, "comment_mention",
                             data={"comment_id": comment.get("id", ""),
                                   "author": comment.get("author", "")})

    # 3. Same category edges — SKIPPED (too noisy, creates giant cliques)
    # Category membership is recorded in manifest data on each node.

    # 4. Shared tag edges (2+ shared tags required)
    for i in range(len(filenames)):
        tags_i = set(nodes[filenames[i]]["manifest"]["tags"])
        for j in range(i + 1, len(filenames)):
            tags_j = set(nodes[filenames[j]]["manifest"]["tags"])
            shared = tags_i & tags_j
            if len(shared) >= MIN_SHARED_TAGS:
                add_edge(filenames[i], filenames[j], "shared_tags",
                         data={"tags": list(shared)})

    # 5. Shared lore edges — apps reviewed in the same podcast episode
    if any(n["lore"] for n in nodes.values()):
        episode_apps = defaultdict(list)
        for filename, node in nodes.items():
            if node["lore"]:
                for ep in node["lore"].get("episodes", []):
                    episode_apps[ep].append(filename)
        for ep, apps in episode_apps.items():
            for i in range(len(apps)):
                for j in range(i + 1, len(apps)):
                    add_edge(apps[i], apps[j], "shared_lore",
                             data={"episode": ep})

    log(f"Detected {len(edges)} edges ({len(seen_edges)} unique)")
    return edges


# ── Component Building ──────────────────────────────────────────

def build_components(nodes, edges):
    """Group nodes into connected components using Union-Find."""
    uf = UnionFind()

    # Add all nodes
    for filename in nodes:
        uf.add(filename)

    # Union connected nodes via edges
    for edge in edges:
        uf.union(edge["source"], edge["target"])

    # Build component objects
    components = []
    for i, group in enumerate(uf.components()):
        group_edges = [
            e for e in edges
            if e["source"] in group and e["target"] in group
        ]
        components.append({
            "id": f"graph-{i+1:04d}",
            "nodes": sorted(group),
            "edges": group_edges,
            "size": len(group),
        })

    # Sort by size descending
    components.sort(key=lambda c: c["size"], reverse=True)
    # Re-number after sort
    for i, comp in enumerate(components):
        comp["id"] = f"graph-{i+1:04d}"

    log(f"Built {len(components)} components (largest: {components[0]['size'] if components else 0})")
    return components


# ── Deep Copy ──────────────────────────────────────────────────

def deep_copy_component(component, nodes):
    """Deep-copy all node data for a component into a self-contained object.

    Community data is slimmed: only top 3 comments (flattened, by upvotes)
    and summary rating stats are kept per node to control output size.
    """
    comp_nodes = {}
    all_player_ids = set()

    for filename in component["nodes"]:
        node = nodes.get(filename)
        if node:
            slim_node = copy.deepcopy(node)
            # Slim community data — top 3 comments only, no full trees
            all_comments = _flatten_comments(slim_node["community"].get("comments", []))
            all_comments.sort(key=lambda c: c.get("upvotes", 0), reverse=True)
            top_comments = []
            for c in all_comments[:3]:
                top_comments.append({
                    "id": c.get("id", ""),
                    "author": c.get("author", ""),
                    "authorId": c.get("authorId", ""),
                    "text": c.get("text", ""),
                    "upvotes": c.get("upvotes", 0),
                })
            slim_node["community"] = {
                "top_comments": top_comments,
                "avg_rating": slim_node["community"]["avg_rating"],
                "total_ratings": slim_node["community"]["total_ratings"],
                "total_comments": slim_node["community"]["total_comments"],
            }
            comp_nodes[filename] = slim_node
            # Collect player IDs
            all_player_ids.update(node["community"].get("commenters", []))
            all_player_ids.update(node["community"].get("raters", []))

    # Build player roster for this component (resolve from ORIGINAL nodes, not slim)
    players = []
    for pid in sorted(all_player_ids):
        if pid:
            players.append({"id": pid, "username": _resolve_player_name(pid, nodes, component["nodes"])})

    return {
        "id": component["id"],
        "nodes": comp_nodes,
        "edges": copy.deepcopy(component["edges"]),
        "players": players,
        "size": len(comp_nodes),
    }


def _resolve_player_name(player_id, all_nodes, filenames):
    """Try to find username from ratings/comments in the original (full) nodes."""
    for filename in filenames:
        node = all_nodes.get(filename)
        if not node:
            continue
        for r in node["community"].get("ratings", []):
            if r.get("playerId") == player_id:
                return r.get("username", player_id)
        for c in _flatten_comments(node["community"].get("comments", [])):
            if c.get("authorId") == player_id:
                return c.get("author", player_id)
    return player_id


# ── Graph Merge ──────────────────────────────────────────────────

def merge_graphs(graph_a, graph_b, nodes):
    """Merge two graph components into one."""
    merged_nodes = list(set(graph_a["nodes"]) | set(graph_b["nodes"]))
    merged_edges = graph_a["edges"] + graph_b["edges"]

    return {
        "id": graph_a["id"],  # Keep first graph's ID
        "nodes": sorted(merged_nodes),
        "edges": merged_edges,
        "size": len(merged_nodes),
    }


# ── Full Compile ──────────────────────────────────────────────────

def compile_graph(manifest, rankings, community, lore):
    """Full pipeline: nodes → edges → components → deep copy → output."""
    nodes = build_nodes(manifest, rankings, community, lore)
    log(f"Built {len(nodes)} nodes")

    edges = detect_edges(nodes, community)

    components = build_components(nodes, edges)

    # Deep-copy each component
    graphs = []
    for comp in components:
        graph = deep_copy_component(comp, nodes)
        graphs.append(graph)

    # Build edge type summary
    edge_types = defaultdict(int)
    for e in edges:
        edge_types[e["type"]] += 1

    # Build slim flat index (no full comment/rating blobs — those live in graphs)
    slim_nodes = {}
    for filename, node in nodes.items():
        slim_nodes[filename] = {
            "manifest": node["manifest"],
            "ranking": node["ranking"],
            "community": {
                "avg_rating": node["community"]["avg_rating"],
                "total_ratings": node["community"]["total_ratings"],
                "total_comments": node["community"]["total_comments"],
            },
            "lore": node["lore"],
            "graph": None,  # Will be filled below
        }

    # Tag each node with its graph ID
    for graph in graphs:
        for filename in graph["nodes"]:
            if filename in slim_nodes:
                slim_nodes[filename]["graph"] = graph["id"]

    result = {
        "meta": {
            "generated": datetime.now().isoformat(),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "total_graphs": len(graphs),
            "largest_graph": graphs[0]["size"] if graphs else 0,
            "edge_types": dict(edge_types),
        },
        "nodes": slim_nodes,  # Slim index (lookup by file, find graph ID)
        "graphs": graphs,     # Self-contained deep-copied graph components
    }

    return result


# ── CLI ──────────────────────────────────────────────────────────

def main():
    manifest = load_json(MANIFEST)
    rankings = load_json(RANKINGS)
    community = load_json(COMMUNITY)
    lore = load_json(LORE_FILE)

    if not manifest:
        print("ERROR: manifest.json not found")
        sys.exit(1)

    result = compile_graph(manifest, rankings, community, lore)

    if "--stats" in sys.argv:
        m = result["meta"]
        print(f"Nodes: {m['total_nodes']}")
        print(f"Edges: {m['total_edges']}")
        print(f"Graphs: {m['total_graphs']}")
        print(f"Largest: {m['largest_graph']} nodes")
        print(f"Edge types: {m['edge_types']}")
        return

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, separators=(",", ":"))

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"Compiled content graph: {OUTPUT.name}")
    print(f"  Nodes: {result['meta']['total_nodes']}")
    print(f"  Edges: {result['meta']['total_edges']}")
    print(f"  Graphs: {result['meta']['total_graphs']}")
    print(f"  Largest graph: {result['meta']['largest_graph']} nodes")
    print(f"  Size: {size_mb:.1f} MB")

    if "--push" in sys.argv:
        print("\nCommitting and pushing...")
        subprocess.run(["git", "add", str(OUTPUT)], cwd=ROOT)
        subprocess.run(
            ["git", "commit", "-m", "chore: compile content graph"],
            cwd=ROOT,
        )
        subprocess.run(["git", "push"], cwd=ROOT)
        print("Pushed!")


if __name__ == "__main__":
    main()
