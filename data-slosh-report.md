# Data Slosh Quality Report

Generated: 2026-02-07 17:14:08
Scanner: Data Slosh 19-rule regex scorer (local-only, no AI)

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total files scanned | 526 |
| Files scored | 526 |
| Average score | 79.9 |
| Median score | 82 |
| Highest score | 98 |
| Lowest score | 17 |

## Score Distribution

| Range | Count | Percentage |
|-------|-------|------------|
| 90-100 (Excellent) | 64 | 12.2% |
| 71-89 (Good) | 382 | 72.6% |
| 51-70 (Fair) | 69 | 13.1% |
| 0-50 (Poor) | 11 | 2.1% |

## Category Averages

| Category | Apps | Avg Score | Min | Max |
|----------|------|-----------|-----|-----|
| 3d-immersive | 35 | 76.3 | 62 | 91 |
| audio-music | 40 | 83.3 | 60 | 96 |
| creative-tools | 18 | 82.6 | 58 | 98 |
| experimental-ai | 216 | 80.6 | 17 | 96 |
| games-puzzles | 130 | 77.0 | 24 | 94 |
| generative-art | 29 | 82.9 | 72 | 94 |
| particle-physics | 18 | 81.1 | 65 | 91 |
| visual-art | 40 | 81.6 | 54 | 96 |

## Top Issues (Most Common Failures)

| # | Rule | Severity | Failures | % of Apps |
|---|------|----------|----------|-----------|
| 1 | no-noscript | INFO | 524 | 99.6% |
| 2 | no-aria-labels | INFO | 473 | 89.9% |
| 3 | inline-onclick | INFO | 403 | 76.6% |
| 4 | no-media-queries | INFO | 347 | 66.0% |
| 5 | no-localstorage | WARN | 321 | 61.0% |
| 6 | no-error-handling | WARN | 264 | 50.2% |
| 7 | missing-description | WARN | 201 | 38.2% |
| 8 | missing-input-labels | INFO | 122 | 23.2% |
| 9 | console-log-pollution | WARN | 76 | 14.4% |
| 10 | external-scripts | ERROR | 73 | 13.9% |
| 11 | no-json-export | WARN | 72 | 13.7% |
| 12 | external-styles | ERROR | 17 | 3.2% |
| 13 | cdn-dependencies | ERROR | 16 | 3.0% |
| 14 | missing-viewport | ERROR | 11 | 2.1% |
| 15 | missing-charset | ERROR | 10 | 1.9% |
| 16 | missing-html-lang | WARN | 10 | 1.9% |
| 17 | missing-doctype | ERROR | 9 | 1.7% |
| 18 | missing-title | WARN | 9 | 1.7% |
| 19 | hardcoded-api-keys | WARN | 2 | 0.4% |

## All Files Ranked by Score (Worst First)

