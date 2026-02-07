# Local First Tools

450 self-contained HTML applications. No build process, no dependencies, works offline.

**[Browse the Gallery](https://kody-w.github.io/localFirstTools-main/)**

## Structure

```
index.html                Gallery frontend
scripts/autosort.py       Auto-sort pipeline
apps/
  manifest.json           App registry
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
