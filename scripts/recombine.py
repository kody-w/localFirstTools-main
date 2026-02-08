#!/usr/bin/env python3
"""Genetic Recombination Engine — breed new content from top performers' DNA.

THE MEDIUM IS THE MESSAGE. Instead of creating apps from scratch or linearly
molting one forward, this engine extracts "traits" (proven patterns) from
high-scoring apps and recombines them into new organisms. Works with ANY
content type — games, synths, visualizers, tools — not just games.

Two modes:
  Adaptive (default): Uses content_identity to discover what each parent IS,
    what techniques it uses, what its strengths are. The LLM figures out what's
    worth combining. No fixed gene list.
  Classic (--classic): Uses 10 hardcoded game-specific gene patterns detected
    via regex. Fast but game-biased.

Usage:
    python3 scripts/recombine.py                              # Breed 1 app from top donors
    python3 scripts/recombine.py --count 5                    # Breed 5 apps
    python3 scripts/recombine.py --parents app1.html app2.html  # Specific parents
    python3 scripts/recombine.py --experience "discovery"     # Target experience
    python3 scripts/recombine.py --classic                    # Use regex gene detection
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
from content_identity import analyze as _analyze_content


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


# ---------------------------------------------------------------------------
# Adaptive Trait Discovery (content-agnostic, LLM-based)
# ---------------------------------------------------------------------------

def discover_traits(filepath, content=None):
    """Discover what an app IS and what patterns it uses, via content_identity.

    Unlike detect_genes() which uses hardcoded game-specific regex patterns,
    this works with ANY content type. The LLM discovers what's interesting.

    Returns dict with mode, medium, techniques, strengths, weaknesses, scores.
    Falls back to regex gene detection if LLM unavailable.
    """
    identity = _analyze_content(filepath, content=content)
    if not identity:
        # LLM unavailable — fall back to regex genes
        if content is None:
            content = Path(filepath).read_text(errors="replace")
        return {
            "mode": "regex",
            "medium": "unknown",
            "techniques": [],
            "strengths": [],
            "weaknesses": [],
            "genes": detect_genes(content),
        }

    return {
        "mode": "adaptive",
        "medium": identity.get("medium", "unknown"),
        "techniques": identity.get("techniques", []),
        "strengths": identity.get("strengths", []),
        "weaknesses": identity.get("weaknesses", []),
        "improvement_vectors": identity.get("improvement_vectors", []),
        "scores": {
            "craft": identity.get("craft_score", 0),
            "completeness": identity.get("completeness_score", 0),
            "engagement": identity.get("engagement_score", 0),
        },
    }


def build_adaptive_synthesis_prompt(parents_data, experience=None,
                                    target_category=None):
    """Build synthesis prompt using content identity instead of gene samples.

    THE MEDIUM IS THE MESSAGE. The prompt tells the LLM what each parent IS,
    what it does well, and asks it to breed something new. No fixed gene list.
    """
    parent_sections = []
    for pd in parents_data:
        traits = pd.get("traits", {})
        section = f"### Parent: {pd['file']} (score {pd['score']})\n"
        section += f"**Medium:** {traits.get('medium', 'unknown')}\n"
        if traits.get("techniques"):
            section += f"**Techniques:** {', '.join(traits['techniques'])}\n"
        if traits.get("strengths"):
            section += "**Strengths:**\n"
            for s in traits["strengths"]:
                section += f"  - {s}\n"
        if traits.get("weaknesses"):
            section += "**Weaknesses to avoid in offspring:**\n"
            for w in traits["weaknesses"]:
                section += f"  - {w}\n"
        # Include a content excerpt (the LLM needs to see actual code)
        content = pd.get("content", "")
        if content:
            excerpt = content[:8000]
            section += f"\n**Source (excerpt):**\n```html\n{excerpt}\n```\n"
        parent_sections.append(section)

    parents_text = "\n".join(parent_sections)

    experience_text = ""
    if experience:
        experience_text = f"""
## EXPERIENCE TARGET (the SOUL of the creation)

**Emotion:** {experience.get('emotion', 'engaging')}
**Feeling:** {experience.get('description', '')}

**Design direction:**
{chr(10).join('- ' + h for h in experience.get('mechanical_hints', []))}

**What to AVOID:**
{chr(10).join('- ' + a for a in experience.get('anti_patterns', []))}

