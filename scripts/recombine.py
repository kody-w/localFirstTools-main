#!/usr/bin/env python3
"""Genetic Recombination Engine — breed new games from top performers' DNA.

Instead of creating games from scratch or linearly molting one game forward,
this engine extracts "genes" (proven code patterns) from high-scoring apps and
recombines them into new organisms. Combined with experience-first prompting,
it produces games with the technical DNA of champions and the soul of an
emotional target.

Gene Types:
    render_pipeline  — Canvas setup, clear/draw/update loop
    physics_engine   — Velocity, gravity, collision, bounce
    particle_system  — Emitter, spawn, lifetime, fade
    audio_engine     — Web Audio oscillators, gain nodes, sound design
    input_handler    — Keyboard/mouse/touch with state tracking
    state_machine    — Game states, transitions, menus
    entity_system    — Classes/factories for game objects
    hud_renderer     — Score display, health bars, status text
    progression      — Levels, waves, difficulty scaling
    juice            — Screen shake, flash, combo, feedback

Usage:
    python3 scripts/recombine.py                              # Breed 1 game from top donors
    python3 scripts/recombine.py --count 5                    # Breed 5 games
    python3 scripts/recombine.py --parents game1.html game2.html  # Specific parents
    python3 scripts/recombine.py --experience "discovery"     # Target experience
    python3 scripts/recombine.py --dry-run                    # Show plan, don't create
    python3 scripts/recombine.py --list-genes                 # Show gene catalog from top apps

Output: New HTML files in apps/<category>/ with rappterzoo:parent lineage tags.
"""

import json
import random
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
EXPERIENCE_PALETTE = ROOT / "scripts" / "experience_palette.json"

# Add scripts to path for imports
sys.path.insert(0, str(ROOT / "scripts"))
from copilot_utils import (
    VALID_CATEGORIES,
    copilot_call,
    detect_backend,
    load_manifest,
    parse_llm_html,
    save_manifest,
)
from rank_games import score_game, grade_from_score


# ---------------------------------------------------------------------------
# Gene Definitions — what patterns we extract from donor apps
# ---------------------------------------------------------------------------
GENE_PATTERNS = {
    "render_pipeline": {
        "description": "Canvas setup, clear/draw/update render loop",
        "detection": [
            r"getContext\(['\"]2d['\"]\)",
            r"requestAnimationFrame",
            r"clearRect\s*\(",
        ],
        "extraction": r"(?:(?:const|let|var)\s+(?:canvas|ctx|context)\b.*?$.*?){3,}",
        "weight": 3,
    },
    "physics_engine": {
        "description": "Velocity, gravity, collision detection, bounce",
        "detection": [
            r"velocity|\.vx\b|\.vy\b",
            r"gravity|\.g\b",
            r"collisi|intersect|overlap|hitTest|bounds",
        ],
        "extraction": r"(?:velocity|gravity|acceleration|friction|bounce).*?(?=\n\n|\bfunction\b|\bclass\b)",
        "weight": 3,
    },
    "particle_system": {
        "description": "Particle emitter, spawn, lifetime, visual effects",
        "detection": [
            r"particle|emitter",
            r"spawn|emit|burst",
            r"lifetime|age|alpha|fade",
        ],
        "extraction": r"(?:class\s+Particle|function\s+\w*[Pp]article).*?(?=\nclass\b|\nfunction\b(?!\s+\w*[Pp]article))",
        "weight": 2,
    },
    "audio_engine": {
        "description": "Web Audio API sound synthesis and design",
        "detection": [
            r"AudioContext|webkitAudioContext",
            r"createOscillator|createGain",
        ],
        "extraction": r"(?:AudioContext|webkitAudioContext).*?(?=\n\n\n|\bclass\b)",
        "weight": 2,
    },
    "input_handler": {
        "description": "Keyboard/mouse/touch with pressed-key state tracking",
        "detection": [
            r"addEventListener\s*\(\s*['\"]key",
            r"keys\s*\[|pressed\[|keysDown|keysPressed",
        ],
        "extraction": r"addEventListener\s*\(['\"]key.*?(?=\n\n\n|\bfunction\b(?!\s*\())",
        "weight": 2,
    },
    "state_machine": {
        "description": "Game state management, transitions, menus",
        "detection": [
            r"gameState|state\s*===?\s*['\"]",
            r"setState|changeState|transition",
        ],
        "extraction": r"(?:gameState|state\s*=).*?(?=\n\n\n)",
        "weight": 2,
    },
    "entity_system": {
        "description": "Game object classes/factories with update/draw methods",
        "detection": [
            r"class\s+\w+\s*\{",
            r"(?:update|draw|render)\s*\(\s*\)",
        ],
        "extraction": r"class\s+\w+\s*\{[^}]+(?:\{[^}]*\}[^}]*)*\}",
        "weight": 3,
    },
    "hud_renderer": {
        "description": "Score display, health bars, status text overlay",
        "detection": [
            r"drawHUD|renderHUD|updateHUD|drawUI",
            r"fillText.*score|fillText.*health|fillText.*level",
        ],
        "extraction": r"(?:function\s+(?:draw|render)(?:HUD|UI|Score|Health)).*?(?=\nfunction\b)",
        "weight": 1,
    },
    "progression": {
        "description": "Level/wave system, difficulty scaling, unlocks",
        "detection": [
            r"level|wave|stage|round",
            r"nextLevel|nextWave|advance|progress",
        ],
        "extraction": r"(?:function\s+\w*(?:level|wave|advance|progress)).*?(?=\nfunction\b)",
        "weight": 2,
    },
    "juice": {
        "description": "Screen shake, hit flash, combo system, feedback effects",
        "detection": [
            r"shake|flash|combo|multiplier|streak",
            r"knockback|recoil|vibrat|pulse",
        ],
        "extraction": r"(?:function\s+\w*(?:shake|flash|effect|juice|feedback)).*?(?=\nfunction\b)",
        "weight": 2,
    },
}


