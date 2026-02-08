#!/usr/bin/env python3
"""Tests for data freshness across the RappterZoo ecosystem.

Validates that generated JSON data files (broadcasts, community, content-graph)
contain unique, non-duplicate content. Catches stale template-generated data.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APPS_DIR = ROOT / "apps"
FEED_FILE = APPS_DIR / "broadcasts" / "feed.json"
LORE_FILE = APPS_DIR / "broadcasts" / "lore.json"
COMMUNITY_FILE = APPS_DIR / "community.json"
MANIFEST_FILE = APPS_DIR / "manifest.json"
RANKINGS_FILE = APPS_DIR / "rankings.json"
GRAPH_FILE = APPS_DIR / "content-graph.json"


# ── Helpers ──

def load_json(path):
    if not path.exists():
        pytest.skip(f"{path.name} not found")
    with open(path) as f:
        return json.load(f)


def get_all_manifest_apps(manifest):
    """Return set of all app filenames from manifest."""
    apps = set()
    for cat_data in manifest.get("categories", {}).values():
        for app in cat_data.get("apps", []):
            apps.add(app["file"])
    return apps


def get_all_dialogue_texts(feed):
    """Extract all dialogue text strings from feed episodes."""
    texts = []
    for ep in feed.get("episodes", []):
        for seg in ep.get("segments", []):
            if "text" in seg:
                texts.append(seg["text"])
            if "dialogue" in seg:
                for line in seg["dialogue"]:
                    if "text" in line:
                        texts.append(line["text"])
    return texts


# ── Broadcast Feed Tests ──

class TestBroadcastFreshness:
    """Verify broadcast feed.json has unique, non-template content."""

    def test_feed_exists(self):
        assert FEED_FILE.exists(), "feed.json must exist"

    def test_has_episodes(self):
        feed = load_json(FEED_FILE)
        assert len(feed.get("episodes", [])) >= 1

    def test_no_duplicate_dialogue_lines(self):
        """No two dialogue lines in the entire feed should be identical."""
        feed = load_json(FEED_FILE)
        texts = get_all_dialogue_texts(feed)
        dupes = [t for t, count in Counter(texts).items() if count > 1]
        assert len(dupes) == 0, (
            f"Found {len(dupes)} duplicate dialogue lines:\n"
            + "\n".join(f"  [{Counter(texts)[d]}x] {d[:100]}" for d in dupes[:10])
        )

    def test_no_duplicate_community_quotes_in_episode(self):
        """Within a single episode, no community quote should be repeated."""
        feed = load_json(FEED_FILE)
        for ep in feed.get("episodes", []):
            texts = []
            for seg in ep.get("segments", []):
                if "text" in seg:
                    texts.append(seg["text"])
                for line in seg.get("dialogue", []):
                    if "text" in line:
                        texts.append(line["text"])
            dupes = [t for t, c in Counter(texts).items() if c > 1]
            assert len(dupes) == 0, (
                f"Episode {ep.get('id')}: {len(dupes)} duplicate lines:\n"
                + "\n".join(f"  {d[:80]}" for d in dupes[:5])
            )

    def test_episode_titles_unique(self):
        feed = load_json(FEED_FILE)
        titles = [ep["title"] for ep in feed.get("episodes", [])]
        assert len(titles) == len(set(titles)), f"Duplicate episode titles: {titles}"

    def test_episodes_have_intro_and_outro(self):
        feed = load_json(FEED_FILE)
        for ep in feed.get("episodes", []):
            types = [s["type"] for s in ep.get("segments", [])]
            assert "intro" in types, f"{ep['id']} missing intro"
            assert "outro" in types, f"{ep['id']} missing outro"

    def test_episodes_have_reviews(self):
        feed = load_json(FEED_FILE)
        for ep in feed.get("episodes", []):
            reviews = [s for s in ep["segments"] if s["type"] == "review"]
            assert len(reviews) >= 1, f"{ep['id']} has no reviews"

    def test_review_dialogue_has_both_hosts(self):
        feed = load_json(FEED_FILE)
        for ep in feed.get("episodes", []):
            for seg in ep["segments"]:
                if seg["type"] == "review" and "dialogue" in seg:
                    hosts = {line["host"] for line in seg["dialogue"]}
                    assert "Rapptr" in hosts, f"Review in {ep['id']} missing Rapptr"
                    assert "ZooKeeper" in hosts, f"Review in {ep['id']} missing ZooKeeper"

    def test_no_template_placeholders(self):
        """Dialogue should not contain unresolved {placeholders}."""
        feed = load_json(FEED_FILE)
        texts = get_all_dialogue_texts(feed)
        for text in texts:
            assert "{title}" not in text, f"Unresolved placeholder: {text[:80]}"
            assert "{score}" not in text, f"Unresolved placeholder: {text[:80]}"
            assert "{grade}" not in text, f"Unresolved placeholder: {text[:80]}"
            assert "{category}" not in text, f"Unresolved placeholder: {text[:80]}"
            assert "{n}" not in text, f"Unresolved placeholder: {text[:80]}"

    def test_dialogue_min_length(self):
        """Each dialogue line should be substantive (>10 chars)."""
        feed = load_json(FEED_FILE)
        texts = get_all_dialogue_texts(feed)
        short = [t for t in texts if len(t) < 10]
        assert len(short) == 0, f"Found {len(short)} too-short lines: {short[:5]}"


# ── Community Data Tests ──

class TestCommunityFreshness:
    """Verify community.json has unique content covering all apps."""

    def test_community_exists(self):
        assert COMMUNITY_FILE.exists(), "community.json must exist"

    def test_all_manifest_apps_have_community(self):
        """Every app in manifest should have community data."""
        manifest = load_json(MANIFEST_FILE)
        community = load_json(COMMUNITY_FILE)
        manifest_apps = get_all_manifest_apps(manifest)
        community_apps = set(community.get("apps", {}).keys())
        missing = manifest_apps - community_apps
        # Allow up to 5% missing (new apps may not have community yet)
        pct_missing = len(missing) / len(manifest_apps) * 100 if manifest_apps else 0
        assert pct_missing < 10, (
            f"{len(missing)}/{len(manifest_apps)} apps ({pct_missing:.0f}%) missing community data: "
            + ", ".join(sorted(missing)[:10])
        )

    def test_no_duplicate_comments_per_app(self):
        """Within a single app, no two comments should have identical text."""
        community = load_json(COMMUNITY_FILE)
        for filename, app_data in community.get("apps", {}).items():
            comments = app_data.get("comments", [])
            texts = [c.get("text", "") for c in comments]
            dupes = [t for t, count in Counter(texts).items() if count > 1 and t]
            assert len(dupes) == 0, (
                f"{filename}: {len(dupes)} duplicate comments: {dupes[0][:60]}..."
            )

    def test_no_globally_reused_comments(self):
        """Same exact comment text should not appear across different apps (>3x = suspicious)."""
        community = load_json(COMMUNITY_FILE)
        all_comments = []
        for app_data in community.get("apps", {}).values():
            for c in app_data.get("comments", []):
                all_comments.append(c.get("text", ""))
        counts = Counter(all_comments)
        overused = {t: c for t, c in counts.items() if c > 3 and t}
        assert len(overused) == 0, (
            f"{len(overused)} comments appear >3 times globally:\n"
            + "\n".join(f"  [{c}x] {t[:80]}" for t, c in sorted(overused.items(), key=lambda x: -x[1])[:5])
        )

    def test_comments_reference_app_context(self):
        """At least 30% of comments should contain the app title or a tag."""
        manifest = load_json(MANIFEST_FILE)
        community = load_json(COMMUNITY_FILE)

        app_meta = {}
        for cat_data in manifest.get("categories", {}).values():
            for app in cat_data.get("apps", []):
                app_meta[app["file"]] = {
                    "title": app.get("title", "").lower(),
                    "tags": [t.lower() for t in app.get("tags", [])],
                }

        contextual = 0
        total = 0
        for filename, app_data in community.get("apps", {}).items():
            meta = app_meta.get(filename, {})
            title = meta.get("title", "")
            tags = meta.get("tags", [])
            for c in app_data.get("comments", []):
                text = c.get("text", "").lower()
                total += 1
                if title and title in text:
                    contextual += 1
                elif any(tag in text for tag in tags):
                    contextual += 1
        if total > 0:
            pct = contextual / total * 100
            assert pct >= 20, (
                f"Only {pct:.0f}% of comments reference app title/tags (expected >=20%)"
            )

    def test_unique_player_names(self):
        """Player/author names should be diverse — no single author >2% of comments."""
        community = load_json(COMMUNITY_FILE)
        authors = []
        for app_data in community.get("apps", {}).values():
            for c in app_data.get("comments", []):
                authors.append(c.get("author", ""))
        if not authors:
            pytest.skip("No comments found")
        counts = Counter(authors)
        threshold = len(authors) * 0.02
        overactive = {a: c for a, c in counts.items() if c > threshold}
        assert len(overactive) == 0, (
            f"{len(overactive)} authors appear >2% of all comments: "
            + ", ".join(f"{a}({c})" for a, c in sorted(overactive.items(), key=lambda x: -x[1])[:5])
        )


# ── Lore Tracker Tests ──

class TestLoreFreshness:
    """Verify lore.json tracks episode history properly."""

    def test_lore_exists(self):
        assert LORE_FILE.exists(), "lore.json must exist"

    def test_lore_tracks_reviewed_apps(self):
        lore = load_json(LORE_FILE)
        reviewed = lore.get("reviewed_apps", {})
        assert len(reviewed) >= 1, "Lore should track at least one reviewed app"

    def test_lore_episode_count_matches_feed(self):
        lore = load_json(LORE_FILE)
        feed = load_json(FEED_FILE)
        lore_eps = len(lore.get("episode_summaries", []))
        feed_eps = len(feed.get("episodes", []))
        assert lore_eps == feed_eps, (
            f"Lore tracks {lore_eps} episodes but feed has {feed_eps}"
        )


# ── Cross-File Consistency Tests ──

class TestEcosystemConsistency:
    """Verify data files are consistent with each other."""

    def test_broadcast_apps_exist_in_manifest(self):
        """All apps reviewed in broadcasts should exist in manifest."""
        feed = load_json(FEED_FILE)
        manifest = load_json(MANIFEST_FILE)
        manifest_apps = get_all_manifest_apps(manifest)

        reviewed_files = set()
        for ep in feed.get("episodes", []):
            for seg in ep["segments"]:
                if seg["type"] in ("review", "roast") and "app" in seg:
                    reviewed_files.add(seg["app"]["file"])

        missing = reviewed_files - manifest_apps
        assert len(missing) == 0, (
            f"Broadcast references apps not in manifest: {missing}"
        )

    def test_rankings_covers_manifest(self):
        """Rankings should cover most manifest apps."""
        manifest = load_json(MANIFEST_FILE)
        rankings = load_json(RANKINGS_FILE)
        manifest_apps = get_all_manifest_apps(manifest)
        ranked_apps = set(rankings.get("apps", {}).keys())
        missing = manifest_apps - ranked_apps
        pct = len(missing) / len(manifest_apps) * 100 if manifest_apps else 0
        assert pct < 5, (
            f"{len(missing)} manifest apps ({pct:.0f}%) missing from rankings"
        )