Let the feeling DRIVE the design decisions. The experience target shapes
everything — interaction patterns, pacing, visual mood, audio character.
"""

    cat_hint = ""
    if target_category:
        cat_hint = f"\nTarget category: {target_category}\n"

    prompt = f"""You are a content genome synthesizer. You will create a brand-new, original HTML app
by recombining the best qualities of these parent apps. The offspring should be
BETTER than either parent — combining their strengths while avoiding their weaknesses.

Do NOT assume this must be a game. It could be anything: a music tool, art generator,
physics sim, data visualizer, educational tool, or something entirely new. Let the
parents' DNA guide what the offspring becomes.

CRITICAL RULES:
- Output ONLY the complete HTML file, nothing else
- Single self-contained HTML file with ALL CSS and JS inline
- <!DOCTYPE html>, <title>, <meta name="viewport"> required
- ZERO external dependencies (no CDNs, no APIs, no external files)
- Must work offline
- Must be genuinely compelling and interactive
- The offspring must feel like a coherent whole, not a Frankenstein of parts
- Combine the parents' BEST techniques into something that transcends both

## PARENT DNA

{parents_text}

{experience_text}
{cat_hint}

## SYNTHESIS INSTRUCTIONS

1. Study what each parent IS and what it does well
2. Identify complementary strengths that would be powerful together
3. Design an offspring that inherits the best of both parents
4. The offspring should be recognizably related to its parents but distinctly NEW
5. Implement completely — this should feel finished, not like a prototype
6. Add polish: smooth animations, responsive design, satisfying interactions
7. Ensure it works on both desktop (keyboard) and mobile (touch)
8. Make it something that would genuinely surprise and delight someone opening it

The bar is high — this offspring is bred from champions.

Output the complete HTML file now:"""

    return prompt


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
    """Build the LLM prompt that synthesizes a new app from genome + experience.

    Classic mode: uses hardcoded gene samples as architectural inspiration.
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
## EXPERIENCE TARGET (the SOUL of the creation)

**Emotion:** {experience.get('emotion', 'engaging')}
**Feeling:** {experience.get('description', '')}

**Design direction:**
{chr(10).join('- ' + h for h in experience.get('mechanical_hints', []))}

**What to AVOID:**
{chr(10).join('- ' + a for a in experience.get('anti_patterns', []))}

Let the feeling DRIVE the design decisions. The experience target shapes
everything — interaction patterns, pacing, visual mood, audio character.
"""

    # Category hint
    cat_hint = ""
    if target_category:
        cat_hint = f"\nTarget category: {target_category}\n"

    prompt = f"""You are a content genome synthesizer. You will create a brand-new, original HTML app
by recombining proven code patterns (genes) from top-scoring apps, guided by an
emotional experience target.

Do NOT assume this must be a game. The genes come from various content types.
Let the genetic material guide what the offspring becomes.

CRITICAL RULES:
- Output ONLY the complete HTML file, nothing else
- Single self-contained HTML file with ALL CSS and JS inline
- <!DOCTYPE html>, <title>, <meta name="viewport"> required
- ZERO external dependencies (no CDNs, no APIs, no external files)
- Must work offline
- Must be genuinely compelling and interactive
- DO NOT copy the gene samples verbatim — use them as INSPIRATION for your own implementation
- The creation must feel like a coherent whole, not a Frankenstein of parts

## GENETIC MATERIAL (proven patterns from high-scoring apps)

These are code patterns extracted from the best-performing apps in the gallery.
Use them as architectural inspiration — adapt the patterns to serve the experience target.

{genes_text}

{experience_text}
{cat_hint}

## SYNTHESIS INSTRUCTIONS

