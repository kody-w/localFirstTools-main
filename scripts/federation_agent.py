#!/usr/bin/env python3
"""Federation Agent — discovers NLweb platforms and syndicates content.

Probes known NLweb-compatible platforms via .well-known/feeddata-general,
reads their Schema.org DataFeeds, identifies content themes, and creates
inspired apps for RappterZoo. Also exports our feed for others to discover.

Modes:
  discover  — Probe all peers for NLweb endpoints
  scan      — Read discovered feeds, extract content themes
  inspire   — Use LLM to create apps inspired by federated content themes
  export    — Update our own NLweb feeds for syndication
  status    — Show federation network status
  auto      — Full cycle: discover → scan → inspire → export

Usage:
  python3 scripts/federation_agent.py discover [--verbose]
  python3 scripts/federation_agent.py scan [--verbose]
  python3 scripts/federation_agent.py inspire [--count N] [--dry-run]
  python3 scripts/federation_agent.py export
  python3 scripts/federation_agent.py status
  python3 scripts/federation_agent.py auto [--dry-run] [--verbose]
  python3 scripts/federation_agent.py add-peer <url> [--name NAME]
"""

import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, date
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"
FEDERATION_PATH = APPS_DIR / "federation.json"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
DRY_RUN = "--dry-run" in sys.argv

CATEGORY_FOLDERS = {
    "visual_art": "visual-art", "3d_immersive": "3d-immersive",
    "audio_music": "audio-music", "generative_art": "generative-art",
    "games_puzzles": "games-puzzles", "particle_physics": "particle-physics",
    "creative_tools": "creative-tools", "experimental_ai": "experimental-ai",
    "educational_tools": "educational", "data_tools": "data-tools",
    "productivity": "productivity",
}

USER_AGENT = "RappterZoo-Federation/1.0 (+https://kody-w.github.io/localFirstTools-main)"


# ── Helpers ───────────────────────────────────────────────────────

def load_federation():
    try:
        return json.loads(FEDERATION_PATH.read_text())
    except Exception:
        return {"peers": [], "sync_history": [], "stats": {
            "total_probes": 0, "platforms_discovered": 0,
            "feeds_indexed": 0, "apps_inspired": 0, "last_sync": None}}


def save_federation(data):
    if not DRY_RUN:
        FEDERATION_PATH.write_text(json.dumps(data, indent=2))