def detect_genes(content: str) -> dict:
    """Detect which genes are present in an app's source code.

    Returns dict of gene_name -> {present: bool, strength: int (0-3), markers: list}
    """
    genes = {}
    for gene_name, gene_def in GENE_PATTERNS.items():
        markers_found = []
        for pattern in gene_def["detection"]:
            if re.search(pattern, content, re.IGNORECASE):
                markers_found.append(pattern)

        total_markers = len(gene_def["detection"])
        found_count = len(markers_found)

        if found_count == total_markers:
            strength = 3  # Full gene expression
        elif found_count >= total_markers // 2 + 1:
            strength = 2  # Partial expression
        elif found_count >= 1:
            strength = 1  # Trace
        else:
            strength = 0  # Absent

        genes[gene_name] = {
            "present": strength > 0,
            "strength": strength,
            "markers": markers_found,
            "weight": gene_def["weight"],
        }

    return genes


def extract_gene_samples(content: str, gene_name: str, max_chars: int = 2000):
    """Extract a representative code sample for a specific gene.

    Returns the best matching code snippet, or None if gene isn't present.
    """
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    js = "\n".join(scripts)

    gene_def = GENE_PATTERNS.get(gene_name)
    if not gene_def:
        return None

    # Try the extraction regex first
    match = re.search(gene_def["extraction"], js, re.DOTALL | re.MULTILINE)
    if match:
        sample = match.group(0).strip()
        return sample[:max_chars]

    # Fallback: find the region around detection markers
    for pattern in gene_def["detection"]:
        m = re.search(pattern, js, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 500)
            end = min(len(js), m.end() + 500)
            return js[start:end].strip()[:max_chars]

    return None


