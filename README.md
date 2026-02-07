# Local First Tools

450+ self-contained HTML applications. No build process, no dependencies, works offline.

**[Browse the Gallery](https://kody-w.github.io/localFirstTools-main/)**

## Structure

```
index.html              Gallery frontend
apps/
  manifest.json         App registry
  visual-art/           40 apps
  3d-immersive/         24 apps
  audio-music/          37 apps
  generative-art/       27 apps
  games-puzzles/        90 apps
  particle-physics/     18 apps
  creative-tools/        4 apps
  experimental-ai/     217 apps
  uncategorized/         2 apps
```

## How it works

- `index.html` fetches `apps/manifest.json` and renders the gallery
- Each app is a single HTML file in its category folder
- Click any card to launch the app
- Search, filter by category, sort by name/date/complexity

## Philosophy

Every app is one file. No CDNs, no npm, no tracking. Open in a browser and it works.