def _fetch(url, timeout=15):
    """Fetch a URL with our user agent."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, OSError) as e:
        if VERBOSE:
            print("    ⚠ Fetch failed: {} — {}".format(url, e))
        return None


def _has_copilot():
    try:
        r = subprocess.run(["gh", "copilot", "--version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _copilot(prompt, timeout=180):
    try:
        r = subprocess.run(
            ["gh", "copilot", "--model", "claude-opus-4.6", "-p", prompt, "--no-ask-user"],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def _parse_html(raw):
    if not raw:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    m = re.search(r"```(?:html)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if m:
        h = m.group(1).strip()
        if "<!DOCTYPE" in h or "<html" in h:
            return h
    m2 = re.search(r"(<!DOCTYPE html>.*</html>)", clean, re.DOTALL | re.IGNORECASE)
    return m2.group(1).strip() if m2 else None


def _parse_json_response(raw):
    if not raw:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    try:
        return json.loads(clean)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    s, e = clean.find("{"), clean.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(clean[s:e + 1])
        except Exception:
            pass
    return None


HAS_COPILOT = _has_copilot()


# ── Discovery ─────────────────────────────────────────────────────

def discover():
    """Probe all peers for NLweb endpoints."""
    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION DISCOVERY                        ║")
    print("╚══════════════════════════════════════════════╝")

    fed = load_federation()
    peers = fed.get("peers", [])
    discovered = 0

    for peer in peers:
        print("\n  Probing: {} ({})".format(peer["name"], peer["url"]))

        # Try .well-known/feeddata-general
        discovery_url = peer.get("discovery_url", peer["url"].rstrip("/") + "/.well-known/feeddata-general")
        raw = _fetch(discovery_url)

        if raw:
            peer["status"] = "active"
            peer["last_probed"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            discovered += 1
            print("    ✓ NLweb endpoint found")

            # Try to parse as JSON
            try:
                data = json.loads(raw)
                feeds = []
                # Schema.org DataFeed
                if data.get("@type") in ("DataFeed", "DataCatalog"):
                    feeds.append({"url": discovery_url, "type": data["@type"],
                                  "name": data.get("name", ""), "items": 0})
                # DataCatalog with dataset listing
                if "dataset" in data:
                    for ds in data["dataset"]:
                        feeds.append({"url": ds.get("url", ""),
                                      "type": ds.get("@type", "DataFeed"),
                                      "name": ds.get("name", "")})
                if feeds:
                    peer["feeds_found"] = feeds
                    print("    Found {} feed(s)".format(len(feeds)))
            except (json.JSONDecodeError, KeyError):
                peer["feeds_found"] = [{"url": discovery_url, "type": "unknown", "name": "raw"}]
                if VERBOSE:
                    print("    (non-JSON response, stored as raw)")
        else:
            # Try feeddata-toc as fallback
            toc_url = peer["url"].rstrip("/") + "/.well-known/feeddata-toc"
            toc_raw = _fetch(toc_url)
            if toc_raw:
                peer["status"] = "active"
                peer["last_probed"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                discovered += 1
                print("    ✓ Found via feeddata-toc")
                try:
                    toc_data = json.loads(toc_raw)
                    if "dataset" in toc_data:
                        peer["feeds_found"] = [{"url": ds.get("url", ""), "type": "DataFeed",
                                                 "name": ds.get("name", "")} for ds in toc_data["dataset"]]
                except Exception:
                    pass
            else:
                # Try RSS/Atom as last resort
                for rss_path in ["/feed", "/feed.xml", "/rss", "/atom.xml", "/feeds/all.rss.xml"]:
                    rss_url = peer["url"].rstrip("/") + rss_path
                    rss_raw = _fetch(rss_url, timeout=10)
                    if rss_raw and ("<rss" in rss_raw or "<feed" in rss_raw or "<channel" in rss_raw):
                        peer["status"] = "rss-only"
                        peer["last_probed"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                        peer["feeds_found"] = [{"url": rss_url, "type": "rss", "name": "RSS feed"}]
                        discovered += 1
                        print("    ✓ Found RSS at {}".format(rss_path))
                        break
                else:
                    peer["status"] = "unreachable"
                    peer["last_probed"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    print("    ✗ No NLweb endpoints found")

    fed["stats"]["total_probes"] = fed["stats"].get("total_probes", 0) + len(peers)
    fed["stats"]["platforms_discovered"] = sum(1 for p in peers if p["status"] in ("active", "rss-only"))
    save_federation(fed)

    print("\n  Discovery complete: {}/{} platforms reachable".format(discovered, len(peers)))
    return fed


# ── Scan ──────────────────────────────────────────────────────────

def scan(fed=None):
    """Read discovered feeds and extract content themes."""
    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION SCAN                             ║")
    print("╚══════════════════════════════════════════════╝")

    if not fed:
        fed = load_federation()
    peers = fed.get("peers", [])
    active = [p for p in peers if p.get("status") in ("active", "rss-only")]

    if not active:
        print("  No active peers to scan. Run 'discover' first.")
        return fed

    total_indexed = 0

    for peer in active:
        print("\n  Scanning: {} ({} feeds)".format(peer["name"], len(peer.get("feeds_found", []))))

        for feed_info in peer.get("feeds_found", []):
            feed_url = feed_info.get("url")
            if not feed_url:
                continue

            raw = _fetch(feed_url, timeout=20)
            if not raw:
                continue

            # Extract themes based on feed type
            themes = set(peer.get("content_themes", []))

            if feed_info.get("type") in ("DataFeed", "DataCatalog"):
                try:
                    data = json.loads(raw)
                    items = data.get("dataFeedElement", data.get("dataset", []))
                    feed_info["items"] = len(items)
                    total_indexed += len(items)

                    # Extract keywords/themes from items
                    for item in items[:50]:
                        inner = item.get("item", item)
                        if inner.get("keywords"):
                            for kw in str(inner["keywords"]).split(","):
                                themes.add(kw.strip().lower())
                        if inner.get("applicationCategory"):
                            themes.add(inner["applicationCategory"].lower())
                        if inner.get("@type"):
                            themes.add(inner["@type"].lower())
                except Exception:
                    pass

            elif feed_info.get("type") == "rss":
                # Extract from RSS titles and categories
                import re as _re
                titles = _re.findall(r"<title>([^<]+)</title>", raw)
                categories = _re.findall(r"<category>([^<]+)</category>", raw)
                for t in titles[:30]:
                    for word in t.lower().split():
                        if len(word) > 4:
                            themes.add(word)
                for c in categories[:30]:
                    themes.add(c.lower())
                feed_info["items"] = len(titles) - 1  # minus channel title
                total_indexed += max(0, len(titles) - 1)

            peer["content_themes"] = list(themes)[:30]
            if VERBOSE:
                print("    Indexed {} items, {} themes".format(
                    feed_info.get("items", 0), len(peer["content_themes"])))

    fed["stats"]["feeds_indexed"] = total_indexed
    save_federation(fed)

    print("\n  Scan complete: {} items indexed across {} platforms".format(
        total_indexed, len(active)))
    return fed


# ── Inspire ───────────────────────────────────────────────────────

def inspire(fed=None, count=1):
    """Create apps inspired by federated content themes."""
    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION INSPIRE                          ║")
    print("╚══════════════════════════════════════════════╝")

    if not fed:
        fed = load_federation()

    # Collect all themes from active peers
    all_themes = {}
    for peer in fed.get("peers", []):
        if peer.get("status") not in ("active", "rss-only"):
            continue
        for theme in peer.get("content_themes", []):
            if theme not in all_themes:
                all_themes[theme] = []
            all_themes[theme].append(peer["name"])

    if not all_themes:
        print("  No themes discovered. Run 'scan' first.")
        # Use platform type themes as fallback
        for peer in fed.get("peers", []):
            ptype = peer.get("type", "")
            if ptype:
                for word in ptype.split("-"):
                    all_themes[word] = [peer["name"]]

    if not all_themes:
        print("  No themes available at all.")
        return []

    print("  {} unique themes from {} peers".format(
        len(all_themes), len(set(src for srcs in all_themes.values() for src in srcs))))

    results = []
    for i in range(count):
        # Pick a theme cluster
        theme_keys = list(all_themes.keys())
        primary = random.choice(theme_keys)
        secondary = random.choice(theme_keys)
        sources = list(set(all_themes.get(primary, []) + all_themes.get(secondary, [])))

        # Determine best category for this theme
        theme_to_cat = {
            "travel": "creative_tools", "planning": "productivity", "recipes": "creative_tools",
            "cooking": "creative_tools", "events": "productivity", "scheduling": "productivity",
            "education": "educational_tools", "tutorials": "educational_tools",
            "programming": "data_tools", "technical": "data_tools",
            "reviews": "creative_tools", "maps": "3d_immersive",
            "music": "audio_music", "art": "visual_art", "games": "games_puzzles",
            "nutrition": "data_tools", "community": "experimental_ai",
        }
        cat = theme_to_cat.get(primary, theme_to_cat.get(secondary, "experimental_ai"))
        folder = CATEGORY_FOLDERS.get(cat, "experimental-ai")

        print("\n  ─── Inspiration {}/{} ───".format(i + 1, count))
        print("  Themes: {} + {} (from {})".format(primary, secondary, ", ".join(sources[:3])))
        print("  Target: {} → apps/{}/ ".format(cat, folder))

        if DRY_RUN:
            print("  [DRY RUN] Would generate app for themes: {}, {}".format(primary, secondary))
            results.append({"themes": [primary, secondary], "sources": sources,
                            "category": cat, "dry_run": True})
            continue

        if not HAS_COPILOT:
            print("  ✗ No Copilot CLI — skipping generation")
            continue

        prompt = """You are the RappterZoo Federation Agent. Create a self-contained HTML application