1. Start with the experience target — what should the user FEEL?
2. Choose patterns that serve that feeling (don't just pick the flashiest genes)
3. Implement a complete interaction loop appropriate to the content type
4. Include proper state management, error handling, and user feedback
5. Add polish: smooth animations, particle effects, sound feedback, satisfying interactions
6. Make it visually distinctive — custom color palette, animations, effects
7. Ensure responsive design (works on mobile)
8. Add keyboard AND mouse/touch controls where appropriate

Create something that would genuinely surprise and delight someone opening it in a browser.
The bar is high — this offspring is bred from champions.

Output the complete HTML file now:"""

    return prompt


def synthesize_adaptive(parents_data, experience=None, target_category=None,
                        dry_run=False):
    """Adaptive synthesis: breed a new app using content identity.

    Instead of fixed gene samples, sends parent identities + content excerpts
    to the LLM. The LLM discovers what's worth combining.

    Returns dict with: html, filename, title, metadata, lineage
    """
    prompt = build_adaptive_synthesis_prompt(parents_data, experience, target_category)
    parent_files = [pd["file"] for pd in parents_data]
    traits_used = []
    for pd in parents_data:
        traits = pd.get("traits", {})
        traits_used.extend(traits.get("techniques", []))
    traits_used = list(set(traits_used))

    if dry_run:
        return {
            "status": "dry_run",
            "prompt_size": len(prompt),
            "parents": parent_files,
            "traits_used": traits_used,
            "experience": experience.get("id") if experience else None,
        }

    backend = detect_backend()
    if backend == "unavailable":
        return {"status": "failed", "reason": "copilot-unavailable"}

    raw = copilot_call(prompt, timeout=180)
    if not raw:
        return {"status": "failed", "reason": "copilot-empty-response"}

    html = parse_llm_html(raw)
    if not html or len(html) < 500:
        return {"status": "failed", "reason": "output-too-small"}

    if "<!doctype html>" not in html.lower()[:200]:
        return {"status": "failed", "reason": "missing-doctype"}

    title_match = re.search(r"<title>(.*?)</title>", html)
    title = title_match.group(1).strip() if title_match else "Untitled Recombinant"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    filename = f"{slug}.html"

    return {
        "status": "success",
        "html": html,
        "filename": filename,
        "title": title,
        "traits_used": traits_used,
        "parents": parent_files,
        "experience": experience.get("id") if experience else None,
        "size": len(html),
    }


def synthesize_game(genome: dict, experience: dict = None, target_category: str = None,
                    dry_run: bool = False) -> dict:
    """Classic synthesis: use regex-detected gene samples to breed a new app.

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
              target_category: str = None, dry_run: bool = False, verbose: bool = False,
              adaptive: bool = True) -> list:
    """Main recombination pipeline. Breed `count` new apps.

    Args:
        adaptive: If True (default), use content_identity for trait discovery.
                  If False, use classic regex-based gene detection.

    Returns list of result dicts.
    """
    results = []

    for i in range(count):
        if verbose:
            print(f"\n{'='*60}")
            print(f"RECOMBINATION {i+1}/{count} ({'adaptive' if adaptive else 'classic'} mode)")
            print(f"{'='*60}")

        # Select parents
        if parent_files:
            parents = []
            for pf in parent_files:
                filepath = None
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

        # Load experience
        experience = load_experience(experience_id) if experience_id else load_experience()
        if verbose and experience:
            print(f"  Experience: {experience['id']} — {experience['emotion']}")

        if adaptive:
            # Adaptive path: discover traits via content identity
            parents_data = []
            for p in parents:
                traits = discover_traits(p["path"], p["content"])
                p["traits"] = traits
                parents_data.append({
                    "file": p["file"],
                    "score": p["score"],
                    "traits": traits,
                    "content": p["content"],
                })
                if verbose:
                    medium = traits.get("medium", "unknown")
                    techs = ", ".join(traits.get("techniques", [])[:5])
                    print(f"  Parent: {p['file']} (score {p['score']}) medium: {medium}")
                    if techs:
                        print(f"    techniques: {techs}")

            result = synthesize_adaptive(parents_data, experience, target_category, dry_run=dry_run)
        else:
            # Classic path: regex gene detection + crossover
            if verbose:
                for p in parents:
                    gene_list = [g for g, info in p["genes"].items() if info["present"]]
                    print(f"  Parent: {p['file']} (score {p['score']}) genes: {', '.join(gene_list)}")

            genome = crossover(parents)
            if verbose:
                print(f"  Genome: {', '.join(genome.keys())}")

            result = synthesize_game(genome, experience, target_category, dry_run=dry_run)

        if result["status"] == "success":
            # Inject lineage tags
            lineage_items = result.get("genes_used") or result.get("traits_used") or []
            parent_list = result.get("parents", [])
            html = inject_lineage_tags(
                result["html"],
                parent_list,
                lineage_items,
                result.get("experience"),
            )
            result["html"] = html

            # Determine category
            cat = target_category or _guess_category(
                result.get("genes_used") if not adaptive else None,
                parents,
                html=html if adaptive else None,
            )
            folder = VALID_CATEGORIES.get(cat, "experimental-ai")

            # Write file
            if not dry_run:
                out_path = APPS_DIR / folder / result["filename"]
                if out_path.exists():
                    stem = out_path.stem
                    suffix = random.randint(100, 999)
                    result["filename"] = f"{stem}-{suffix}.html"
                    out_path = APPS_DIR / folder / result["filename"]

                out_path.write_text(html)
                result["path"] = str(out_path)
                result["category"] = cat

                offspring_score = score_game(out_path, html)
                result["score"] = offspring_score["score"]
                result["grade"] = offspring_score["grade"]

                if verbose:
                    print(f"  Offspring: {result['filename']} (score {result['score']}, grade {result['grade']})")
                    print(f"  Written to: {out_path}")

        results.append(result)

    return results