def catalog_genes(top_n: int = 20) -> dict:
    """Build a gene catalog from the top-scoring apps.

    Returns dict mapping gene_name -> list of {file, strength, sample}
    """
    manifest = load_manifest()
    catalog = {gene: [] for gene in GENE_PATTERNS}

    # Score all apps and get top N
    scored = []
    for cat_key, cat_data in manifest["categories"].items():
        folder = cat_data["folder"]
        for app in cat_data["apps"]:
            filepath = APPS_DIR / folder / app["file"]
            if not filepath.exists():
                continue
            try:
                content = filepath.read_text(errors="replace")
                if len(content) < 500:
                    continue
                result = score_game(filepath, content)
                scored.append((result["score"], filepath, content, app["file"]))
            except Exception:
                continue

    scored.sort(key=lambda x: x[0], reverse=True)
    top_apps = scored[:top_n]

    for score, filepath, content, filename in top_apps:
        genes = detect_genes(content)
        for gene_name, gene_info in genes.items():
            if gene_info["present"] and gene_info["strength"] >= 2:
                sample = extract_gene_samples(content, gene_name)
                catalog[gene_name].append({
                    "file": filename,
                    "score": score,
                    "strength": gene_info["strength"],
                    "sample": sample,
                })

    return catalog


def select_parents(count: int = 2, category: str = None) -> list:
    """Select high-scoring donor apps for recombination.

    Prefers apps with complementary gene profiles — if parent A has strong
    physics but weak audio, parent B should have strong audio.
    """
    manifest = load_manifest()
    candidates = []

    for cat_key, cat_data in manifest["categories"].items():
        if category and cat_key != category:
            continue
        folder = cat_data["folder"]
        for app in cat_data["apps"]:
            filepath = APPS_DIR / folder / app["file"]
            if not filepath.exists():
                continue
            try:
                content = filepath.read_text(errors="replace")
                if len(content) < 1000:
                    continue
                result = score_game(filepath, content)
                if result["score"] < 50:
                    continue
                genes = detect_genes(content)
                gene_signature = tuple(
                    (g, info["strength"]) for g, info in genes.items() if info["present"]
                )
                candidates.append({
                    "file": app["file"],
                    "path": filepath,
                    "score": result["score"],
                    "genes": genes,
                    "gene_signature": gene_signature,
                    "category": cat_key,
                    "content": content,
                })
            except Exception:
                continue

    if len(candidates) < count:
        return candidates

    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Select first parent from top tier
    top_tier = candidates[:max(10, len(candidates) // 5)]
    parent_a = random.choice(top_tier)
    selected = [parent_a]

    # Select remaining parents for gene complementarity
    a_strong = {g for g, info in parent_a["genes"].items() if info["strength"] >= 2}
    a_weak = {g for g, info in parent_a["genes"].items() if info["strength"] < 2}

    for _ in range(count - 1):
        best_complement = None
        best_score = -1

        for c in candidates:
            if c in selected:
                continue
            # Score complementarity: how many of A's weak genes does this candidate fill?
            c_strong = {g for g, info in c["genes"].items() if info["strength"] >= 2}
            complement_score = len(c_strong & a_weak) * 2 + c["score"] / 100
            if complement_score > best_score:
                best_score = complement_score
                best_complement = c

        if best_complement:
            selected.append(best_complement)

    return selected


def crossover(parents: list) -> dict:
    """Select the best genes from each parent to form a genome.

    Returns dict of gene_name -> {source_file, sample, strength}
    """
    genome = {}

    for gene_name in GENE_PATTERNS:
        best_source = None
        best_strength = 0

        for parent in parents:
            gene_info = parent["genes"].get(gene_name, {})
            strength = gene_info.get("strength", 0)
            if strength > best_strength:
                best_strength = strength
                best_source = parent

        if best_source and best_strength >= 1:
            sample = extract_gene_samples(best_source["content"], gene_name)
            genome[gene_name] = {
                "source_file": best_source["file"],
                "source_score": best_source["score"],
                "strength": best_strength,
                "sample": sample,
            }

    return genome


def load_experience(experience_id: str = None):
    """Load an experience target from the palette."""
    if not EXPERIENCE_PALETTE.exists():
        return None

    palette = json.loads(EXPERIENCE_PALETTE.read_text())
    experiences = palette.get("experiences", [])

    if not experiences:
        return None

    if experience_id:
        for exp in experiences:
            if exp["id"] == experience_id:
                return exp
        return None

    # Random selection weighted by freshness (prefer less-used experiences)
    return random.choice(experiences)


def build_synthesis_prompt(genome: dict, experience: dict = None, target_category: str = None) -> str:
    """Build the LLM prompt that synthesizes a new game from genome + experience.

    This is where genetic recombination meets experience-first design.
    """
    # Gene descriptions with code samples
    gene_sections = []
    for gene_name, gene_data in genome.items():
        desc = GENE_PATTERNS[gene_name]["description"]
        section = f"### Gene: {gene_name} (from {gene_data['source_file']}, score {gene_data['source_score']})\n"
        section += f"Purpose: {desc}\n"
        if gene_data.get("sample"):
            # Truncate samples to keep prompt manageable
            sample = gene_data["sample"][:1500]
            section += f"Reference implementation:\n```javascript\n{sample}\n```\n"
        gene_sections.append(section)

    genes_text = "\n".join(gene_sections)

    # Experience section
    experience_text = ""
    if experience:
        experience_text = f"""
## EXPERIENCE TARGET (this is the SOUL of the game)

**Emotion:** {experience.get('emotion', 'engaging')}
**Feeling:** {experience.get('description', '')}

**Design direction:**
{chr(10).join('- ' + h for h in experience.get('mechanical_hints', []))}

**What to AVOID:**
{chr(10).join('- ' + a for a in experience.get('anti_patterns', []))}

The game mechanics should emerge from this emotional target. Don't just bolt features
onto a template — let the feeling DRIVE the design decisions.
"""

    # Category hint
    cat_hint = ""
    if target_category:
        cat_hint = f"\nTarget category: {target_category}\n"

    prompt = f"""You are a game genome synthesizer. You will create a brand-new, original HTML game
by recombining proven code patterns (genes) from top-scoring games, guided by an
emotional experience target.

CRITICAL RULES:
- Output ONLY the complete HTML file, nothing else
- Single self-contained HTML file with ALL CSS and JS inline
- <!DOCTYPE html>, <title>, <meta name="viewport"> required
- ZERO external dependencies (no CDNs, no APIs, no external files)
- Must work offline
- Must be genuinely fun and interactive
- DO NOT copy the gene samples verbatim — use them as INSPIRATION for your own implementation
- The game must feel like a coherent whole, not a Frankenstein of parts

## GENETIC MATERIAL (proven patterns from high-scoring games)

These are code patterns extracted from the best-performing games in the gallery.
Use them as architectural inspiration — adapt the patterns to serve the experience target.

{genes_text}

{experience_text}
{cat_hint}

## SYNTHESIS INSTRUCTIONS

1. Start with the experience target — what should the player FEEL?
2. Choose mechanics that serve that feeling (don't just pick the flashiest genes)
3. Implement a complete game loop: init → update → render → repeat
4. Include: title screen, gameplay, game over, restart
5. Add juice: screen shake, particle effects, sound feedback, combo systems
6. Make it visually distinctive — custom color palette, animations, effects
7. Ensure responsive design (works on mobile)
8. Add keyboard AND mouse/touch controls

Create something that would genuinely surprise and delight someone opening it in a browser.
The bar is high — this game is bred from champions.

Output the complete HTML file now:"""

    return prompt


def synthesize_game(genome: dict, experience: dict = None, target_category: str = None,
                    dry_run: bool = False) -> dict:
    """Use LLM to synthesize a new game from genome + experience target.

    Returns dict with: html, filename, title, metadata, lineage
    """
    prompt = build_synthesis_prompt(genome, experience, target_category)

    if dry_run:
        parent_files = list(set(g["source_file"] for g in genome.values()))
        return {
            "status": "dry_run",
            "prompt_size": len(prompt),
            "genes_used": list(genome.keys()),
            "parents": parent_files,
            "experience": experience.get("id") if experience else None,
        }

    # Check backend
    backend = detect_backend()
    if backend == "unavailable":
        return {"status": "failed", "reason": "copilot-unavailable"}

    # Call LLM
    raw = copilot_call(prompt, timeout=180)
    if not raw:
        return {"status": "failed", "reason": "copilot-empty-response"}

    html = parse_llm_html(raw)
    if not html or len(html) < 500:
        return {"status": "failed", "reason": "output-too-small"}

    # Validate basics
    if "<!doctype html>" not in html.lower()[:200]:
        return {"status": "failed", "reason": "missing-doctype"}

    # Extract title
    title_match = re.search(r"<title>(.*?)</title>", html)
    title = title_match.group(1).strip() if title_match else "Untitled Recombinant"

    # Generate filename from title
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    filename = f"{slug}.html"

    # Build lineage metadata
    parent_files = list(set(g["source_file"] for g in genome.values()))

    return {
        "status": "success",
        "html": html,
        "filename": filename,
        "title": title,
        "genes_used": list(genome.keys()),
        "parents": parent_files,
        "experience": experience.get("id") if experience else None,
        "size": len(html),
    }


def inject_lineage_tags(html: str, parents: list, genes: list, experience_id: str = None) -> str:
    """Inject rappterzoo:parent and lineage meta tags into the HTML."""
    lineage_tags = []
    lineage_tags.append(f'<meta name="rappterzoo:author" content="recombination-engine">')
    lineage_tags.append(f'<meta name="rappterzoo:author-type" content="agent">')
    lineage_tags.append(f'<meta name="rappterzoo:parents" content="{",".join(parents)}">')
    lineage_tags.append(f'<meta name="rappterzoo:genes" content="{",".join(genes)}">')
    lineage_tags.append(f'<meta name="rappterzoo:created" content="{date.today().isoformat()}">')
    lineage_tags.append(f'<meta name="rappterzoo:generation" content="0">')
    if experience_id:
        lineage_tags.append(f'<meta name="rappterzoo:experience" content="{experience_id}">')

    tags_str = "\n    ".join(lineage_tags)

    # Insert after <head> or after first <meta>
    if "<head>" in html:
        html = html.replace("<head>", f"<head>\n    {tags_str}", 1)
    elif "<HEAD>" in html:
        html = html.replace("<HEAD>", f"<HEAD>\n    {tags_str}", 1)
    else:
        # Insert after <!DOCTYPE html>
        html = re.sub(
            r"(<!DOCTYPE html>)",
            rf"\1\n<head>\n    {tags_str}\n</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return html


def recombine(count: int = 1, experience_id: str = None, parent_files: list = None,
              target_category: str = None, dry_run: bool = False, verbose: bool = False) -> list:
    """Main recombination pipeline. Breed `count` new games.

    Returns list of result dicts.
    """
    results = []

    for i in range(count):
        if verbose:
            print(f"\n{'='*60}")
            print(f"RECOMBINATION {i+1}/{count}")
            print(f"{'='*60}")

        # Select parents
        if parent_files:
            parents = []
            for pf in parent_files:
                filepath = None
                # Search for the file
                for html_file in APPS_DIR.rglob(pf):
                    filepath = html_file
                    break
                if filepath and filepath.exists():
                    content = filepath.read_text(errors="replace")
                    result = score_game(filepath, content)
                    genes = detect_genes(content)
                    parents.append({
                        "file": filepath.name,
                        "path": filepath,
                        "score": result["score"],
                        "genes": genes,
                        "category": "unknown",
                        "content": content,
                    })
        else:
            parents = select_parents(count=2, category=target_category)

        if len(parents) < 2:
            results.append({"status": "failed", "reason": "not-enough-parents"})
            continue

        if verbose:
            for p in parents:
                gene_list = [g for g, info in p["genes"].items() if info["present"]]
                print(f"  Parent: {p['file']} (score {p['score']}) genes: {', '.join(gene_list)}")

        # Crossover
        genome = crossover(parents)
        if verbose:
            print(f"  Genome: {', '.join(genome.keys())}")

        # Load experience
        experience = load_experience(experience_id) if experience_id else load_experience()
        if verbose and experience:
            print(f"  Experience: {experience['id']} — {experience['emotion']}")

        # Synthesize
        result = synthesize_game(genome, experience, target_category, dry_run=dry_run)

        if result["status"] == "success":
            # Inject lineage tags
            html = inject_lineage_tags(
                result["html"],
                result["parents"],
                result["genes_used"],
                result.get("experience"),
            )
            result["html"] = html

            # Determine category
            cat = target_category or _guess_category(genome, parents)
            folder = VALID_CATEGORIES.get(cat, "games-puzzles")

            # Write file
            if not dry_run:
                out_path = APPS_DIR / folder / result["filename"]
                # Avoid overwrites
                if out_path.exists():
                    stem = out_path.stem
                    suffix = random.randint(100, 999)
                    result["filename"] = f"{stem}-{suffix}.html"
                    out_path = APPS_DIR / folder / result["filename"]

                out_path.write_text(html)
                result["path"] = str(out_path)
                result["category"] = cat

                # Score the offspring
                offspring_score = score_game(out_path, html)
                result["score"] = offspring_score["score"]
                result["grade"] = offspring_score["grade"]

                if verbose:
                    print(f"  Offspring: {result['filename']} (score {result['score']}, grade {result['grade']})")
                    print(f"  Written to: {out_path}")

        results.append(result)

    return results


def _guess_category(genome: dict, parents: list) -> str:
    """Guess the best category for a recombinant based on genome and parents."""
    # If parents share a category, use it
    parent_cats = [p.get("category") for p in parents if p.get("category")]
    if parent_cats and len(set(parent_cats)) == 1:
        return parent_cats[0]

    # Otherwise, infer from dominant genes
    has_physics = "physics_engine" in genome and genome["physics_engine"]["strength"] >= 2
    has_audio = "audio_engine" in genome and genome["audio_engine"]["strength"] >= 2
    has_particles = "particle_system" in genome and genome["particle_system"]["strength"] >= 2
    has_entities = "entity_system" in genome and genome["entity_system"]["strength"] >= 2

    if has_physics and has_entities:
        return "games_puzzles"
    if has_audio:
        return "audio_music"
    if has_particles:
        return "particle_physics"
    return "games_puzzles"  # Default


def print_gene_catalog(catalog: dict):
    """Print a human-readable gene catalog."""
    print(f"\n{'='*70}")
    print("GENE CATALOG — Top Donor Apps")
    print(f"{'='*70}")

    for gene_name, donors in catalog.items():
        desc = GENE_PATTERNS[gene_name]["description"]
        print(f"\n  {gene_name} ({desc})")
        if donors:
            for d in donors[:3]:
                print(f"    [{d['strength']}/3] {d['file']} (score {d['score']})")
        else:
            print(f"    (no strong donors found)")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or "-v" in args
    list_genes = "--list-genes" in args

    if list_genes:
        catalog = catalog_genes()
        print_gene_catalog(catalog)
        return 0

    # Parse --count N
    count = 1
    if "--count" in args:
        idx = args.index("--count")
        if idx + 1 < len(args):
            count = int(args[idx + 1])

    # Parse --experience ID
    experience_id = None
    if "--experience" in args:
        idx = args.index("--experience")
        if idx + 1 < len(args):
            experience_id = args[idx + 1]

    # Parse --parents file1 file2
    parent_files = None
    if "--parents" in args:
        idx = args.index("--parents")
        parent_files = []
        for j in range(idx + 1, len(args)):
            if args[j].startswith("--"):
                break
            parent_files.append(args[j])

    # Parse --category
    target_category = None
    if "--category" in args:
        idx = args.index("--category")
        if idx + 1 < len(args):
            target_category = args[idx + 1]

    results = recombine(
        count=count,
        experience_id=experience_id,
        parent_files=parent_files,
        target_category=target_category,
        dry_run=dry_run,
        verbose=verbose,
    )

    # Summary
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "failed"]

    print(f"\nRecombination complete: {len(successes)} succeeded, {len(failures)} failed")
    for r in successes:
        print(f"  + {r.get('filename', '?')} (score {r.get('score', '?')}, grade {r.get('grade', '?')})")
        print(f"    Parents: {', '.join(r.get('parents', []))}")
        print(f"    Genes: {', '.join(r.get('genes_used', []))}")
        if r.get("experience"):
            print(f"    Experience: {r['experience']}")
    for r in failures:
        print(f"  x FAILED: {r.get('reason', 'unknown')}")

    return 0 if successes else 1


if __name__ == "__main__":
    sys.exit(main())
