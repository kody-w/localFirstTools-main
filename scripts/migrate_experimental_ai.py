#!/usr/bin/env python3
"""
Mass Reclassification of experimental-ai
==========================================
Moves misplaced apps from experimental-ai to their correct categories.
Updates HTML meta tags, manifest.json, and validates everything.

Usage:
    python3 scripts/migrate_experimental_ai.py                # Dry run (shows plan)
    python3 scripts/migrate_experimental_ai.py --execute      # Actually move files
    python3 scripts/migrate_experimental_ai.py --execute --commit  # Move + git commit + push
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

# ============================================================================
# CLASSIFICATION MAP
# Each entry: filename -> target_category_key
# Files NOT listed here STAY in experimental_ai
# ============================================================================

MIGRATIONS = {
    # ── creative-tools (utilities, productivity, enterprise, editors) ──────
    "unit-converter-suite.html": "creative_tools",
    "lorem-ipsum-generator.html": "creative_tools",
    "json-formatter-validator.html": "creative_tools",
    "password-generator-strength-checker.html": "creative_tools",
    "meeting-cost-calculator.html": "creative_tools",
    "pomodoro-timer-analytics.html": "creative_tools",
    "timer-stopwatch-simple.html": "creative_tools",
    "cyber-timer.html": "creative_tools",
    "habit-tracker.html": "creative_tools",
    "habit-tracker-goal-manager.html": "creative_tools",
    "timezone-overlap-finder.html": "creative_tools",
    "timezone-meeting-planner.html": "creative_tools",
    "qr-code-generator-scanner.html": "creative_tools",
    "color-picker-palette-generator.html": "creative_tools",
    "color-palette-generator.html": "creative_tools",
    "markdown-editor-live-preview.html": "creative_tools",
    "markdown-resume-builder.html": "creative_tools",
    "note-taking-rich-text-editor.html": "creative_tools",
    "noteforge.html": "creative_tools",
    "universal-data-transformer.html": "creative_tools",
    "api-endpoint-tester.html": "creative_tools",
    "p2p-drop.html": "creative_tools",
    "p2p-whiteboard.html": "creative_tools",
    "prompt-library.html": "creative_tools",
    "ghostwriter.html": "creative_tools",
    "omni-writer.html": "creative_tools",
    "knowledge-os.html": "creative_tools",
    "brain-search-engine.html": "creative_tools",
    "digital-twin-keeper.html": "creative_tools",
    "local-first-crm.html": "creative_tools",
    "local-first-crdt-database.html": "creative_tools",
    "local-first-db-sync.html": "creative_tools",
    "cdn-file-manager.html": "creative_tools",
    "github-gallery-setup.html": "creative_tools",
    "living-document.html": "creative_tools",
    "document-time-machine.html": "creative_tools",
    "chat-application.html": "creative_tools",
    "snap-message-app.html": "creative_tools",
    "sneakernet-complete.html": "creative_tools",
    "sneaker-net-social.html": "creative_tools",
    "sneakernet-messenger.html": "creative_tools",
    "dual-camera-recorder-fixed.html": "creative_tools",
    "indoor-navigator.html": "creative_tools",
    "ai-savings-tracker.html": "creative_tools",
    "interview-question-bank.html": "creative_tools",
    "ai-prompt-lab.html": "creative_tools",
    "vibe-terminal.html": "creative_tools",
    "presentation_app_final.html": "creative_tools",
    "mac-migration-assessment-copilot.html": "creative_tools",
    "lowcode-workflow-translator.html": "creative_tools",
    "crm-questionnaire-viewer.html": "creative_tools",
    "dynamics365-simulator.html": "creative_tools",
    "salesforce-simulator.html": "creative_tools",
    "dynamics365-email-automation.html": "creative_tools",
    "dynamics365-powerplatform.html": "creative_tools",
    "copilot-agent-store.html": "creative_tools",
    "neuai-crm-assistant.html": "creative_tools",
    "magnetic-agents-ui.html": "creative_tools",
    "workflow-executor-app.html": "creative_tools",
    "agent-deployment-prototype.html": "creative_tools",
    "final-dashboard.html": "creative_tools",
    "splitspace.html": "creative_tools",
    "automated-actions-ui.html": "creative_tools",
    "custom-copilot-ui.html": "creative_tools",
    "ai-simulation-sales-demo.html": "creative_tools",
    "consolidated-ai-tools.html": "creative_tools",
    "wowMon_detail_view.html": "creative_tools",
    "windowed-desktop.html": "creative_tools",
    "local-browser.html": "creative_tools",
    "neuai-installer-wizard.html": "creative_tools",
    "extension-download.html": "creative_tools",
    "desktop-download.html": "creative_tools",
    "linux-browser-boot.html": "creative_tools",
    "linux-terminal-emulator.html": "creative_tools",
    "emdr-complete.html": "creative_tools",
    "breathwork.html": "creative_tools",
    "jim-rohn-journal-app.html": "creative_tools",
    "localfirst-magazine-2025-Q1.html": "creative_tools",
    "prompt-broadcast-social.html": "creative_tools",
    "mcp-registry.html": "creative_tools",
    "magentic-agents-ui.html": "creative_tools",
    "windows95-emulator.html": "creative_tools",
    "conspiracy-cooking-show.html": "creative_tools",

    # ── generative-art (procedural art, fractals, algorithmic visuals) ─────
    "atmospheric-sculptor.html": "generative_art",
    "amber-resonance.html": "generative_art",
    "bioluminescent-depth-explorer.html": "generative_art",
    "retrograde-garden.html": "generative_art",
    "psychometric-isobars.html": "generative_art",
    "hourglass-choice.html": "generative_art",
    "confluence.html": "generative_art",
    "isobar-pressure.html": "generative_art",
    "emotion-lattice.html": "generative_art",
    "typographic-terrarium.html": "generative_art",
    "memory-layers.html": "generative_art",
    "hourglass-terrarium.html": "generative_art",
    "resonance-threads.html": "generative_art",
    "fractal-explorer-interactive.html": "generative_art",
    "neon-archaeology.html": "generative_art",
    "rainy-night-neon-noir.html": "generative_art",
    "frost-glass.html": "generative_art",
    "geode-crack.html": "generative_art",
    "liminal-drift-atlas.html": "generative_art",
    "snowflake-symmetry-studio.html": "generative_art",
    "shadow-story-automaton.html": "generative_art",
    "infinite-city-wfc.html": "generative_art",
    "vacuum-tube-meditation.html": "generative_art",
    "canyon-composer.html": "generative_art",
    "glacial-core.html": "generative_art",
    "neural-weave.html": "generative_art",
    "sympathetic-reveal.html": "generative_art",
    "prism-refract.html": "generative_art",
    "lava-blobs.html": "generative_art",
    "memory-erosion-garden.html": "generative_art",
    "stalactite-time-machine.html": "generative_art",
    "imprint-erosion.html": "generative_art",
    "abyssal-symphony.html": "generative_art",
    "cellular-sandpile.html": "generative_art",
    "fractal-os.html": "generative_art",
    "tree-chronicle.html": "generative_art",
    "recursive-dream-machine.html": "generative_art",
    "marginalia-menagerie.html": "generative_art",
    "senbazuru-sanctuary.html": "generative_art",
    "stratified-echo.html": "generative_art",
    "gas-station-3am.html": "generative_art",

    # ── particle-physics (physics sims, evolution, science) ────────────────
    "evolution-simulator-3d.html": "particle_physics",
    "vestigial-automata.html": "particle_physics",
    "ant-farm-ultra.html": "particle_physics",
    "symbiotic-slime-mold-network.html": "particle_physics",
    "primordial-soup.html": "particle_physics",
    "ant-farm-simulation.html": "particle_physics",
    "cellular-multiverse.html": "particle_physics",
    "lagrange-point-garden.html": "particle_physics",
    "surface-tension.html": "particle_physics",
    "evolution-simulator.html": "particle_physics",
    "colony-mind.html": "particle_physics",
    "pendulum-wave.html": "particle_physics",
    "mycelium-network-builder.html": "particle_physics",
    "osm-ecosystem-city.html": "particle_physics",

    # ── 3d-immersive (WebGL, 3D environments) ─────────────────────────────
    "vaporwave-city-flyover.html": "3d_immersive",
    "tesseract-4d-rotator.html": "3d_immersive",
    "non-euclidean-hallway.html": "3d_immersive",
    "data-city.html": "3d_immersive",
    "workshop.html": "3d_immersive",
    "ray-march-studio.html": "3d_immersive",
    "bloomer.html": "3d_immersive",
    "procedural-solar-system.html": "3d_immersive",
    "zero-g-station-builder.html": "3d_immersive",
    "memory-palace.html": "3d_immersive",
    "shader-playground.html": "3d_immersive",
    "inception-globe-tower.html": "3d_immersive",
    "deterministic-universe-explorer.html": "3d_immersive",
    "infinite-city.html": "3d_immersive",
    "genesis-ark-odyssey.html": "3d_immersive",

    # ── games-puzzles (games, puzzles, interactive toys) ───────────────────
    "task-flow.html": "games_puzzles",
    "evomon-lab.html": "games_puzzles",
    "executive-presentation-slide2.html": "games_puzzles",
    "agent-browser.html": "games_puzzles",
    "Agent Workflow System.html": "games_puzzles",
    "terminal-viewer.html": "games_puzzles",
    "api-request-tester.html": "games_puzzles",
    "text-file-splitter.html": "games_puzzles",
    "qr-sharer.html": "games_puzzles",
    "css-animation-builder.html": "games_puzzles",
    "leviathan-omniverse-v109-mobile-optimized.html": "games_puzzles",
    "severance-refiner.html": "games_puzzles",
    "witness-protocol-addon.html": "games_puzzles",
    "dynamic-agent-workflow.html": "games_puzzles",
    "tab-pet.html": "games_puzzles",
    "firefly-collector.html": "games_puzzles",
    "TAROT_DEMO.html": "games_puzzles",
    "evomon-history-viewer.html": "games_puzzles",
    "presentation-slide-responsive-updated.html": "games_puzzles",
    "accordion-memories.html": "games_puzzles",
    "typing-speed-test.html": "games_puzzles",
    "inspection-ritual.html": "games_puzzles",

    # ── educational (learning, tutorials, interactive lessons) ─────────────
    "flashcard-study-app.html": "educational_tools",
    "neural-network-playground.html": "educational_tools",
    "algorithm-visualizer-pro.html": "educational_tools",
    "data-structures-visualizer.html": "educational_tools",
    "interactive-code-playground.html": "educational_tools",
    "infinite-hotel.html": "educational_tools",
    "regex-master-interactive.html": "educational_tools",
    "speak-brilliantly-guide.html": "educational_tools",
    "antikythera-mechanism.html": "educational_tools",
    "neural-builder.html": "educational_tools",
    "record-review-app.html": "educational_tools",
    "influence-mastery-app.html": "educational_tools",
    "brain-thought-simulator.html": "educational_tools",
    "global-time-machine.html": "educational_tools",

    # ── audio-music (synths, audio tools) ──────────────────────────────────
    "text-to-speech-choir.html": "audio_music",

    # ── visual-art (drawing tools, visual effects, design) ─────────────────
    "landmark-art-studio.html": "visual_art",
    "picasso-bowl.html": "visual_art",
    "procedural-spider-ik.html": "visual_art",
    "crowd-heatmap.html": "visual_art",
}

# Category key -> folder name mapping
CATEGORY_FOLDERS = {
    "creative_tools": "creative-tools",
    "generative_art": "generative-art",
    "visual_art": "visual-art",
    "particle_physics": "particle-physics",
    "audio_music": "audio-music",
    "games_puzzles": "games-puzzles",
    "educational_tools": "educational",
    "3d_immersive": "3d-immersive",
    "experimental_ai": "experimental-ai",
}


def update_meta_category(html_content: str, new_category_key: str) -> str:
    """Update the rappterzoo:category meta tag in HTML content."""
    # Try both formats: experimental_ai and experimental-ai
    patterns = [
        r'(<meta\s+name="rappterzoo:category"\s+content=")[^"]*(")',
        r"(<meta\s+name='rappterzoo:category'\s+content=')[^']*(')",
    ]
    new_folder = CATEGORY_FOLDERS[new_category_key]
    for pat in patterns:
        if re.search(pat, html_content):
            html_content = re.sub(pat, rf'\g<1>{new_folder}\2', html_content)
            return html_content
    # Tag doesn't exist; don't add one
    return html_content


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")


def validate_manifest(manifest):
    """Validate counts match actual array lengths."""
    errors = []
    for key, cat in manifest["categories"].items():
        actual = len(cat.get("apps", []))
        declared = cat.get("count", 0)
        if actual != declared:
            errors.append(f"  {key}: count={declared} but {actual} apps in array")
    return errors


def main():
    execute = "--execute" in sys.argv
    commit = "--commit" in sys.argv

    print("=" * 70)
    print("EXPERIMENTAL-AI MASS RECLASSIFICATION")
    print("=" * 70)
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print()

    # Load manifest
    manifest = load_manifest()
    exp_ai = manifest["categories"]["experimental_ai"]
    print(f"Current experimental-ai count: {exp_ai['count']} (manifest)")
    print(f"Current experimental-ai apps:  {len(exp_ai['apps'])} (array)")
    print()

    # Build index: filename -> manifest entry (for experimental_ai)
    exp_entries = {}
    for entry in exp_ai["apps"]:
        exp_entries[entry["file"]] = entry

    # Tally by destination
    dest_counts = defaultdict(list)
    missing_files = []
    missing_entries = []
    skipped = []

    for filename, dest_cat in MIGRATIONS.items():
        src_path = APPS_DIR / "experimental-ai" / filename
        if not src_path.exists():
            missing_files.append(filename)
            continue
        if filename not in exp_entries:
            missing_entries.append(filename)
            # File exists but not in manifest - still move it
        dest_counts[dest_cat].append(filename)

    # Print plan
    print("MIGRATION PLAN")
    print("-" * 50)
    total_moving = 0
    for cat_key in sorted(dest_counts.keys()):
        files = dest_counts[cat_key]
        folder = CATEGORY_FOLDERS[cat_key]
        print(f"  → {folder:20s}: {len(files):3d} apps")
        total_moving += len(files)

    staying = len(exp_entries) - total_moving - len(missing_files)
    print(f"  ✓ {'experimental-ai':20s}: {staying:3d} apps (STAY)")
    print(f"  ─────────────────────────────")
    print(f"  Total moving:          {total_moving:3d}")
    print(f"  Total staying:         {staying:3d}")
    print()

    if missing_files:
        print(f"⚠ {len(missing_files)} files in migration map but NOT on disk:")
        for f in missing_files:
            print(f"    {f}")
        print()

    if missing_entries:
        print(f"⚠ {len(missing_entries)} files on disk but NOT in manifest (will still move):")
        for f in missing_entries:
            print(f"    {f}")
        print()

    # Show what stays
    staying_files = []
    for filename in exp_entries:
        if filename not in MIGRATIONS:
            staying_files.append(filename)
    print(f"STAYING in experimental-ai ({len(staying_files)}):")
    for f in sorted(staying_files):
        entry = exp_entries[f]
        print(f"  ✓ {f:55s} - {entry.get('title', '?')}")
    print()

    if not execute:
        print("=" * 70)
        print("DRY RUN COMPLETE. Run with --execute to apply changes.")
        print("=" * 70)
        return

    # ── EXECUTE MIGRATIONS ──────────────────────────────────────────────
    print("EXECUTING MIGRATIONS...")
    print("=" * 70)

    moved = 0
    errors = []

    for cat_key, filenames in dest_counts.items():
        folder = CATEGORY_FOLDERS[cat_key]
        dest_dir = APPS_DIR / folder

        # Ensure destination directory exists
        dest_dir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            src_path = APPS_DIR / "experimental-ai" / filename
            dest_path = dest_dir / filename

            if dest_path.exists():
                print(f"  ⚠ SKIP {filename} - already exists in {folder}/")
                skipped.append(filename)
                continue

            try:
                # 1. Read and update HTML meta tag
                content = src_path.read_text(encoding="utf-8")
                updated_content = update_meta_category(content, cat_key)

                # 2. Write to new location with updated meta tag
                dest_path.write_text(updated_content, encoding="utf-8")

                # 3. Remove from old location
                src_path.unlink()

                # 4. Update manifest: remove from experimental_ai
                entry = exp_entries.get(filename)
                if entry and entry in manifest["categories"]["experimental_ai"]["apps"]:
                    manifest["categories"]["experimental_ai"]["apps"].remove(entry)
                    manifest["categories"]["experimental_ai"]["count"] = len(
                        manifest["categories"]["experimental_ai"]["apps"]
                    )

                    # 5. Add to destination category
                    if cat_key not in manifest["categories"]:
                        print(f"  ⚠ Category {cat_key} not in manifest!")
                        errors.append(f"Missing category: {cat_key}")
                        continue

                    manifest["categories"][cat_key]["apps"].append(entry)
                    manifest["categories"][cat_key]["count"] = len(
                        manifest["categories"][cat_key]["apps"]
                    )

                moved += 1
                print(f"  [{moved:3d}/{total_moving}] {filename:55s} → {folder}/")

            except Exception as e:
                errors.append(f"{filename}: {e}")
                print(f"  ✗ ERROR {filename}: {e}")

    # Save manifest
    print()
    print("Saving manifest.json...")
    save_manifest(manifest)

    # Validate
    print("Validating manifest.json...")
    try:
        test = json.load(open(MANIFEST_PATH, encoding="utf-8"))
        print("  ✓ Valid JSON")
    except json.JSONDecodeError as e:
        print(f"  ✗ INVALID JSON: {e}")

    val_errors = validate_manifest(manifest)
    if val_errors:
        print("  ⚠ Count mismatches:")
        for e in val_errors:
            print(f"    {e}")
    else:
        print("  ✓ All counts match")

    # Verify files exist at destinations
    print()
    print("Verifying file integrity...")
    missing_at_dest = 0
    for cat_key, filenames in dest_counts.items():
        folder = CATEGORY_FOLDERS[cat_key]
        for filename in filenames:
            if filename in skipped:
                continue
            dest_path = APPS_DIR / folder / filename
            if not dest_path.exists():
                print(f"  ✗ MISSING: {folder}/{filename}")
                missing_at_dest += 1
    if missing_at_dest == 0:
        print(f"  ✓ All {moved} moved files verified at destination")

    # ── REPORT ──────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("MIGRATION REPORT")
    print("=" * 70)
    print(f"Total apps moved:        {moved}")
    print(f"Files skipped (existed): {len(skipped)}")
    print(f"Errors:                  {len(errors)}")
    print()
    print("Destination breakdown:")
    for cat_key in sorted(dest_counts.keys()):
        folder = CATEGORY_FOLDERS[cat_key]
        actual_moved = len([f for f in dest_counts[cat_key] if f not in skipped])
        new_count = manifest["categories"][cat_key]["count"]
        print(f"  {folder:20s}: +{actual_moved:3d}  (total now: {new_count})")

    exp_count = manifest["categories"]["experimental_ai"]["count"]
    print(f"\nexperimental-ai: 222 → {exp_count} ({222 - exp_count} removed)")
    reduction = ((222 - exp_count) / 222) * 100
    print(f"Reduction: {reduction:.1f}%")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")

    # ── GIT COMMIT ──────────────────────────────────────────────────────
    if commit and moved > 0:
        print()
        print("Committing to git...")

        # Build commit message
        dest_summary = []
        for cat_key in sorted(dest_counts.keys()):
            folder = CATEGORY_FOLDERS[cat_key]
            count = len([f for f in dest_counts[cat_key] if f not in skipped])
            if count > 0:
                dest_summary.append(f"- {count} to {folder}")

        msg = f"""refactor: mass reclassification of experimental-ai ({moved} apps migrated)

Moved {moved} apps from experimental-ai to their correct categories:
{chr(10).join(dest_summary)}

experimental-ai reduced from 222 to {exp_count} (genuinely experimental apps only)"""

        try:
            subprocess.run(["git", "add", "-A", "apps/"], cwd=REPO_ROOT, check=True)
            subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=REPO_ROOT, check=True)
            print("  ✓ Committed and pushed to main")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Git error: {e}")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
