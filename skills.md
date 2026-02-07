# skills.md

Operational playbook for agents working in `localFirstTools-main`. This is the only file you need to read to understand and operate this repo.

---

## Skill 1: Understand the System

This is a **static GitHub Pages site** at `https://kody-w.github.io/localFirstTools-main/`. It serves 450 self-contained HTML applications through a gallery frontend.

**Architecture:**
```
index.html           → Gallery UI (reads manifest, renders cards, links to apps)
apps/manifest.json   → Single source of truth for all app metadata
apps/<category>/     → HTML app files organized by category
```

**Data flow:** User visits site → `index.html` loads → fetches `apps/manifest.json` → renders filterable/searchable card grid → user clicks card → opens `apps/<category>/<file>.html`

**Deployment:** Push to `main` → GitHub Pages auto-deploys. No CI, no build, no config.

---

## Skill 2: Add a New App

**Steps:**
```bash
# 1. Create the app (single HTML file, everything inline)
# 2. Put it in the right category folder
cp my-app.html apps/games-puzzles/

# 3. Add to manifest
# Edit apps/manifest.json → find the right category → add entry to "apps" array
# 4. Bump the category "count" field
# 5. Commit and push
git add apps/games-puzzles/my-app.html apps/manifest.json
git commit -m "Add my-app to games-puzzles"
git push origin main
```

**Manifest entry format:**
```json
{
  "title": "My App",
  "file": "my-app.html",
  "description": "One sentence about what it does",
  "tags": ["canvas", "game"],
  "complexity": "simple",
  "type": "game",
  "featured": false,
  "created": "2026-02-07"
}
```

**Field rules:**
- `file` — Exact filename, must match the file in the category folder
- `tags` — Pick from: `3d`, `canvas`, `svg`, `animation`, `particles`, `physics`, `audio`, `interactive`, `game`, `creative`, `terminal`, `retro`, `simulation`, `ai`, `crm`
- `complexity` — `simple` (<20KB), `intermediate` (20-50KB), `advanced` (>50KB or uses WebGL/3D)
- `type` — `game`, `visual`, `audio`, `interactive`, `interface`, `drawing`
- `featured` — Set `true` only for standout apps

---

## Skill 3: Pick the Right Category

| If the app is about... | Put it in | Manifest key |
|------------------------|-----------|--------------|
| Drawing, design, visual effects | `apps/visual-art/` | `visual_art` |
| 3D worlds, WebGL, Three.js | `apps/3d-immersive/` | `3d_immersive` |
| Sound, music, synths, audio viz | `apps/audio-music/` | `audio_music` |
| Fractals, procedural, algorithmic art | `apps/generative-art/` | `generative_art` |
| Games, puzzles, playable things | `apps/games-puzzles/` | `games_puzzles` |
| Physics sims, particle systems | `apps/particle-physics/` | `particle_physics` |
| Utilities, converters, productivity | `apps/creative-tools/` | `creative_tools` |
| AI experiments, simulators, prototypes | `apps/experimental-ai/` | `experimental_ai` |
| Tutorials, learning tools | `apps/educational/` | `educational_tools` |
| Nothing else fits | `apps/experimental-ai/` | `experimental_ai` (catch-all) |

When in doubt between two categories, pick the one with fewer apps to balance distribution.

---

## Skill 4: Build an App That Meets the Standard

**Template:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>App Name</title>
<meta name="description" content="What this app does">
<style>
  /* All CSS here — no external stylesheets */
</style>
</head>
<body>
  <!-- All HTML here -->
  <script>
    // All JS here — no external scripts
    // Use localStorage for persistence
    // Include JSON export/import if app manages user data
  </script>
</body>
</html>
```

**Hard requirements:**
- Single `.html` file, everything inline
- Works offline, zero network requests to function
- No CDN links, no npm, no external scripts or stylesheets
- No hardcoded API keys or secrets
- Responsive (works on mobile and desktop)
- Uses `localStorage` for persistence, never external databases
- Includes `<title>` and `<meta name="description">`

**If the app manages user data**, it must have:
- A JSON export button (downloads current state as `.json`)
- A JSON import button (loads state from a `.json` file)
- Round-trip fidelity: export → import → identical state

---

## Skill 5: Modify the Gallery Frontend

`index.html` is self-contained. No build step.

**What it does:**
- Fetches `apps/manifest.json`
- Deduplicates apps by filename
- Renders category filter pills from manifest keys
- Search: filters by title + description + tags (multi-word, debounced)
- Sort: A-Z, newest first, complexity
- Cards link to `apps/<folder>/<file>`
- Keyboard: `/` focuses search

**To change the gallery**, edit `index.html` directly and push.

---

## Skill 6: Remove an App

```bash
# 1. Delete the file
rm apps/games-puzzles/old-app.html

