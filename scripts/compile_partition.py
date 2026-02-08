#!/usr/bin/env python3
"""
Compile a single category partition from manifest, rankings, community, and lore data.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def load_json(path):
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    """Save JSON file minified."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, separators=(',', ':'))

def extract_stem(filename):
    """Extract stem from filename (remove .html)."""
    return filename.replace('.html', '') if filename.endswith('.html') else filename

def compile_partition(category_key, output_path):
    """Compile partition for a single category."""

    # Load all data files
    base_dir = Path(__file__).parent.parent
    manifest = load_json(base_dir / 'apps' / 'manifest.json')
    rankings_data = load_json(base_dir / 'apps' / 'rankings.json')
    rankings = rankings_data.get('rankings', [])
    community = load_json(base_dir / 'apps' / 'community.json')
    lore = load_json(base_dir / 'apps' / 'broadcasts' / 'lore.json')

    # Get category data
    if category_key not in manifest['categories']:
        print(f"Error: Category '{category_key}' not found in manifest", file=sys.stderr)
        sys.exit(1)

    cat_data = manifest['categories'][category_key]
    folder = cat_data['folder']
    apps = cat_data['apps']

    # Build all-apps title index for comment mention detection
    all_titles = {}
    for cat_key, cat_info in manifest['categories'].items():
        cat_folder = cat_info['folder']
        for app in cat_info['apps']:
            if len(app['title']) > 3:  # Only titles >3 chars
                all_titles[app['title'].lower()] = {
                    'file': app['file'],
                    'category': cat_key,
                    'folder': cat_folder
                }

    # Build nodes dict
    nodes = {}
    for app in apps:
        filename = app['file']
        stem = extract_stem(filename)

        # Get ranking data
        rank_data = next((r for r in rankings if r.get('file') == filename), None)
        score = rank_data.get('score', 0) if rank_data else 0
        grade = rank_data.get('grade', 'F') if rank_data else 'F'

        # Extract playability from dimensions
        playability = 0
        if rank_data and 'dimensions' in rank_data:
            playability = rank_data['dimensions'].get('playability', {}).get('score', 0)

        # Get community data
        player_ratings = community.get('ratings', {}).get(stem, [])
        player_comments = community.get('comments', {}).get(stem, [])

        avg_rating = sum(r.get('stars', 0) for r in player_ratings) / len(player_ratings) if player_ratings else 0
        total_ratings = len(player_ratings)
        total_comments = len(player_comments)

        # Top 3 comments by upvotes
        sorted_comments = sorted(player_comments, key=lambda c: c.get('upvotes', 0), reverse=True)
        top_comments = [
            {
                'author': c['author'],
                'text': c['text'],
                'upvotes': c.get('upvotes', 0)
            }
            for c in sorted_comments[:3]
        ]

        # Get lore data
        lore_entry = lore.get('apps', {}).get(filename)
        lore_data = None
        if lore_entry:
            lore_data = {
                'episodes': lore_entry.get('episodes', []),
                'scores': lore_entry.get('scores', []),
                'grades': lore_entry.get('grades', [])
            }

        # Build node
        nodes[filename] = {
            'title': app['title'],
            'file': filename,
            'category': category_key,
            'folder': folder,
            'path': f"apps/{folder}/{filename}",
            'url': f"https://kody-w.github.io/localFirstTools-main/apps/{folder}/{filename}",
            'tags': app.get('tags', []),
            'description': app.get('description', ''),
            'score': score,
            'grade': grade,
            'playability': playability,
            'avg_rating': round(avg_rating, 2),
            'total_ratings': total_ratings,
            'total_comments': total_comments,
            'top_comments': top_comments,
            'lore': lore_data
        }

    # Build edges
    internal_edges = []
    cross_edges = []

    # Track edges to avoid duplicates
    edge_set = set()

    # 1. Shared player edges (same player rated/commented on both apps)
    player_to_apps = defaultdict(set)

    for app in apps:
        stem = extract_stem(app['file'])

        # Collect players from ratings
        for rating in community.get('ratings', {}).get(stem, []):
            player_id = rating.get('playerId')
            if player_id:
                player_to_apps[player_id].add(app['file'])

        # Collect players from comments
        for comment in community.get('comments', {}).get(stem, []):
            player_id = comment.get('playerId')
            if player_id:
                player_to_apps[player_id].add(app['file'])

    # Create shared_player edges (cap at 10 per player)
    for player_id, app_files in player_to_apps.items():
        if len(app_files) < 2:
            continue

        app_list = sorted(list(app_files))[:10]  # Cap at 10 apps per player
        for i, src in enumerate(app_list):
            for tgt in app_list[i+1:]:
                edge_key = (src, tgt, 'shared_player')
                if edge_key not in edge_set:
                    edge_set.add(edge_key)

                    # Count how many players share these two apps
                    weight = sum(1 for pid, files in player_to_apps.items() if src in files and tgt in files)

                    edge = {
                        'source': src,
                        'target': tgt,
                        'type': 'shared_player',
                        'weight': weight
                    }
                    internal_edges.append(edge)

    # 2. Comment mention edges (comment text contains another app's title)
    for app in apps:
        stem = extract_stem(app['file'])

        for comment in community.get('comments', {}).get(stem, []):
            text_lower = comment.get('text', '').lower()

            # Search for mentions of other apps
            for title_lower, target_info in all_titles.items():
                if title_lower in text_lower:
                    target_file = target_info['file']
                    target_cat = target_info['category']

                    # Skip self-mention
                    if target_file == app['file']:
                        continue

                    edge_key = (app['file'], target_file, 'comment_mention')
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)

                        edge = {
                            'source': app['file'],
                            'target': target_file,
                            'type': 'comment_mention',
                            'weight': 5
                        }

                        if target_cat == category_key:
                            internal_edges.append(edge)
                        else:
                            cross_edges.append(edge)

    # 3. Shared tags edges (apps share 3+ tags)
    for i, app1 in enumerate(apps):
        tags1 = set(app1.get('tags', []))

        for app2 in apps[i+1:]:
            tags2 = set(app2.get('tags', []))
            shared = tags1 & tags2

            if len(shared) >= 3:
                edge_key = (app1['file'], app2['file'], 'shared_tags')
                if edge_key not in edge_set:
                    edge_set.add(edge_key)

                    edge = {
                        'source': app1['file'],
                        'target': app2['file'],
                        'type': 'shared_tags',
                        'weight': len(shared)
                    }
                    internal_edges.append(edge)

    # Build partition object
    partition = {
        'category': category_key,
        'node_count': len(nodes),
        'nodes': nodes,
        'internal_edges': internal_edges,
        'cross_edges': cross_edges
    }

    # Save partition
    save_json(output_path, partition)

    print(f"Compiled partition for {category_key}:")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Internal edges: {len(internal_edges)}")
    print(f"  Cross edges: {len(cross_edges)}")
    print(f"  Output: {output_path}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: compile_partition.py <category_key> <output_path>", file=sys.stderr)
        sys.exit(1)

    category_key = sys.argv[1]
    output_path = sys.argv[2]

    compile_partition(category_key, output_path)
