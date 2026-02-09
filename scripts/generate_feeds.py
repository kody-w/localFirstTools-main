#!/usr/bin/env python3
"""Generate NLweb-compatible feeds from apps/manifest.json.

Produces:
  - apps/feed.json  — Schema.org DataFeed (JSON-LD) for NLweb/agent discovery
  - apps/feed.xml   — RSS 2.0 feed for traditional syndication

Usage:
  python3 scripts/generate_feeds.py [--verbose]
"""

import json
import os
import sys
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

SITE_URL = "https://kody-w.github.io/localFirstTools-main"
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "manifest.json")
FEED_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "feed.json")
FEED_XML_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "feed.xml")
RANKINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "apps", "rankings.json")

SCHEMA_TYPE_MAP = {
    "game": "VideoGame",
    "visual": "CreativeWork",
    "audio": "MusicComposition",
    "interactive": "WebApplication",
    "interface": "WebApplication",
}

COMPLEXITY_MAP = {
    "simple": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
}


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def load_rankings(path):
    """Load rankings, handling the nested structure."""
    data = load_json(path)
    if isinstance(data, dict):
        return data.get("rankings", [])
    return data if isinstance(data, list) else []


def build_feed_json(manifest, rankings):
    """Build Schema.org DataFeed JSON-LD."""
    scores = {}
    if rankings:
        for entry in rankings:
            scores[entry.get("file", "")] = entry.get("score", 0)

    items = []
    for cat_key, cat in manifest.get("categories", {}).items():
        folder = cat.get("folder", cat_key.replace("_", "-"))
        for app in cat.get("apps", []):
            app_url = "{}/apps/{}/{}".format(SITE_URL, folder, app["file"])
            schema_type = SCHEMA_TYPE_MAP.get(app.get("type", ""), "WebApplication")

            item = {
                "@type": "DataFeedItem",
                "dateModified": app.get("created", "2024-01-01"),
                "item": {
                    "@type": schema_type,
                    "name": app.get("title", app["file"]),
                    "description": app.get("description", ""),
                    "url": app_url,
                    "applicationCategory": cat.get("title", cat_key),
                    "operatingSystem": "Any (browser)",
                    "offers": {
                        "@type": "Offer",
                        "price": "0",
                        "priceCurrency": "USD",
                    },
                    "isAccessibleForFree": True,
                    "inLanguage": "en",
                },
            }

            if app.get("tags"):
                item["item"]["keywords"] = ", ".join(app["tags"])
            if app.get("complexity"):
                item["item"]["proficiencyLevel"] = COMPLEXITY_MAP.get(
                    app["complexity"], app["complexity"]
                )
            if app.get("featured"):
                item["item"]["isFamilyFriendly"] = True

            score = scores.get(app["file"], 0)
            if score:
                item["item"]["aggregateRating"] = {
                    "@type": "AggregateRating",
                    "ratingValue": round(score, 1),
                    "bestRating": 100,
                    "worstRating": 0,
                    "ratingCount": 1,
                }

            gen = app.get("generation", 0)
            if gen:
                item["item"]["version"] = "gen-{}".format(gen)

            items.append(item)

    feed = {
        "@context": "https://schema.org",
        "@type": "DataFeed",
        "name": "RappterZoo App Feed",
        "description": "All self-contained HTML applications in the RappterZoo autonomous content platform. Each app is a single-file, zero-dependency, offline-capable browser application.",
        "url": "{}/apps/feed.json".format(SITE_URL),
        "publisher": {
            "@type": "Organization",
            "name": "RappterZoo",
            "url": "https://github.com/kody-w/localFirstTools-main",
        },
        "dateModified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "license": "https://opensource.org/licenses/MIT",
        "dataFeedElement": items,
    }
    return feed


def build_feed_xml(manifest, rankings):
    """Build RSS 2.0 XML feed."""
    scores = {}
    if rankings:
        for entry in rankings:
            scores[entry.get("file", "")] = entry.get("score", 0)

    items_xml = []
    for cat_key, cat in manifest.get("categories", {}).items():
        folder = cat.get("folder", cat_key.replace("_", "-"))
        for app in cat.get("apps", []):
            app_url = "{}/apps/{}/{}".format(SITE_URL, folder, app["file"])
            title = app.get("title", app["file"])
            desc = app.get("description", "")
            created = app.get("created", "2024-01-01")
            tags = app.get("tags", [])
            score = scores.get(app["file"], 0)

            categories_xml = ""
            for tag in tags:
                categories_xml += "      <category>{}</category>\n".format(
                    xml_escape(tag)
                )
            categories_xml += "      <category>{}</category>\n".format(
                xml_escape(cat.get("title", cat_key))
            )

            score_note = " (score: {}/100)".format(round(score)) if score else ""

            items_xml.append(
                """    <item>
      <title>{title}</title>
      <link>{url}</link>
      <description>{desc}{score}</description>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{date}</pubDate>
{categories}    </item>""".format(
                    title=xml_escape(title),
                    url=xml_escape(app_url),
                    desc=xml_escape(desc),
                    score=xml_escape(score_note),
                    date=xml_escape(created),
                    categories=categories_xml,
                )
            )

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>RappterZoo — Autonomous Content Platform</title>
    <link>{site}</link>
    <description>Self-contained, local-first HTML apps created and evolved by AI agents. Games, tools, art, audio, crypto, and more.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{site}/apps/feed.xml" rel="self" type="application/rss+xml"/>
    <docs>https://www.rssboard.org/rss-specification</docs>
    <generator>RappterZoo generate_feeds.py</generator>
{items}
  </channel>
</rss>""".format(
        site=SITE_URL,
        now=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        items="\n".join(items_xml),
    )
    return rss


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    manifest = load_json(os.path.abspath(MANIFEST_PATH))

    rankings = None
    rankings_abs = os.path.abspath(RANKINGS_PATH)
    if os.path.exists(rankings_abs):
        try:
            rankings = load_rankings(rankings_abs)
        except Exception:
            if verbose:
                print("  Warning: could not load rankings.json")

    # Count apps
    total = sum(
        len(c.get("apps", []))
        for c in manifest.get("categories", {}).values()
    )

    # Generate JSON-LD feed
    feed_json = build_feed_json(manifest, rankings)
    json_path = os.path.abspath(FEED_JSON_PATH)
    with open(json_path, "w") as f:
        json.dump(feed_json, f, indent=2)
    if verbose:
        print("  Wrote {} ({} items)".format(json_path, len(feed_json["dataFeedElement"])))

    # Generate RSS feed
    feed_xml = build_feed_xml(manifest, rankings)
    xml_path = os.path.abspath(FEED_XML_PATH)
    with open(xml_path, "w") as f:
        f.write(feed_xml)
    if verbose:
        print("  Wrote {}".format(xml_path))

    print("Generated feeds: {} apps -> feed.json + feed.xml".format(total))


if __name__ == "__main__":
    main()
