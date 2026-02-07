# CLAUDE.md

Instructions for AI agents working in this repository.

## What This Repo Is

A GitHub Pages site serving 450 self-contained HTML applications through a gallery frontend. Every app is a single `.html` file with all CSS/JS inline. No build process, no package manager, no external dependencies.

**Live site:** https://kody-w.github.io/localFirstTools-main/

## Repo Structure

```
/
├── index.html                  # Gallery frontend (fetches apps/manifest.json)
├── README.md
├── CLAUDE.md                   # This file
├── .gitignore
└── apps/
    ├── manifest.json           # App registry (source of truth)
    ├── 3d-immersive/           # 23 apps - WebGL, Three.js, 3D worlds
    ├── audio-music/            # 37 apps - Synthesizers, DAWs, music tools
    ├── creative-tools/         #  4 apps - Productivity, utilities
    ├── experimental-ai/        # 214 apps - AI interfaces, simulators, experiments
    ├── games-puzzles/          # 85 apps - Games, puzzles, interactive play
    ├── generative-art/         # 27 apps - Algorithmic art, procedural generation
    ├── particle-physics/       # 18 apps - Physics sims, particle systems
    ├── visual-art/             # 40 apps - Visual experiences, design tools
    └── uncategorized/          #  2 apps
```

**Root is sacred.** Only `index.html`, `README.md`, `CLAUDE.md`, and `.gitignore` live in root. All apps go under `apps/<category>/`.

## How It Works

1. `index.html` is the gallery frontend served by GitHub Pages
2. On load, it fetches `apps/manifest.json`
3. It renders searchable, filterable cards linking to `apps/<category>/<file>.html`
4. Each app is completely standalone -- click to open, works offline

## manifest.json Schema

```json
{
  "categories": {
    "<category_key>": {
      "title": "Human Readable Title",
      "folder": "kebab-case-folder-name",
      "color": "#hex",
      "count": 40,
      "apps": [
        {
          "title": "App Title",
          "file": "app-filename.html",
          "description": "One-line description",
          "tags": ["canvas", "3d", "animation"],
          "complexity": "simple|intermediate|advanced",
          "type": "game|visual|audio|interactive|interface",
          "featured": true,
          "created": "YYYY-MM-DD"
        }
      ]
    }
  },
  "meta": {
    "version": "1.0",
    "lastUpdated": "YYYY-MM-DD"
  }
}
```

## Adding a New App

1. Create a self-contained HTML file (all CSS/JS inline, no external deps)
2. Pick the right category folder under `apps/`
3. Place the file: `apps/<category>/my-app.html`
4. Add an entry to `apps/manifest.json` in the correct category's `apps` array
5. Update the category `count` field
6. Commit and push -- GitHub Pages deploys automatically

Example manifest entry:
```json
{
  "title": "My New App",
  "file": "my-new-app.html",
  "description": "What it does in one sentence",
  "tags": ["canvas", "animation"],
  "complexity": "intermediate",
  "type": "visual",
  "featured": false,
  "created": "2026-02-07"
}
```

## App Requirements

Every HTML app MUST:
- Be a single `.html` file with all CSS and JavaScript inline
- Have a proper `<!DOCTYPE html>`, `<title>`, and `<meta name="viewport">`
- Work offline with zero network requests (no CDNs, no APIs required to function)
- Use `localStorage` for any data persistence
- Include JSON import/export if it manages user data

Every HTML app MUST NOT:
- Reference external `.js` or `.css` files
- Depend on files in other directories
- Assume any specific URL path (use relative paths only)
- Include hardcoded API keys or secrets

## Category Guide

| Key | Folder | Use for |
|-----|--------|---------|
| `visual_art` | `visual-art` | Drawing tools, visual effects, design apps |
| `3d_immersive` | `3d-immersive` | Three.js, WebGL, 3D environments |
| `audio_music` | `audio-music` | Synths, DAWs, music theory, audio viz |
| `generative_art` | `generative-art` | Procedural, algorithmic, fractal art |
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive toys |
| `particle_physics` | `particle-physics` | Physics sims, particle systems |
| `creative_tools` | `creative-tools` | Productivity, utilities, converters |
| `experimental_ai` | `experimental-ai` | AI experiments, simulators, prototypes |
| `educational_tools` | `educational` | Tutorials, learning tools |
| `uncategorized` | `uncategorized` | Doesn't fit elsewhere (avoid if possible) |

## Modifying the Gallery Frontend

`index.html` is a single self-contained file. It:
- Fetches `apps/manifest.json` on load
- Builds category filter pills from manifest keys
- Renders cards with links to `apps/<folder>/<file>`
- Has search (filters by title + description + tags)
- Has sort (A-Z, newest, complexity)
- Keyboard shortcut: `/` to focus search

To change the gallery UI, edit `index.html` directly. No build step.

## Deployment

Push to `main` branch. GitHub Pages auto-deploys from root. No CI/CD config needed -- it's legacy static hosting.

## Rules

- **Never put HTML apps in root.** Always `apps/<category>/`.
- **Never add external dependencies.** Every app is self-contained.
- **Always update manifest.json** when adding or removing apps.
- **Keep manifest.json and file system in sync.** Every manifest entry must have a matching file. Every app file should have a manifest entry.
- **No build process.** Everything is hand-editable static files.
- **No secrets.** This is a public repo. Never commit API keys, tokens, or credentials.