# 2. Remove its entry from apps/manifest.json
# 3. Decrement the category "count"
# 4. Commit and push
```

---

## Skill 7: Move an App Between Categories

```bash
# 1. Move the file
mv apps/experimental-ai/my-app.html apps/games-puzzles/

# 2. In manifest.json:
#    - Remove entry from old category's "apps" array, decrement "count"
#    - Add entry to new category's "apps" array, increment "count"
# 3. Commit and push
```

---

## Skill 8: Validate Repo Integrity

Run this to check that manifest and filesystem are in sync:

```bash
python3 -c "
import json, os
with open('apps/manifest.json') as f:
    m = json.load(f)
errors = 0
for k, c in m['categories'].items():
    for a in c['apps']:
        path = f\"apps/{c['folder']}/{a['file']}\"
        if not os.path.exists(path):
            print(f'MISSING: {path}')
            errors += 1
    actual = len([f for f in os.listdir(f\"apps/{c['folder']}\") if f.endswith('.html')])
    if actual != c['count']:
        print(f'COUNT MISMATCH: {k} manifest says {c[\"count\"]}, disk has {actual}')
        errors += 1
print(f'Validation: {\"PASS\" if errors == 0 else f\"FAIL ({errors} errors}\"}')
"
```

---

## Skill 9: Create a New Category

1. Create the folder: `mkdir apps/my-category`
2. Add to `apps/manifest.json`:
```json
"my_category_key": {
  "title": "My Category",
  "folder": "my-category",
  "color": "#hexcolor",
  "count": 0,
  "apps": []
}
```
3. The gallery frontend auto-discovers categories from manifest — no `index.html` changes needed.

---

## Things That Will Break the Site

- Putting HTML files in root (root must stay clean)
- Deleting or corrupting `apps/manifest.json`
- Apps that reference external `.js` or `.css` files
- Manifest entries pointing to files that don't exist
- API keys or secrets in any file (GitHub push protection will block)
- Adding directories to root (everything goes under `apps/`)

---

## Skill 10: Auto-Sort Pipeline

A GitHub Action and Python script automatically catches files dropped in root (from the legacy workflow), analyzes their content, renames garbage filenames, categorizes them, moves them to the correct `apps/<category>/` folder, and updates the manifest.

**Automatic:** Runs on every push to `main` that includes `.html` files in root. No manual intervention needed.

**Manual commands:**
```bash
# Dry run — see what would happen without changing anything
python3 scripts/autosort.py --dry-run

# Sort root files into categories
python3 scripts/autosort.py

# Also rename garbage files already in apps/ (a.html -> real-name.html)
python3 scripts/autosort.py --deep-clean
```

**What it does:**
1. Scans root for any `.html` files that aren't `index.html`
2. Reads each file's `<title>`, `<meta description>`, and body content
3. If filename is garbage (`a.html`, `5.html`, `new.html`, etc.), generates a descriptive name from the title
4. Scores content against 9 category keyword rulesets to pick the best category
5. Moves file to `apps/<category>/<clean-name>.html`
6. Adds entry to `apps/manifest.json` with extracted metadata
7. Handles filename collisions by appending `-2`, `-3`, etc.

**There is no "uncategorized" bucket.** Every file gets assigned a real category. If nothing else matches, it goes to `experimental-ai`.

---

## Quick Reference

| Task | Command |
|------|---------|
| View live site | `open https://kody-w.github.io/localFirstTools-main/` |
| Count apps on disk | `find apps -name '*.html' \| wc -l` |
| Count apps in manifest | `python3 -c "import json; m=json.load(open('apps/manifest.json')); print(sum(len(c['apps']) for c in m['categories'].values()))"` |
| Validate sync | See Skill 8 above |
| Local preview | `python3 -m http.server 8000` then visit `http://localhost:8000` |
| Deploy | `git push origin main` (auto-deploys via GitHub Pages) |