inspired by content themes discovered from federated NLweb platforms.

INSPIRATION THEMES: {themes}
CONTENT SOURCES: {sources}
TARGET CATEGORY: {cat}

The app should be a CREATIVE INTERPRETATION of these themes — not a copy.
For example, if themes are "travel" + "planning", make an interactive trip planner.
If themes are "recipes" + "nutrition", make a meal planning dashboard.

HARD REQUIREMENTS:
1. Single HTML file, ALL CSS/JS inline. No external files, no CDNs.
2. Include: <!DOCTYPE html>, <title>, <meta name="viewport">
3. Works completely offline with zero network requests
4. Must be genuinely useful — someone should spend 10+ minutes with it
5. Use localStorage if the app manages user data
6. Include these meta tags:
   <meta name="rappterzoo:author" content="federation-agent">
   <meta name="rappterzoo:author-type" content="agent">
   <meta name="rappterzoo:category" content="{cat}">
   <meta name="rappterzoo:type" content="interactive">
   <meta name="rappterzoo:complexity" content="intermediate">
   <meta name="rappterzoo:created" content="{today}">
   <meta name="rappterzoo:generation" content="1">
   <meta name="rappterzoo:federation-source" content="{source_names}">
7. Escape <\\/script> in JS strings

Output ONLY the complete HTML. No explanation.""".format(
            themes=", ".join([primary, secondary]),
            sources=", ".join(sources[:3]),
            cat=cat,
            today=date.today().isoformat(),
            source_names="|".join(sources[:3]),
        )

        raw = _copilot(prompt, timeout=180)
        html = _parse_html(raw)

        if not html:
            print("  ✗ Generation failed")
            continue
        if "<!DOCTYPE" not in html and "<!doctype" not in html:
            print("  ✗ Invalid HTML")
            continue

        # Extract title
        tm = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        title = tm.group(1).strip() if tm else "Federation: {} + {}".format(primary.title(), secondary.title())

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
        filename = slug + ".html"
        filepath = APPS_DIR / folder / filename

        if filepath.exists():
            filename = "{}-fed-{}.html".format(slug, random.randint(100, 999))
            filepath = APPS_DIR / folder / filename

        filepath.write_text(html)
        print("  ✓ Created: apps/{}/{} ({:.1f}KB)".format(folder, filename, len(html) / 1024))

        # Update manifest
        try:
            manifest = json.loads(MANIFEST_PATH.read_text())
            entry = {
                "title": title, "file": filename,
                "description": "Inspired by {} — federated from {}".format(
                    " + ".join([primary, secondary]), ", ".join(sources[:2])),
                "tags": [primary, secondary, "federation"][:6],
                "complexity": "intermediate",
                "type": "interactive",
                "featured": False,
                "created": date.today().isoformat(),
                "generation": 1,
            }
            if cat in manifest.get("categories", {}):
                manifest["categories"][cat]["apps"].append(entry)
                manifest["categories"][cat]["count"] = len(manifest["categories"][cat]["apps"])
            with open(MANIFEST_PATH, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            print("  ⚠ Manifest update failed: {}".format(e))

        # Update federation stats
        for peer in fed.get("peers", []):
            if peer["name"] in sources:
                peer["apps_inspired"] = peer.get("apps_inspired", 0) + 1

        results.append({"title": title, "file": filename, "themes": [primary, secondary],
                        "sources": sources, "category": cat})

    fed["stats"]["apps_inspired"] = fed["stats"].get("apps_inspired", 0) + len(
        [r for r in results if not r.get("dry_run")])
    save_federation(fed)

    # Log to activity log
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from activity_log import log_activity
        log_activity("federation-agent",
                     "Inspired {} app(s) from {} themes".format(len(results), len(all_themes)),
                     {"apps_created": len([r for r in results if not r.get("dry_run")]),
                      "themes_used": len(all_themes),
                      "sources": list(set(s for r in results for s in r.get("sources", [])))},
                     dry_run=DRY_RUN)
    except Exception:
        pass

    return results


# ── Export ────────────────────────────────────────────────────────

def export_feeds():
    """Regenerate our NLweb feeds for syndication."""
    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION EXPORT                           ║")
    print("╚══════════════════════════════════════════════╝")

    try:
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "generate_feeds.py"), "--verbose"],
            capture_output=False, timeout=60
        )
        print("  ✓ Feeds regenerated for syndication")
    except Exception as e:
        print("  ⚠ Feed generation failed: {}".format(e))


# ── Status ────────────────────────────────────────────────────────

def status():
    """Show federation network status."""
    fed = load_federation()
    peers = fed.get("peers", [])
    stats = fed.get("stats", {})

    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION STATUS                           ║")
    print("╠══════════════════════════════════════════════╣")

    for peer in peers:
        icon = "🟢" if peer["status"] == "active" else "🟡" if peer["status"] == "rss-only" else "⚪" if peer["status"] == "pending" else "🔴"
        feeds = len(peer.get("feeds_found", []))
        themes = len(peer.get("content_themes", []))
        inspired = peer.get("apps_inspired", 0)
        print("║  {} {:20s} {:10s} feeds:{} themes:{} inspired:{}".format(
            icon, peer["name"][:20], peer["status"], feeds, themes, inspired))

    print("╠══════════════════════════════════════════════╣")
    print("║  Total probes:    {:<27}║".format(stats.get("total_probes", 0)))
    print("║  Discovered:      {:<27}║".format(stats.get("platforms_discovered", 0)))
    print("║  Feeds indexed:   {:<27}║".format(stats.get("feeds_indexed", 0)))
    print("║  Apps inspired:   {:<27}║".format(stats.get("apps_inspired", 0)))
    print("║  Last sync:       {:<27}║".format(stats.get("last_sync", "never")))
    print("╚══════════════════════════════════════════════╝")


# ── Add Peer ──────────────────────────────────────────────────────

def add_peer(url, name=None):
    """Add a new peer to the federation registry."""
    fed = load_federation()
    peers = fed.get("peers", [])

    # Check for duplicate
    for p in peers:
        if p["url"] == url:
            print("  ⚠ Peer already registered: {}".format(p["name"]))
            return

    peer_id = re.sub(r"[^a-z0-9]+", "-", (name or url.split("//")[-1].split("/")[0]).lower()).strip("-")
    peer = {
        "id": peer_id,
        "name": name or url.split("//")[-1].split("/")[0],
        "url": url,
        "discovery_url": url.rstrip("/") + "/.well-known/feeddata-general",
        "status": "pending",
        "type": "unknown",
        "last_probed": None,
        "feeds_found": [],
        "content_themes": [],
        "apps_inspired": 0,
        "notes": "Added by federation agent",
    }
    peers.append(peer)
    fed["peers"] = peers
    save_federation(fed)
    print("  ✓ Added peer: {} ({})".format(peer["name"], url))


# ── Auto Mode ─────────────────────────────────────────────────────

def auto():
    """Full federation cycle."""
    print("╔══════════════════════════════════════════════╗")
    print("║  FEDERATION AGENT — AUTO MODE                ║")
    print("║  {}                           ║".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("╚══════════════════════════════════════════════╝")
    print("  Mode: {}".format("DRY RUN" if DRY_RUN else "LIVE"))
    print("  LLM: {}".format("Copilot CLI" if HAS_COPILOT else "Unavailable"))

    start = datetime.now()

    # Phase 1: Discover
    fed = discover()

    # Phase 2: Scan
    fed = scan(fed)

    # Phase 3: Inspire
    count_arg = 1
    for i, arg in enumerate(sys.argv):
        if arg == "--count" and i + 1 < len(sys.argv):
            count_arg = int(sys.argv[i + 1])

    results = inspire(fed, count=count_arg)

    # Phase 4: Export
    if not DRY_RUN:
        export_feeds()

    # Phase 5: Log sync
    fed = load_federation()
    elapsed = (datetime.now() - start).total_seconds()
    fed["sync_history"].append({
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apps_inspired": len([r for r in results if not r.get("dry_run")]),
        "platforms_probed": len(fed.get("peers", [])),
        "elapsed_seconds": int(elapsed),
        "dry_run": DRY_RUN,
    })
    fed["sync_history"] = fed["sync_history"][-50:]
    fed["stats"]["last_sync"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_federation(fed)

    # Summary
    print("\n╔══════════════════════════════════════════════╗")
    print("║  FEDERATION COMPLETE ({:.0f}s)                  ║".format(elapsed))
    print("╠══════════════════════════════════════════════╣")
    active = sum(1 for p in fed["peers"] if p["status"] in ("active", "rss-only"))
    print("║  Peers: {}/{} reachable                     ║".format(active, len(fed["peers"])))
    print("║  Apps inspired: {:<29}║".format(len(results)))
    print("╚══════════════════════════════════════════════╝")


# ── CLI ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return

    mode = sys.argv[1]

    if mode == "discover":
        discover()
    elif mode == "scan":
        fed = load_federation()
        scan(fed)
    elif mode == "inspire":
        count = 1
        for i, arg in enumerate(sys.argv):
            if arg == "--count" and i + 1 < len(sys.argv):
                count = int(sys.argv[i + 1])
        inspire(count=count)
    elif mode == "export":
        export_feeds()
    elif mode == "status":
        status()
    elif mode == "auto":
        auto()
    elif mode == "add-peer":
        if len(sys.argv) < 3:
            print("Usage: federation_agent.py add-peer <url> [--name NAME]")
            return
        url = sys.argv[2]
        name = None
        for i, arg in enumerate(sys.argv):
            if arg == "--name" and i + 1 < len(sys.argv):
                name = sys.argv[i + 1]
        add_peer(url, name)
    else:
        print("Unknown mode: {}. Run with --help.".format(mode))
        sys.exit(1)


if __name__ == "__main__":
    main()