def _guess_category(genome_or_traits, parents, html=None):
    """Guess the best category for a recombinant.

    Works with both classic genome dict and adaptive trait lists.
    Uses content identity on the offspring HTML when available.
    """
    # If parents share a category, use it
    parent_cats = [p.get("category") for p in parents
                   if p.get("category") and p.get("category") != "unknown"]
    if parent_cats and len(set(parent_cats)) == 1:
        return parent_cats[0]

    # Adaptive: analyze the offspring HTML directly
    if html:
        identity = _analyze_content(Path("/tmp/offspring.html"), content=html, use_cache=False)
        if identity:
            medium = identity.get("medium", "").lower()
            # Map medium keywords to categories
            category_keywords = {
                "audio_music": ["synth", "music", "audio", "sound", "daw", "drum", "beat", "tone"],
                "visual_art": ["drawing", "paint", "sketch", "design", "color", "art tool"],
                "generative_art": ["fractal", "generative", "procedural", "algorithmic", "mandelbrot"],
                "3d_immersive": ["3d", "webgl", "three.js", "voxel", "immersive"],
                "particle_physics": ["particle", "physics sim", "gravity sim", "n-body"],
                "games_puzzles": ["game", "puzzle", "platformer", "shooter", "rpg", "arcade"],
                "creative_tools": ["editor", "converter", "calculator", "tool", "utility", "planner"],
                "educational_tools": ["tutorial", "learn", "educational", "quiz", "flashcard"],
            }
            for cat, keywords in category_keywords.items():
                if any(kw in medium for kw in keywords):
                    return cat
            # Check parent mediums for hints
            for p in parents:
                traits = p.get("traits", {})
                if traits.get("medium"):
                    p_medium = traits["medium"].lower()
                    for cat, keywords in category_keywords.items():
                        if any(kw in p_medium for kw in keywords):
                            return cat

    # Classic: infer from genome dict
    if genome_or_traits and isinstance(genome_or_traits, dict):
        genome = genome_or_traits
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

    return "experimental_ai"  # Catch-all (not games_puzzles)


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
    classic = "--classic" in args
    adaptive = not classic

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

    if verbose:
        print(f"Mode: {'adaptive' if adaptive else 'classic'}")

    results = recombine(
        count=count,
        experience_id=experience_id,
        parent_files=parent_files,
        target_category=target_category,
        dry_run=dry_run,
        verbose=verbose,
        adaptive=adaptive,
    )

    # Summary
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "failed"]

    print(f"\nRecombination complete: {len(successes)} succeeded, {len(failures)} failed")
    for r in successes:
        print(f"  + {r.get('filename', '?')} (score {r.get('score', '?')}, grade {r.get('grade', '?')})")
        print(f"    Parents: {', '.join(r.get('parents', []))}")
        lineage = r.get("genes_used") or r.get("traits_used") or []
        if lineage:
            print(f"    {'Genes' if not adaptive else 'Traits'}: {', '.join(lineage)}")
        if r.get("experience"):
            print(f"    Experience: {r['experience']}")
    for r in failures:
        print(f"  x FAILED: {r.get('reason', 'unknown')}")

    return 0 if successes else 1


if __name__ == "__main__":
    sys.exit(main())