| # | File | Category | Score | Errors | Warnings | Info | Failed Rules |
|---|------|----------|-------|--------|----------|------|--------------|
| 1 | apps/experimental-ai/witness-protocol-addon.html | experimental-ai | 17 | 3 | 6 | 4 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +7 more |
| 2 | apps/games-puzzles/frankenship.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 3 | apps/games-puzzles/laws-of-creation.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 4 | apps/games-puzzles/monster-court.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 5 | apps/games-puzzles/noir-detective.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 6 | apps/games-puzzles/rhythm-terrain.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 7 | apps/games-puzzles/rogue-deck-arena.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 8 | apps/games-puzzles/street-food-tycoon.html | games-puzzles | 24 | 3 | 5 | 3 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 9 | apps/experimental-ai/TAROT_SYSTEM_ADDITION.html | experimental-ai | 27 | 3 | 4 | 4 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, +5 more |
| 10 | apps/experimental-ai/hacker-news-simulator.html | experimental-ai | 41 | 3 | 2 | 2 | external-scripts, external-styles, cdn-dependencies, missing-description, no-localstorage, no-aria-labels, +1 more |
| 11 | apps/experimental-ai/chat-application.html | experimental-ai | 46 | 3 | 1 | 2 | external-scripts, external-styles, cdn-dependencies, console-log-pollution, no-noscript, inline-onclick |
| 12 | apps/games-puzzles/pokedex.html | games-puzzles | 51 | 2 | 3 | 2 | missing-charset, missing-viewport, missing-html-lang, missing-description, console-log-pollution, no-noscript, +1 more |
| 13 | apps/experimental-ai/cdn-file-manager.html | experimental-ai | 52 | 2 | 2 | 4 | external-scripts, cdn-dependencies, missing-description, no-localstorage, no-aria-labels, no-noscript, +2 more |
| 14 | apps/games-puzzles/NexusWorlds.html | games-puzzles | 54 | 2 | 2 | 3 | external-scripts, cdn-dependencies, missing-description, console-log-pollution, no-noscript, inline-onclick, +1 more |
| 15 | apps/visual-art/artifact-converter.html | visual-art | 54 | 2 | 2 | 3 | external-scripts, cdn-dependencies, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, +1 more |
| 16 | apps/experimental-ai/ai-companion-hub-enhanced.html | experimental-ai | 56 | 2 | 2 | 2 | external-scripts, external-styles, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 17 | apps/experimental-ai/linux-browser-boot.html | experimental-ai | 56 | 2 | 2 | 2 | external-scripts, cdn-dependencies, no-localstorage, console-log-pollution, no-aria-labels, no-noscript |
| 18 | apps/experimental-ai/magellentic-agents.html | experimental-ai | 56 | 2 | 2 | 2 | external-scripts, external-styles, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 19 | apps/experimental-ai/wristAI.html | experimental-ai | 56 | 2 | 2 | 2 | external-scripts, cdn-dependencies, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 20 | apps/experimental-ai/Agent Workflow System.html | experimental-ai | 57 | 2 | 1 | 4 | external-scripts, external-styles, missing-description, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 21 | apps/creative-tools/data-slosh-tests.html | creative-tools | 58 | 2 | 2 | 1 | external-scripts, external-styles, console-log-pollution, hardcoded-api-keys, inline-onclick |
| 22 | apps/experimental-ai/final-dashboard.html | experimental-ai | 58 | 2 | 2 | 1 | external-scripts, external-styles, missing-description, console-log-pollution, no-noscript |
| 23 | apps/experimental-ai/osm-ecosystem-city.html | experimental-ai | 59 | 2 | 1 | 3 | external-scripts, cdn-dependencies, no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 24 | apps/audio-music/elite_speaking_tracker.html | audio-music | 60 | 1 | 3 | 5 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +3 more |
| 25 | apps/audio-music/youtube-webcam-sync-fixed.html | audio-music | 60 | 1 | 3 | 5 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, +3 more |
| 26 | apps/games-puzzles/m365realplayer.html | games-puzzles | 60 | 1 | 3 | 5 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, +3 more |
| 27 | apps/experimental-ai/mac-migration-assessment-copilot.html | experimental-ai | 61 | 2 | 1 | 2 | external-scripts, external-styles, console-log-pollution, no-noscript, inline-onclick |
| 28 | apps/visual-art/teacher-learner-app.html | visual-art | 61 | 2 | 1 | 2 | external-scripts, external-styles, missing-description, no-noscript, inline-onclick |
| 29 | apps/3d-immersive/cityofHeroes.html | 3d-immersive | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, +2 more |
| 30 | apps/3d-immersive/evomon-world-generator.html | 3d-immersive | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +2 more |
| 31 | apps/3d-immersive/snake3.html | 3d-immersive | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +2 more |
| 32 | apps/experimental-ai/procedural-spider-ik.html | experimental-ai | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +2 more |
| 33 | apps/games-puzzles/ai-companion-hub-interactive-assistant.html | games-puzzles | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, +2 more |
| 34 | apps/games-puzzles/evolution-simulator-2d.html | games-puzzles | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +2 more |
| 35 | apps/games-puzzles/fpspic.html | games-puzzles | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, +2 more |
| 36 | apps/games-puzzles/helicopter-rescue-sim.html | games-puzzles | 62 | 1 | 3 | 4 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +2 more |
| 37 | apps/visual-art/teacher-learner.html | visual-art | 63 | 2 | 1 | 1 | external-scripts, external-styles, missing-description, no-noscript |
| 38 | apps/3d-immersive/drone-simulator.html | 3d-immersive | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +1 more |
| 39 | apps/3d-immersive/gameoflife.html | 3d-immersive | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +1 more |
| 40 | apps/audio-music/bothangles-ios-fixed.html | audio-music | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, +1 more |
| 41 | apps/audio-music/drone-simulator-link-app.html | audio-music | 64 | 1 | 3 | 3 | cdn-dependencies, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +1 more |
| 42 | apps/games-puzzles/dota3.html | games-puzzles | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, +1 more |
| 43 | apps/games-puzzles/racing2.html | games-puzzles | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, +1 more |
| 44 | apps/games-puzzles/reader.html | games-puzzles | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, +1 more |
| 45 | apps/games-puzzles/wave-rider-surfing-game.html | games-puzzles | 64 | 1 | 3 | 3 | external-scripts, missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, +1 more |
| 46 | apps/3d-immersive/ecs-console-3d.html | 3d-immersive | 65 | 1 | 2 | 5 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 47 | apps/3d-immersive/evomon-world.html | 3d-immersive | 65 | 1 | 2 | 5 | external-scripts, missing-description, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 48 | apps/3d-immersive/tile-room-3d.html | 3d-immersive | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 49 | apps/experimental-ai/bloomer.html | experimental-ai | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 50 | apps/experimental-ai/evomon-history-viewer.html | experimental-ai | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 51 | apps/experimental-ai/evomon-lab.html | experimental-ai | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 52 | apps/experimental-ai/workshop.html | experimental-ai | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 53 | apps/games-puzzles/mermaid-viewer.html | games-puzzles | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 54 | apps/games-puzzles/nexus-holographic-companion.html | games-puzzles | 65 | 1 | 2 | 5 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 55 | apps/particle-physics/time-travel-editor.html | particle-physics | 65 | 1 | 2 | 5 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 56 | apps/visual-art/akashic-library.html | visual-art | 65 | 1 | 2 | 5 | external-scripts, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 57 | apps/experimental-ai/magentic-agents-ui.html | experimental-ai | 66 | 1 | 3 | 2 | external-styles, missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript |
| 58 | apps/games-puzzles/3d-world-navigation.html | games-puzzles | 66 | 1 | 3 | 2 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript |
| 59 | apps/games-puzzles/crystal-caves-world.html | games-puzzles | 66 | 1 | 3 | 2 | external-scripts, missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript |
| 60 | apps/3d-immersive/kingdom-defense.html | 3d-immersive | 67 | 1 | 2 | 4 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 61 | apps/experimental-ai/agent-browser.html | experimental-ai | 67 | 1 | 2 | 4 | cdn-dependencies, missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 62 | apps/experimental-ai/evolution-simulator-3d.html | experimental-ai | 67 | 1 | 2 | 4 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 63 | apps/experimental-ai/qr-sharer.html | experimental-ai | 67 | 1 | 2 | 4 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 64 | apps/experimental-ai/task-flow.html | experimental-ai | 67 | 1 | 2 | 4 | missing-viewport, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 65 | apps/games-puzzles/m365UI.html | games-puzzles | 67 | 1 | 2 | 4 | external-scripts, missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 66 | apps/particle-physics/black-hole-descent.html | particle-physics | 67 | 1 | 2 | 4 | external-scripts, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 67 | apps/3d-immersive/app-museum-3d.html | 3d-immersive | 69 | 1 | 2 | 3 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 68 | apps/3d-immersive/pocket-universe.html | 3d-immersive | 69 | 1 | 2 | 3 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 69 | apps/3d-immersive/procedural-city-generator.html | 3d-immersive | 69 | 1 | 2 | 3 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 70 | apps/audio-music/rokos-basilisk.html | audio-music | 69 | 1 | 2 | 3 | cdn-dependencies, no-json-export, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 71 | apps/experimental-ai/data-city.html | experimental-ai | 69 | 1 | 2 | 3 | external-scripts, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 72 | apps/experimental-ai/desktop-download.html | experimental-ai | 69 | 1 | 2 | 3 | cdn-dependencies, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 73 | apps/experimental-ai/neuai-installer-wizard.html | experimental-ai | 69 | 1 | 2 | 3 | cdn-dependencies, no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 74 | apps/experimental-ai/non-euclidean-hallway.html | experimental-ai | 69 | 1 | 2 | 3 | external-scripts, missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 75 | apps/experimental-ai/prompt-broadcast-social.html | experimental-ai | 69 | 1 | 2 | 3 | external-scripts, missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 76 | apps/games-puzzles/racing.html | games-puzzles | 69 | 1 | 2 | 3 | external-scripts, missing-description, console-log-pollution, no-noscript, inline-onclick, missing-input-labels |
| 77 | apps/games-puzzles/star wars galaxies.html | games-puzzles | 69 | 1 | 2 | 3 | external-scripts, missing-description, no-json-export, no-aria-labels, no-noscript, inline-onclick |
| 78 | apps/visual-art/nexus.html | visual-art | 69 | 1 | 2 | 3 | external-scripts, missing-description, console-log-pollution, no-noscript, inline-onclick, missing-input-labels |
| 79 | apps/experimental-ai/book-factory-world.html | experimental-ai | 70 | 1 | 1 | 5 | external-scripts, missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 80 | apps/visual-art/doodle-to-world.html | visual-art | 70 | 1 | 1 | 5 | external-scripts, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 81 | apps/3d-immersive/feedShyworm4.html | 3d-immersive | 71 | 1 | 2 | 2 | external-scripts, missing-description, no-json-export, no-aria-labels, no-noscript |
| 82 | apps/experimental-ai/emdr-complete.html | experimental-ai | 71 | 1 | 2 | 2 | external-scripts, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 83 | apps/experimental-ai/leviathan-omniverse-v109-mobile-optimized.html | experimental-ai | 71 | 1 | 2 | 2 | external-scripts, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 84 | apps/experimental-ai/splitspace.html | experimental-ai | 71 | 1 | 2 | 2 | external-styles, missing-description, console-log-pollution, no-aria-labels, no-noscript |
| 85 | apps/experimental-ai/terminal-viewer.html | experimental-ai | 71 | 1 | 2 | 2 | external-styles, missing-description, no-localstorage, no-aria-labels, no-noscript |
| 86 | apps/3d-immersive/runecraft-3d.html | 3d-immersive | 72 | 1 | 1 | 4 | external-scripts, missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 87 | apps/experimental-ai/copilot-agent-store.html | experimental-ai | 72 | 1 | 1 | 4 | cdn-dependencies, no-localstorage, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 88 | apps/experimental-ai/influence-mastery-app.html | experimental-ai | 72 | 0 | 4 | 4 | missing-description, no-json-export, no-error-handling, console-log-pollution, no-aria-labels, no-noscript, +2 more |
| 89 | apps/experimental-ai/memory-palace.html | experimental-ai | 72 | 1 | 1 | 4 | external-scripts, missing-description, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 90 | apps/experimental-ai/workflow-executor-app.html | experimental-ai | 72 | 1 | 1 | 4 | external-styles, missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 91 | apps/experimental-ai/wowMon_detail_view.html | experimental-ai | 72 | 0 | 4 | 4 | missing-description, no-json-export, no-error-handling, console-log-pollution, no-aria-labels, no-noscript, +2 more |
| 92 | apps/experimental-ai/zero-g-station-builder.html | experimental-ai | 72 | 1 | 1 | 4 | external-scripts, console-log-pollution, no-media-queries, no-noscript, inline-onclick, missing-input-labels |
| 93 | apps/games-puzzles/space-defender-xbox-controller.html | games-puzzles | 72 | 0 | 4 | 4 | missing-description, no-localstorage, no-error-handling, console-log-pollution, no-media-queries, no-aria-labels, +2 more |
| 94 | apps/generative-art/gpu-fluid-simulator.html | generative-art | 72 | 0 | 4 | 4 | missing-description, no-localstorage, no-error-handling, console-log-pollution, no-aria-labels, no-noscript, +2 more |
| 95 | apps/visual-art/claude-subagents-tutorial.html | visual-art | 72 | 0 | 4 | 4 | missing-description, no-localstorage, no-error-handling, hardcoded-api-keys, no-aria-labels, no-noscript, +2 more |
| 96 | apps/visual-art/pipboy-interface.html | visual-art | 72 | 1 | 1 | 4 | external-scripts, missing-description, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 97 | apps/experimental-ai/executive-memory-visualizer.html | experimental-ai | 74 | 1 | 1 | 3 | external-styles, missing-description, no-aria-labels, no-noscript, inline-onclick |
| 98 | apps/3d-immersive/starfield-traders.html | 3d-immersive | 75 | 0 | 3 | 5 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 99 | apps/creative-tools/markdown-editor-live.html | creative-tools | 75 | 0 | 3 | 5 | no-json-export, no-error-handling, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 100 | apps/games-puzzles/neuromancer.html | games-puzzles | 75 | 0 | 3 | 5 | missing-description, no-json-export, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +2 more |
| 101 | apps/experimental-ai/custom-copilot-ui.html | experimental-ai | 76 | 1 | 1 | 2 | external-styles, missing-description, no-noscript, inline-onclick |
| 102 | apps/experimental-ai/genesis-ark-odyssey.html | experimental-ai | 76 | 1 | 1 | 2 | external-scripts, no-localstorage, no-media-queries, no-noscript |
| 103 | apps/experimental-ai/windows95-emulator.html | experimental-ai | 76 | 1 | 1 | 2 | cdn-dependencies, console-log-pollution, no-noscript, inline-onclick |
| 104 | apps/particle-physics/ecosystem-city.html | particle-physics | 76 | 1 | 1 | 2 | external-scripts, console-log-pollution, no-noscript, inline-onclick |
| 105 | apps/creative-tools/task-tracker.html | creative-tools | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 106 | apps/experimental-ai/TAROT_DEMO.html | experimental-ai | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 107 | apps/experimental-ai/agent-deployment-prototype.html | experimental-ai | 77 | 0 | 3 | 4 | missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 108 | apps/experimental-ai/dynamics365-email-automation.html | experimental-ai | 77 | 0 | 3 | 4 | missing-description, no-json-export, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 109 | apps/experimental-ai/github-gallery-setup.html | experimental-ai | 77 | 0 | 3 | 4 | missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 110 | apps/experimental-ai/severance-refiner.html | experimental-ai | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 111 | apps/games-puzzles/card-counting-trainer.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 112 | apps/games-puzzles/chronoscape.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 113 | apps/games-puzzles/complete-retroplay-console-ios.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 114 | apps/games-puzzles/gravity-court.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 115 | apps/games-puzzles/hearthstone-card-battle.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 116 | apps/games-puzzles/memory-palace.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 117 | apps/games-puzzles/murder-board.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 118 | apps/games-puzzles/parallax-dimensions.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 119 | apps/games-puzzles/pocket-civ.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 120 | apps/games-puzzles/poker-trainer-continued.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 121 | apps/games-puzzles/the-trial.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 122 | apps/games-puzzles/wowmon-campaign-mode.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 123 | apps/games-puzzles/wowmon-crystal-edition.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 124 | apps/games-puzzles/zork-engine.html | games-puzzles | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 125 | apps/visual-art/claude-subagents-tutorial-continued.html | visual-art | 77 | 0 | 3 | 4 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, +1 more |
| 126 | apps/experimental-ai/nano-banana-chat-app.html | experimental-ai | 78 | 1 | 1 | 1 | cdn-dependencies, console-log-pollution, no-noscript |
| 127 | apps/3d-immersive/abyssal-depths.html | 3d-immersive | 79 | 0 | 3 | 3 | missing-description, no-json-export, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 128 | apps/3d-immersive/chess-academy-3d.html | 3d-immersive | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 129 | apps/3d-immersive/procedural-planet-generator.html | 3d-immersive | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 130 | apps/creative-tools/buzzsaw-dashboard.html | creative-tools | 79 | 0 | 3 | 3 | missing-description, no-json-export, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 131 | apps/creative-tools/circuit-simulator.html | creative-tools | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 132 | apps/experimental-ai/agent-collaboration.html | experimental-ai | 79 | 1 | 0 | 3 | external-styles, no-aria-labels, no-noscript, inline-onclick |
| 133 | apps/experimental-ai/ai-simulation-sales-demo.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-json-export, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 134 | apps/experimental-ai/consolidated-ai-tools.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 135 | apps/experimental-ai/cyber-timer.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 136 | apps/experimental-ai/dual-camera-recorder-fixed.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 137 | apps/experimental-ai/extension-download.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 138 | apps/experimental-ai/infinite-city-wfc.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 139 | apps/experimental-ai/linux-terminal-emulator.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 140 | apps/experimental-ai/procedural-solar-system.html | experimental-ai | 79 | 1 | 0 | 3 | external-scripts, no-noscript, inline-onclick, missing-input-labels |
| 141 | apps/experimental-ai/reality-corruption-simulator.html | experimental-ai | 79 | 0 | 3 | 3 | no-localstorage, no-error-handling, console-log-pollution, no-media-queries, no-noscript, inline-onclick |
| 142 | apps/experimental-ai/vibe-terminal.html | experimental-ai | 79 | 0 | 3 | 3 | missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, missing-input-labels |
| 143 | apps/games-puzzles/gameboy-emulator.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 144 | apps/games-puzzles/neon-moba.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 145 | apps/games-puzzles/recursion.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 146 | apps/games-puzzles/signal-lost.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, missing-input-labels |
| 147 | apps/games-puzzles/steamdeck-game.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 148 | apps/games-puzzles/the-vote.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 149 | apps/games-puzzles/thousand-suns.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 150 | apps/games-puzzles/war-card-game-tutor.html | games-puzzles | 79 | 0 | 3 | 3 | no-localstorage, no-error-handling, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 151 | apps/games-puzzles/wetware.html | games-puzzles | 79 | 0 | 3 | 3 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript, missing-input-labels |
| 152 | apps/visual-art/physics-playground-lab.html | visual-art | 79 | 0 | 3 | 3 | missing-description, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 153 | apps/visual-art/solitaire-tutorial-game.html | visual-art | 79 | 0 | 3 | 3 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 154 | apps/3d-immersive/gameboy-clone.html | 3d-immersive | 80 | 0 | 2 | 5 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 155 | apps/audio-music/youtube-webcam-recorder.html | audio-music | 80 | 0 | 2 | 5 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 156 | apps/creative-tools/ray-march-studio.html | creative-tools | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 157 | apps/experimental-ai/consciousness-backup-terminal.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 158 | apps/experimental-ai/data-structures-visualizer.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 159 | apps/experimental-ai/inspection-ritual.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 160 | apps/experimental-ai/library-of-babel.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 161 | apps/experimental-ai/neural-builder.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 162 | apps/experimental-ai/offline-internet-simulator.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 163 | apps/experimental-ai/p2p-whiteboard.html | experimental-ai | 80 | 0 | 2 | 5 | no-localstorage, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 164 | apps/experimental-ai/senbazuru-sanctuary.html | experimental-ai | 80 | 0 | 2 | 5 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 165 | apps/experimental-ai/text-file-splitter.html | experimental-ai | 80 | 0 | 2 | 5 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 166 | apps/games-puzzles/memory-training-game.html | games-puzzles | 80 | 0 | 2 | 5 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 167 | apps/games-puzzles/regex-defender.html | games-puzzles | 80 | 0 | 2 | 5 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 168 | apps/games-puzzles/xwing-mmo-game.html | games-puzzles | 80 | 0 | 2 | 5 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 169 | apps/generative-art/pangaea-poem-fragmenter.html | generative-art | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 170 | apps/generative-art/thought-lightning.html | generative-art | 80 | 0 | 2 | 5 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 171 | apps/visual-art/forgetting-machine.html | visual-art | 80 | 0 | 2 | 5 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, +1 more |
| 172 | apps/3d-immersive/cubecrusher.html | 3d-immersive | 81 | 0 | 3 | 2 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript |
| 173 | apps/3d-immersive/dreamwalker.html | 3d-immersive | 81 | 0 | 3 | 2 | missing-description, no-json-export, no-error-handling, no-aria-labels, no-noscript |
| 174 | apps/audio-music/music-theory-visualizer.html | audio-music | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 175 | apps/experimental-ai/breathwork.html | experimental-ai | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 176 | apps/experimental-ai/dynamic-agent-workflow.html | experimental-ai | 81 | 0 | 3 | 2 | missing-description, no-localstorage, console-log-pollution, no-media-queries, no-noscript |
| 177 | apps/experimental-ai/executive-presentation-slide2.html | experimental-ai | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 178 | apps/experimental-ai/presentation-slide-responsive-updated.html | experimental-ai | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 179 | apps/games-puzzles/wowmon-card-game-demo.html | games-puzzles | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 180 | apps/games-puzzles/wowmon-card-game-design-demo-improved.html | games-puzzles | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 181 | apps/visual-art/rainbow-svg-path.html | visual-art | 81 | 0 | 3 | 2 | missing-description, no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 182 | apps/3d-immersive/fractal-city-builder.html | 3d-immersive | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 183 | apps/3d-immersive/neural-cellular-automata.html | 3d-immersive | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 184 | apps/3d-immersive/ray-march-studio-2.html | 3d-immersive | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 185 | apps/3d-immersive/ray-march-studio.html | 3d-immersive | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 186 | apps/audio-music/audio-visualizer-universe.html | audio-music | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 187 | apps/audio-music/blind-navigator.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 188 | apps/audio-music/cylinder-composer.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 189 | apps/audio-music/drum-machine-808.html | audio-music | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 190 | apps/audio-music/dune-symphony.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 191 | apps/audio-music/infinite-cave-roguelike-3d.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 192 | apps/audio-music/memory-crease.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 193 | apps/audio-music/music-theory-trainer.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 194 | apps/audio-music/strange-attractor-hypnosis.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 195 | apps/audio-music/synesthesia-paintbrush.html | audio-music | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 196 | apps/creative-tools/cloud-os.html | creative-tools | 82 | 0 | 2 | 4 | missing-description, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 197 | apps/creative-tools/markdown-editor.html | creative-tools | 82 | 0 | 2 | 4 | missing-description, no-error-handling, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 198 | apps/experimental-ai/abyssal-symphony.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 199 | apps/experimental-ai/algorithm-visualizer-pro.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 200 | apps/experimental-ai/amber-resonance.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 201 | apps/experimental-ai/antikythera-mechanism.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 202 | apps/experimental-ai/atmospheric-sculptor.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 203 | apps/experimental-ai/bioluminescent-depth-explorer.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 204 | apps/experimental-ai/canyon-composer.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 205 | apps/experimental-ai/confluence.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 206 | apps/experimental-ai/crm-questionnaire-viewer.html | experimental-ai | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 207 | apps/experimental-ai/css-animation-builder.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 208 | apps/experimental-ai/determinism-debugger.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 209 | apps/experimental-ai/deterministic-universe-explorer.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 210 | apps/experimental-ai/digital-tulpa.html | experimental-ai | 82 | 0 | 2 | 4 | no-json-export, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 211 | apps/experimental-ai/emotion-lattice.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 212 | apps/experimental-ai/evolution-simulator.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 213 | apps/experimental-ai/firefly-collector.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 214 | apps/experimental-ai/fractal-explorer-interactive.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 215 | apps/experimental-ai/frost-glass.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 216 | apps/experimental-ai/geode-crack.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 217 | apps/experimental-ai/glacial-core.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 218 | apps/experimental-ai/hourglass-choice.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 219 | apps/experimental-ai/hourglass-terrarium.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 220 | apps/experimental-ai/imprint-erosion.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 221 | apps/experimental-ai/inception-globe-tower.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 222 | apps/experimental-ai/infinite-city.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 223 | apps/experimental-ai/isobar-pressure.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 224 | apps/experimental-ai/lagrange-point-garden.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 225 | apps/experimental-ai/lava-blobs.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 226 | apps/experimental-ai/liminal-drift-atlas.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 227 | apps/experimental-ai/local-browser.html | experimental-ai | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 228 | apps/experimental-ai/membrane.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 229 | apps/experimental-ai/memory-layers.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 230 | apps/experimental-ai/mycelium-network-builder.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 231 | apps/experimental-ai/neon-archaeology.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 232 | apps/experimental-ai/neural-weave.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 233 | apps/experimental-ai/omni-writer.html | experimental-ai | 82 | 0 | 2 | 4 | missing-description, console-log-pollution, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 234 | apps/experimental-ai/pendulum-wave.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 235 | apps/experimental-ai/primordial-soup.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 236 | apps/experimental-ai/prism-refract.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 237 | apps/experimental-ai/psychometric-isobars.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 238 | apps/experimental-ai/ray-march-studio.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 239 | apps/experimental-ai/resonance-threads.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 240 | apps/experimental-ai/retrograde-garden.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 241 | apps/experimental-ai/shadow-story-automaton.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 242 | apps/experimental-ai/simulated-ancestor.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 243 | apps/experimental-ai/snap-message-app.html | experimental-ai | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 244 | apps/experimental-ai/snowflake-symmetry-studio.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 245 | apps/experimental-ai/stalactite-time-machine.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 246 | apps/experimental-ai/stratified-echo.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 247 | apps/experimental-ai/surface-tension.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 248 | apps/experimental-ai/sympathetic-reveal.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 249 | apps/experimental-ai/text-to-speech-choir.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 250 | apps/experimental-ai/timezone-meeting-planner.html | experimental-ai | 82 | 0 | 2 | 4 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 251 | apps/experimental-ai/tree-chronicle.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 252 | apps/experimental-ai/typographic-terrarium.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 253 | apps/experimental-ai/vacuum-tube-meditation.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 254 | apps/experimental-ai/vestigial-automata.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 255 | apps/experimental-ai/windows-95-ai-agent-autonomous-desktop-controller.html | experimental-ai | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 256 | apps/games-puzzles/colony-survival.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 257 | apps/games-puzzles/consciousness-consensus.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 258 | apps/games-puzzles/cursor-wars.html | games-puzzles | 82 | 0 | 2 | 4 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 259 | apps/games-puzzles/ecs-game-engine.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 260 | apps/games-puzzles/flesh-machine.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 261 | apps/games-puzzles/hearthstone-spectator-mode.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 262 | apps/games-puzzles/hypnagogic-garden.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 263 | apps/games-puzzles/hypnagogic-typewriter.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 264 | apps/games-puzzles/infernal-trader.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 265 | apps/games-puzzles/infinite-cave-roguelike-2.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 266 | apps/games-puzzles/infinite-cave-roguelike-3d.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 267 | apps/games-puzzles/infinite-cave-roguelike.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 268 | apps/games-puzzles/littoral-lexicon.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 269 | apps/games-puzzles/loom-of-the-void.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 270 | apps/games-puzzles/mitochondria-tycoon.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 271 | apps/games-puzzles/murder-mystery.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 272 | apps/games-puzzles/palboids-game.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 273 | apps/games-puzzles/paradox-engine.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 274 | apps/games-puzzles/phantom-protocol.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-error-handling, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 275 | apps/games-puzzles/pixel-dungeon-crawler.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 276 | apps/games-puzzles/recursive-ziggurat.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 277 | apps/games-puzzles/reverse-entropy-garden.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 278 | apps/games-puzzles/rube-goldberg.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 279 | apps/games-puzzles/schrodingers-garden.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 280 | apps/games-puzzles/signal-degradation-simulator.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 281 | apps/games-puzzles/spore-mind.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 282 | apps/games-puzzles/the-price.html | games-puzzles | 82 | 0 | 2 | 4 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 283 | apps/games-puzzles/uncooperative-form.html | games-puzzles | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 284 | apps/games-puzzles/wowMon-survival.html | games-puzzles | 82 | 0 | 2 | 4 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 285 | apps/generative-art/broken-broadcast.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 286 | apps/generative-art/cathedral-light-composer.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 287 | apps/generative-art/ferrofluid-wordsmith.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 288 | apps/generative-art/frozen-symmetry.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 289 | apps/generative-art/genetic-art-breeder.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 290 | apps/generative-art/gravity-echoes.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 291 | apps/generative-art/invisible-strings.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 292 | apps/generative-art/lunar-drift.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 293 | apps/generative-art/lunar-poet.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 294 | apps/generative-art/martyrdom-bloom.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 295 | apps/generative-art/membrane-drift.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 296 | apps/generative-art/morning-dew-canvas.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 297 | apps/generative-art/patina-forge.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 298 | apps/generative-art/phantom-stars.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 299 | apps/generative-art/phosphorescent-revealer.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 300 | apps/generative-art/quill-and-curve.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 301 | apps/generative-art/ruined-bloom.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 302 | apps/generative-art/rust-memory.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 303 | apps/generative-art/smoke-words.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 304 | apps/generative-art/thought-cascade.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 305 | apps/generative-art/umbral-genesis.html | generative-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 306 | apps/particle-physics/fabric-sculptor.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 307 | apps/particle-physics/gravity-orbit-simulator.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 308 | apps/particle-physics/lunar-breath.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 309 | apps/particle-physics/marionette-physics.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 310 | apps/particle-physics/mirage-simulator.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 311 | apps/particle-physics/quantum-immortality-brancher.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 312 | apps/particle-physics/spectral-erosion.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 313 | apps/particle-physics/suminagashi-dreams.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 314 | apps/particle-physics/wind-garden.html | particle-physics | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 315 | apps/visual-art/canvas-svg-graphics-workshop.html | visual-art | 82 | 0 | 2 | 4 | no-json-export, console-log-pollution, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 316 | apps/visual-art/fluid-dynamics-simulator.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 317 | apps/visual-art/gravity-well-sandbox.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 318 | apps/visual-art/infinite-card-catalog.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 319 | apps/visual-art/magnetic-field-painter.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 320 | apps/visual-art/palimpsest-engine.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 321 | apps/visual-art/particle-life-simulator.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 322 | apps/visual-art/phosphor-pattern-painter.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 323 | apps/visual-art/pigment-stratigraphics.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 324 | apps/visual-art/timezone-converter-tool.html | visual-art | 82 | 0 | 2 | 4 | missing-description, no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 325 | apps/visual-art/vector-drawing-studio.html | visual-art | 82 | 0 | 2 | 4 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 326 | apps/3d-immersive/last-signal.html | 3d-immersive | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-aria-labels, no-noscript, inline-onclick |
| 327 | apps/3d-immersive/neon-district-rpg.html | 3d-immersive | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-aria-labels, no-noscript, inline-onclick |
| 328 | apps/3d-immersive/quantum-ninja.html | 3d-immersive | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 329 | apps/audio-music/aurora-veil-composer.html | audio-music | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 330 | apps/audio-music/infinite-bubble-wrap.html | audio-music | 84 | 0 | 2 | 3 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 331 | apps/audio-music/melting-clock-composer.html | audio-music | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 332 | apps/audio-music/phantom-recess.html | audio-music | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 333 | apps/audio-music/temporal-binding-glitch.html | audio-music | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 334 | apps/creative-tools/game-rankings.html | creative-tools | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 335 | apps/creative-tools/wordpress-crawler.html | creative-tools | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-media-queries, no-noscript, inline-onclick |
| 336 | apps/experimental-ai/ant-farm-ultra.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 337 | apps/experimental-ai/automated-actions-ui.html | experimental-ai | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-media-queries, no-noscript, inline-onclick |
| 338 | apps/experimental-ai/cellular-sandpile.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 339 | apps/experimental-ai/conspiracy-cooking-show.html | experimental-ai | 84 | 0 | 2 | 3 | no-json-export, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 340 | apps/experimental-ai/gas-station-3am.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 341 | apps/experimental-ai/infinite-hotel.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 342 | apps/experimental-ai/jim-rohn-journal-app.html | experimental-ai | 84 | 0 | 2 | 3 | missing-description, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 343 | apps/experimental-ai/local-first-db-sync.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 344 | apps/experimental-ai/localfirst-magazine-2025-Q1.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 345 | apps/experimental-ai/marginalia-menagerie.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 346 | apps/experimental-ai/mcp-registry.html | experimental-ai | 84 | 0 | 2 | 3 | missing-description, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 347 | apps/experimental-ai/neural-network-playground.html | experimental-ai | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 348 | apps/experimental-ai/picasso-bowl.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 349 | apps/experimental-ai/presentation_app_final.html | experimental-ai | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 350 | apps/experimental-ai/rainy-night-neon-noir.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 351 | apps/experimental-ai/tesseract-4d-rotator.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 352 | apps/experimental-ai/typing-speed-test.html | experimental-ai | 84 | 0 | 2 | 3 | no-json-export, no-error-handling, no-aria-labels, no-noscript, missing-input-labels |
| 353 | apps/experimental-ai/vaporwave-city-flyover.html | experimental-ai | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 354 | apps/games-puzzles/aero-architect.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 355 | apps/games-puzzles/chess-engine.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 356 | apps/games-puzzles/chroma-breach.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 357 | apps/games-puzzles/deja-vu-corridor.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 358 | apps/games-puzzles/dream-auction.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript |
| 359 | apps/games-puzzles/ecs-emulator-console.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 360 | apps/games-puzzles/epoch-civilization.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript |
| 361 | apps/games-puzzles/god-complex.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript |
| 362 | apps/games-puzzles/mycelium-wars.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript |
| 363 | apps/games-puzzles/pokemon-type-calculator.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-aria-labels, no-noscript, inline-onclick |
| 364 | apps/games-puzzles/procedural-infinite-city.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 365 | apps/games-puzzles/quantum-observer.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 366 | apps/games-puzzles/roguelike-dungeon.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-aria-labels, no-noscript, inline-onclick |
| 367 | apps/games-puzzles/sentient.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-json-export, no-aria-labels, no-noscript, inline-onclick |
| 368 | apps/games-puzzles/sky-pirate.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 369 | apps/games-puzzles/tron-lightcycles.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 370 | apps/games-puzzles/workshop_html_pages.html | games-puzzles | 84 | 0 | 2 | 3 | missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 371 | apps/games-puzzles/wowMon-autobattler-design.html | games-puzzles | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 372 | apps/games-puzzles/zombie-survival.html | games-puzzles | 84 | 0 | 2 | 3 | no-json-export, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 373 | apps/generative-art/bioluminescent-depths.html | generative-art | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 374 | apps/particle-physics/cosmic-web-universe.html | particle-physics | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 375 | apps/particle-physics/flocking-boids.html | particle-physics | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 376 | apps/particle-physics/lava-lamp-lab.html | particle-physics | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 377 | apps/particle-physics/ragdoll-physics.html | particle-physics | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 378 | apps/visual-art/crease-memory-theater.html | visual-art | 84 | 0 | 2 | 3 | no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 379 | apps/3d-immersive/complete-retroplay-console.html | 3d-immersive | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 380 | apps/3d-immersive/voxel-world-builder.html | 3d-immersive | 85 | 0 | 1 | 5 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 381 | apps/audio-music/air-hockey-p2p.html | audio-music | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 382 | apps/audio-music/chirp-data-modem.html | audio-music | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 383 | apps/creative-tools/spreadsheet-app.html | creative-tools | 85 | 0 | 1 | 5 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 384 | apps/creative-tools/the-architect.html | creative-tools | 85 | 0 | 1 | 5 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 385 | apps/experimental-ai/accordion-memories.html | experimental-ai | 85 | 0 | 1 | 5 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 386 | apps/experimental-ai/api-request-tester.html | experimental-ai | 85 | 0 | 1 | 5 | no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 387 | apps/experimental-ai/local-first-crdt-database.html | experimental-ai | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 388 | apps/experimental-ai/meeting-cost-calculator.html | experimental-ai | 85 | 0 | 1 | 5 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 389 | apps/experimental-ai/schrodingers-todo.html | experimental-ai | 85 | 0 | 1 | 5 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 390 | apps/experimental-ai/sneakernet-messenger.html | experimental-ai | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 391 | apps/games-puzzles/browser-os.html | games-puzzles | 85 | 0 | 1 | 5 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 392 | apps/games-puzzles/creature-arena.html | games-puzzles | 85 | 0 | 1 | 5 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 393 | apps/games-puzzles/n64-arcade-console.html | games-puzzles | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 394 | apps/games-puzzles/p2p-arcade-console.html | games-puzzles | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 395 | apps/visual-art/chart-builder-pro.html | visual-art | 85 | 0 | 1 | 5 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 396 | apps/3d-immersive/infinite-city.html | 3d-immersive | 86 | 0 | 2 | 2 | missing-description, no-json-export, no-aria-labels, no-noscript |
| 397 | apps/3d-immersive/sky-realms-game.html | 3d-immersive | 86 | 0 | 2 | 2 | no-json-export, console-log-pollution, no-noscript, inline-onclick |
| 398 | apps/audio-music/memory-vault.html | audio-music | 86 | 0 | 2 | 2 | no-localstorage, console-log-pollution, no-noscript, inline-onclick |
| 399 | apps/creative-tools/post-template.html | creative-tools | 86 | 0 | 2 | 2 | no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 400 | apps/experimental-ai/ant-farm-simulation.html | experimental-ai | 86 | 0 | 2 | 2 | no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 401 | apps/experimental-ai/lorem-ipsum-generator.html | experimental-ai | 86 | 0 | 2 | 2 | no-json-export, no-error-handling, no-aria-labels, no-noscript |
| 402 | apps/experimental-ai/magnetic-agents-ui.html | experimental-ai | 86 | 0 | 2 | 2 | missing-description, no-localstorage, no-media-queries, no-noscript |
| 403 | apps/games-puzzles/babel.html | games-puzzles | 86 | 0 | 2 | 2 | missing-description, no-json-export, no-noscript, inline-onclick |
| 404 | apps/games-puzzles/deep-state.html | games-puzzles | 86 | 0 | 2 | 2 | missing-description, no-json-export, no-media-queries, no-noscript |
| 405 | apps/particle-physics/physics-simulator-lab.html | particle-physics | 86 | 0 | 2 | 2 | no-localstorage, no-error-handling, no-aria-labels, no-noscript |
| 406 | apps/3d-immersive/infinite-cave-roguelike-3d.html | 3d-immersive | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 407 | apps/audio-music/ghost-frequency-scanner.html | audio-music | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 408 | apps/audio-music/step-sequencer-pro.html | audio-music | 87 | 0 | 1 | 4 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 409 | apps/audio-music/wave-music-composer.html | audio-music | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 410 | apps/audio-music/webcam-theremin.html | audio-music | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 411 | apps/creative-tools/collaborative-whiteboard.html | creative-tools | 87 | 0 | 1 | 4 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 412 | apps/creative-tools/pixel-art-studio.html | creative-tools | 87 | 0 | 1 | 4 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 413 | apps/experimental-ai/brain-thought-simulator.html | experimental-ai | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 414 | apps/experimental-ai/cellular-multiverse.html | experimental-ai | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 415 | apps/experimental-ai/color-palette-generator.html | experimental-ai | 87 | 0 | 1 | 4 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 416 | apps/experimental-ai/dynamics365-simulator.html | experimental-ai | 87 | 0 | 1 | 4 | console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 417 | apps/experimental-ai/fractal-os.html | experimental-ai | 87 | 0 | 1 | 4 | no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 418 | apps/experimental-ai/note-taking-rich-text-editor.html | experimental-ai | 87 | 0 | 1 | 4 | no-error-handling, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 419 | apps/experimental-ai/prompt-library.html | experimental-ai | 87 | 0 | 1 | 4 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 420 | apps/experimental-ai/recursive-dream-machine.html | experimental-ai | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 421 | apps/experimental-ai/regex-master-interactive.html | experimental-ai | 87 | 0 | 1 | 4 | no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 422 | apps/experimental-ai/self-aware-loading-screen.html | experimental-ai | 87 | 0 | 1 | 4 | console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 423 | apps/experimental-ai/shader-playground.html | experimental-ai | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, missing-input-labels |
| 424 | apps/experimental-ai/universal-data-transformer.html | experimental-ai | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 425 | apps/games-puzzles/echo-chamber.html | games-puzzles | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 426 | apps/games-puzzles/evomon-adventure.html | games-puzzles | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 427 | apps/games-puzzles/infinite-cave-roguelike-3d-2.html | games-puzzles | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 428 | apps/games-puzzles/pocket-creature.html | games-puzzles | 87 | 0 | 1 | 4 | missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 429 | apps/games-puzzles/quantum-chess.html | games-puzzles | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 430 | apps/games-puzzles/runecraft-clone.html | games-puzzles | 87 | 0 | 1 | 4 | missing-description, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 431 | apps/games-puzzles/tab-hydra.html | games-puzzles | 87 | 0 | 1 | 4 | no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 432 | apps/visual-art/ascii-video-converter.html | visual-art | 87 | 0 | 1 | 4 | no-localstorage, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 433 | apps/visual-art/database-designer-erd.html | visual-art | 87 | 0 | 1 | 4 | no-error-handling, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 434 | apps/visual-art/localstorage-academy-tutorial.html | visual-art | 87 | 0 | 1 | 4 | console-log-pollution, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 435 | apps/visual-art/recursive-dream-studio.html | visual-art | 87 | 0 | 1 | 4 | console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 436 | apps/games-puzzles/steamdeck-game-store.html | games-puzzles | 88 | 0 | 2 | 1 | missing-description, console-log-pollution, no-noscript |
| 437 | apps/3d-immersive/audio-reactive-fractal.html | 3d-immersive | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 438 | apps/audio-music/bio-rhythm-orchestra.html | audio-music | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 439 | apps/audio-music/firefly-sync-meditation.html | audio-music | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 440 | apps/audio-music/loop-station-beatmaker.html | audio-music | 89 | 0 | 1 | 3 | no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 441 | apps/audio-music/synth-daw-studio.html | audio-music | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 442 | apps/creative-tools/data-dashboard.html | creative-tools | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 443 | apps/experimental-ai/autonomous-book-factory.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, missing-input-labels |
| 444 | apps/experimental-ai/compressed-book-factory.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 445 | apps/experimental-ai/digital-twin-keeper.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 446 | apps/experimental-ai/document-time-machine.html | experimental-ai | 89 | 0 | 1 | 3 | console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 447 | apps/experimental-ai/ghostwriter.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 448 | apps/experimental-ai/interactive-code-playground.html | experimental-ai | 89 | 0 | 1 | 3 | console-log-pollution, no-aria-labels, no-noscript, missing-input-labels |
| 449 | apps/experimental-ai/landmark-art-studio.html | experimental-ai | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 450 | apps/experimental-ai/lowcode-workflow-translator.html | experimental-ai | 89 | 0 | 1 | 3 | no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 451 | apps/experimental-ai/noteforge.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 452 | apps/experimental-ai/record-review-app.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 453 | apps/experimental-ai/sneaker-net-social.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 454 | apps/experimental-ai/sneakernet-complete.html | experimental-ai | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 455 | apps/experimental-ai/symbiotic-slime-mold-network.html | experimental-ai | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-aria-labels, no-noscript |
| 456 | apps/games-puzzles/chip8-emulator.html | games-puzzles | 89 | 0 | 1 | 3 | no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 457 | apps/games-puzzles/monster-truck-game.html | games-puzzles | 89 | 0 | 1 | 3 | missing-description, no-noscript, inline-onclick, missing-input-labels |
| 458 | apps/games-puzzles/svg-art-turing-test.html | games-puzzles | 89 | 0 | 1 | 3 | no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 459 | apps/generative-art/neural-cosmos-arena.html | generative-art | 89 | 0 | 1 | 3 | no-localstorage, no-media-queries, no-noscript, inline-onclick |
| 460 | apps/visual-art/ant-farm-3d.html | visual-art | 89 | 0 | 1 | 3 | no-localstorage, no-aria-labels, no-noscript, inline-onclick |
| 461 | apps/visual-art/github-sync-manager.html | visual-art | 89 | 0 | 1 | 3 | missing-description, no-aria-labels, no-noscript, inline-onclick |
| 462 | apps/visual-art/local-first-starter-template.html | visual-art | 89 | 0 | 1 | 3 | no-json-export, no-noscript, inline-onclick, missing-input-labels |
| 463 | apps/audio-music/emotional-typewriter.html | audio-music | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 464 | apps/audio-music/whisper-topography.html | audio-music | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 465 | apps/creative-tools/voice-home-dashboard.html | creative-tools | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 466 | apps/experimental-ai/indoor-navigator.html | experimental-ai | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 467 | apps/experimental-ai/memory-erosion-garden.html | experimental-ai | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 468 | apps/experimental-ai/tab-pet.html | experimental-ai | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 469 | apps/games-puzzles/decision-matrix.html | games-puzzles | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 470 | apps/games-puzzles/ecs-console.html | games-puzzles | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 471 | apps/games-puzzles/retro-console.html | games-puzzles | 90 | 0 | 0 | 5 | no-media-queries, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 472 | apps/3d-immersive/cellular-civilization.html | 3d-immersive | 91 | 0 | 1 | 2 | no-localstorage, no-aria-labels, no-noscript |
| 473 | apps/experimental-ai/colony-mind.html | experimental-ai | 91 | 0 | 1 | 2 | console-log-pollution, no-noscript, inline-onclick |
| 474 | apps/experimental-ai/timer-stopwatch-simple.html | experimental-ai | 91 | 0 | 1 | 2 | no-json-export, no-aria-labels, no-noscript |
| 475 | apps/games-puzzles/code-quest.html | games-puzzles | 91 | 0 | 1 | 2 | console-log-pollution, no-noscript, inline-onclick |
| 476 | apps/games-puzzles/wowMon.html | games-puzzles | 91 | 0 | 1 | 2 | console-log-pollution, no-noscript, inline-onclick |
| 477 | apps/generative-art/fractal-explorer.html | generative-art | 91 | 0 | 1 | 2 | missing-description, no-aria-labels, no-noscript |
| 478 | apps/particle-physics/tectonic-civilization.html | particle-physics | 91 | 0 | 1 | 2 | no-localstorage, no-aria-labels, no-noscript |
| 479 | apps/experimental-ai/ai-prompt-lab.html | experimental-ai | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 480 | apps/experimental-ai/api-endpoint-tester.html | experimental-ai | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 481 | apps/experimental-ai/habit-tracker.html | experimental-ai | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 482 | apps/experimental-ai/interview-question-bank.html | experimental-ai | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 483 | apps/experimental-ai/json-formatter-validator.html | experimental-ai | 92 | 0 | 0 | 4 | no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 484 | apps/experimental-ai/knowledge-os.html | experimental-ai | 92 | 0 | 0 | 4 | no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 485 | apps/experimental-ai/local-first-crm.html | experimental-ai | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 486 | apps/experimental-ai/markdown-resume-builder.html | experimental-ai | 92 | 0 | 0 | 4 | no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 487 | apps/experimental-ai/neuai-crm-assistant.html | experimental-ai | 92 | 0 | 0 | 4 | no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 488 | apps/experimental-ai/p2p-drop.html | experimental-ai | 92 | 0 | 0 | 4 | no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 489 | apps/generative-art/infinite-recursive-art.html | generative-art | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 490 | apps/visual-art/gene-wars.html | visual-art | 92 | 0 | 0 | 4 | no-media-queries, no-noscript, inline-onclick, missing-input-labels |
| 491 | apps/visual-art/particle-life-finance.html | visual-art | 92 | 0 | 0 | 4 | no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 492 | apps/games-puzzles/infinite-game-jam.html | games-puzzles | 93 | 0 | 1 | 1 | console-log-pollution, no-noscript |
| 493 | apps/games-puzzles/snake-2-game.html | games-puzzles | 93 | 0 | 1 | 1 | no-json-export, no-noscript |
| 494 | apps/audio-music/3d-file-explorer.html | audio-music | 94 | 0 | 0 | 3 | no-noscript, inline-onclick, missing-input-labels |
| 495 | apps/audio-music/audio-spectrum-visualizer.html | audio-music | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 496 | apps/audio-music/modular-synthesizer-studio.html | audio-music | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 497 | apps/experimental-ai/ai-savings-tracker.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 498 | apps/experimental-ai/color-picker-palette-generator.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 499 | apps/experimental-ai/flashcard-study-app.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 500 | apps/experimental-ai/habit-tracker-goal-manager.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 501 | apps/experimental-ai/living-document.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 502 | apps/experimental-ai/meta-improvement-system.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 503 | apps/experimental-ai/password-generator-strength-checker.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 504 | apps/experimental-ai/pomodoro-timer-analytics.html | experimental-ai | 94 | 0 | 0 | 3 | no-noscript, inline-onclick, missing-input-labels |
| 505 | apps/experimental-ai/qr-code-generator-scanner.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 506 | apps/experimental-ai/speak-brilliantly-guide.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 507 | apps/experimental-ai/timezone-overlap-finder.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 508 | apps/experimental-ai/unit-converter-suite.html | experimental-ai | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 509 | apps/games-puzzles/steam-deck-game-store.html | games-puzzles | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 510 | apps/games-puzzles/virtual-dealer-suite.html | games-puzzles | 94 | 0 | 0 | 3 | no-noscript, inline-onclick, missing-input-labels |
| 511 | apps/games-puzzles/wowmon-team-builder.html | games-puzzles | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 512 | apps/generative-art/generative-art-studio.html | generative-art | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 513 | apps/visual-art/3d-particle-physics-simulator.html | visual-art | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 514 | apps/visual-art/agent-generator-ui.html | visual-art | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 515 | apps/visual-art/budget-tracker-expense-manager.html | visual-art | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 516 | apps/visual-art/personal-finance-dashboard.html | visual-art | 94 | 0 | 0 | 3 | no-aria-labels, no-noscript, inline-onclick |
| 517 | apps/audio-music/browser-daw.html | audio-music | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 518 | apps/audio-music/immersive-audio-visualizer.html | audio-music | 96 | 0 | 0 | 2 | no-aria-labels, no-noscript |
| 519 | apps/experimental-ai/agent-world.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 520 | apps/experimental-ai/brain-search-engine.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 521 | apps/experimental-ai/dynamics365-powerplatform.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 522 | apps/experimental-ai/markdown-editor-live-preview.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 523 | apps/experimental-ai/neuai-web.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 524 | apps/experimental-ai/salesforce-simulator.html | experimental-ai | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 525 | apps/visual-art/physics-lab.html | visual-art | 96 | 0 | 0 | 2 | no-noscript, inline-onclick |
| 526 | apps/creative-tools/data-slosh.html | creative-tools | 98 | 0 | 0 | 1 | inline-onclick |

