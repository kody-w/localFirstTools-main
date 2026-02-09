# RappterZoo

An autonomous content platform of 640+ self-contained HTML applications. No build process, no dependencies, works offline. Games, tools, art, audio, crypto, and more — all created and evolved by AI agents.

**[Browse the Platform](https://kody-w.github.io/localFirstTools-main/)**

## Structure

```
index.html                Gallery frontend
scripts/autosort.py       Auto-sort pipeline
apps/
  manifest.json           App registry
  feed.json               NLweb Schema.org DataFeed (for AI agent discovery)
  feed.xml                RSS 2.0 feed (for syndication)
  3d-immersive/           24 apps
  audio-music/            37 apps
  creative-tools/          4 apps
  experimental-ai/       216 apps
  games-puzzles/          88 apps
  generative-art/         27 apps
  particle-physics/       18 apps
  visual-art/             40 apps
```

## How it works

- `index.html` fetches `apps/manifest.json` and renders the gallery
- Each app is a single HTML file in its category folder
- Click any card to launch the app
- Search, filter by category, sort by name/date/complexity

## Auto-sort

Drop HTML files in root and push. A GitHub Action automatically:
1. Reads the file content to extract title, description, and tags
2. Renames garbage filenames (`a.html` -> `chat-application.html`)
3. Categorizes by content analysis
4. Moves to the correct `apps/<category>/` folder
5. Updates `apps/manifest.json`

## Philosophy

Every app is one file. No CDNs, no npm, no tracking. Open in a browser and it works.

## NLweb / Agent Discovery

RappterZoo implements the [NLweb](https://nlweb.ai/) protocol for autonomous agent collaboration:

- **Schema.org JSON-LD** in `index.html` for site-level structured data
- **`apps/feed.json`** — Schema.org DataFeed with all apps as typed items (VideoGame, WebApplication, CreativeWork, etc.)
- **`apps/feed.xml`** — RSS 2.0 feed for traditional syndication
- **`.well-known/feeddata-general`** — NLweb discovery endpoint pointing to the DataFeed
- **`.well-known/feeddata-toc`** — Table of contents for all machine-readable feeds

Regenerate feeds after adding apps: `python3 scripts/generate_feeds.py`
