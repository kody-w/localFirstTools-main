# Experimental-AI Mass Reclassification Report

**Date:** 2025-02-09  
**Scope:** All 222 apps in `apps/experimental-ai/`  
**Goal:** Move misplaced apps to correct categories; keep only genuinely experimental/AI apps  

## Summary

| Metric | Value |
|--------|-------|
| Total apps in experimental-ai | 222 |
| Apps to migrate | **194** |
| Apps staying | **27** |
| Reduction | **87.8%** (target was 40%+) |

## Migration Breakdown

| Destination | Count | What's moving there |
|-------------|-------|---------------------|
| creative-tools | 83 | Timers, editors, CRM tools, utilities, messaging, converters |
| generative-art | 41 | Procedural visuals, fractals, atmospheric art, generative experiences |
| games-puzzles | 22 | Molted games, puzzles, interactive toys |
| 3d-immersive | 15 | WebGL demos, 3D environments, shader studios |
| particle-physics | 14 | Evolution sims, cellular automata, physics demos |
| educational | 14 | Learning tools, algorithm visualizers, flashcards |
| visual-art | 4 | Drawing tools, webcam art, cubist visualization |
| audio-music | 1 | Text-to-speech choir |

## Apps Staying in experimental-ai (27)

These are genuinely experimental — AI consciousness, emergence, simulation theory, autonomous systems:

| File | Title | Why it stays |
|------|-------|--------------|
| agent-collaboration.html | Agent Collaboration Tool | Multi-agent AI collaboration |
| agent-world.html | Agent World - AI Agent Simulation | Autonomous agent ecosystem |
| ai-companion-hub-enhanced.html | AI Companion Hub | AI companion with 3D/WebGL |
| wristAI.html | AI Companion Hub | AI assistant interface |
| windows-95-ai-agent-autonomous-desktop-controller.html | Windows 95 AI Agent | Autonomous AI controlling a desktop sim |
| digital-tulpa.html | Digital Tulpa: Mind Garden | Persistent AI consciousness sim |
| cogito.html | Cogito — I Think Therefore I App | Self-aware HTML, existential meta-app |
| consciousness-backup-terminal.html | Consciousness Backup Terminal | Consciousness upload experiment |
| simulated-ancestor.html | Simulated Ancestor | Nested simulation theory explorer |
| library-of-babel.html | The Library of Babel | Borges' infinite library concept |
| determinism-debugger.html | The Determinism Debugger | Free will vs determinism |
| feed-gods.html | Feed Gods — You Are The Algorithm | Emergent social AI simulation |
| book-factory-world.html | Book Factory World | Autonomous literary production |
| compressed-book-factory.html | Autonomous Book Factory | Autonomous book generation |
| autonomous-book-factory.html | Autonomous Book Factory — Visual Pipeline | Autonomous pipeline |
| neuai-web.html | NeuAI Web - AI Assistant | AI assistant with persistent memory |
| meta-improvement-system.html | Meta-Improvement System | Multi-agent self-improvement |
| self-aware-loading-screen.html | Self-Aware Loading Screen | Sentient loading screen |
| membrane.html | THE MEMBRANE | Local AI presence concept |
| executive-memory-visualizer.html | AI Dynamic Memory Explorer | AI memory visualization |
| reality-corruption-simulator.html | Reality Corruption Simulator | Broken simulation concept |
| magellentic-agents.html | Magentic Agents | AI agent system |
| offline-internet-simulator.html | Offline Internet Simulator | Social simulation / filter bubbles |
| schrodingers-todo.html | Schrödinger's Todo | Quantum state concept app |
| emotion-engine.html | Emotion Engine | Real-time sentiment / emotion AI |
| hacker-news-simulator.html | Hacker News Simulator | Social dynamics simulation |
| nano-banana-chat-app.html | Nano Banana AI Chat | AI chat interface |

## How to Execute

```bash
# 1. Preview the plan (dry run, changes nothing)
python3 scripts/migrate_experimental_ai.py

# 2. Execute the migration
python3 scripts/migrate_experimental_ai.py --execute

# 3. Execute + commit + push in one go
python3 scripts/migrate_experimental_ai.py --execute --commit

# 4. Publish rankings after migration
python3 scripts/rank_games.py --push
```

## Post-Migration Category Counts (estimated)

| Category | Before | Added | After |
|----------|--------|-------|-------|
| creative-tools | 147 | +83 | 230 |
| generative-art | 46 | +41 | 87 |
| games-puzzles | 40 | +22 | 62 |
| 3d-immersive | 28 | +15 | 43 |
| particle-physics | 30 | +14 | 44 |
| educational | 18 | +14 | 32 |
| visual-art | 43 | +4 | 47 |
| audio-music | 41 | +1 | 42 |
| **experimental-ai** | **222** | **-194** | **27** |