## Top 20 Highest Scoring Apps

| Rank | File | Category | Score | Failed Rules |
|------|------|----------|-------|--------------|
| 1 | apps/creative-tools/data-slosh.html | creative-tools | 98 | inline-onclick |
| 2 | apps/audio-music/browser-daw.html | audio-music | 96 | no-noscript, inline-onclick |
| 3 | apps/audio-music/immersive-audio-visualizer.html | audio-music | 96 | no-aria-labels, no-noscript |
| 4 | apps/experimental-ai/agent-world.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 5 | apps/experimental-ai/brain-search-engine.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 6 | apps/experimental-ai/dynamics365-powerplatform.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 7 | apps/experimental-ai/markdown-editor-live-preview.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 8 | apps/experimental-ai/neuai-web.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 9 | apps/experimental-ai/salesforce-simulator.html | experimental-ai | 96 | no-noscript, inline-onclick |
| 10 | apps/visual-art/physics-lab.html | visual-art | 96 | no-noscript, inline-onclick |
| 11 | apps/audio-music/3d-file-explorer.html | audio-music | 94 | no-noscript, inline-onclick, missing-input-labels |
| 12 | apps/audio-music/audio-spectrum-visualizer.html | audio-music | 94 | no-aria-labels, no-noscript, inline-onclick |
| 13 | apps/audio-music/modular-synthesizer-studio.html | audio-music | 94 | no-aria-labels, no-noscript, inline-onclick |
| 14 | apps/experimental-ai/ai-savings-tracker.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 15 | apps/experimental-ai/color-picker-palette-generator.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 16 | apps/experimental-ai/flashcard-study-app.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 17 | apps/experimental-ai/habit-tracker-goal-manager.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 18 | apps/experimental-ai/living-document.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 19 | apps/experimental-ai/meta-improvement-system.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |
| 20 | apps/experimental-ai/password-generator-strength-checker.html | experimental-ai | 94 | no-aria-labels, no-noscript, inline-onclick |

## Bottom 20 Lowest Scoring Apps

| Rank | File | Category | Score | Failed Rules |
|------|------|----------|-------|--------------|
| 1 | apps/experimental-ai/witness-protocol-addon.html | experimental-ai | 17 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, console-log-pollution, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 2 | apps/games-puzzles/frankenship.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 3 | apps/games-puzzles/laws-of-creation.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 4 | apps/games-puzzles/monster-court.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 5 | apps/games-puzzles/noir-detective.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 6 | apps/games-puzzles/rhythm-terrain.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 7 | apps/games-puzzles/rogue-deck-arena.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 8 | apps/games-puzzles/street-food-tycoon.html | games-puzzles | 24 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-localstorage, no-error-handling, no-media-queries, no-aria-labels, no-noscript |
| 9 | apps/experimental-ai/TAROT_SYSTEM_ADDITION.html | experimental-ai | 27 | missing-doctype, missing-charset, missing-viewport, missing-title, missing-html-lang, missing-description, no-json-export, no-media-queries, no-aria-labels, no-noscript, inline-onclick |
| 10 | apps/experimental-ai/hacker-news-simulator.html | experimental-ai | 41 | external-scripts, external-styles, cdn-dependencies, missing-description, no-localstorage, no-aria-labels, no-noscript |
| 11 | apps/experimental-ai/chat-application.html | experimental-ai | 46 | external-scripts, external-styles, cdn-dependencies, console-log-pollution, no-noscript, inline-onclick |
| 12 | apps/games-puzzles/pokedex.html | games-puzzles | 51 | missing-charset, missing-viewport, missing-html-lang, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 13 | apps/experimental-ai/cdn-file-manager.html | experimental-ai | 52 | external-scripts, cdn-dependencies, missing-description, no-localstorage, no-aria-labels, no-noscript, inline-onclick, missing-input-labels |
| 14 | apps/games-puzzles/NexusWorlds.html | games-puzzles | 54 | external-scripts, cdn-dependencies, missing-description, console-log-pollution, no-noscript, inline-onclick, missing-input-labels |
| 15 | apps/visual-art/artifact-converter.html | visual-art | 54 | external-scripts, cdn-dependencies, no-localstorage, console-log-pollution, no-aria-labels, no-noscript, inline-onclick |
| 16 | apps/experimental-ai/ai-companion-hub-enhanced.html | experimental-ai | 56 | external-scripts, external-styles, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 17 | apps/experimental-ai/linux-browser-boot.html | experimental-ai | 56 | external-scripts, cdn-dependencies, no-localstorage, console-log-pollution, no-aria-labels, no-noscript |
| 18 | apps/experimental-ai/magellentic-agents.html | experimental-ai | 56 | external-scripts, external-styles, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 19 | apps/experimental-ai/wristAI.html | experimental-ai | 56 | external-scripts, cdn-dependencies, missing-description, console-log-pollution, no-noscript, inline-onclick |
| 20 | apps/experimental-ai/Agent Workflow System.html | experimental-ai | 57 | external-scripts, external-styles, missing-description, no-media-queries, no-aria-labels, no-noscript, inline-onclick |

---
*Report generated by Data Slosh Scanner v1.0 on 2026-02-07 17:14:08*