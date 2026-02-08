#!/usr/bin/env python3
"""Generate RappterZooNation podcast episodes.

Two hosts — Rapptr (enthusiastic optimist) and ZooKeeper (critical realist) —
discuss actual RappterZoo apps with real scores, community data, and deep links.

Usage:
    python3 scripts/generate_broadcast.py                    # Generate next episode
    python3 scripts/generate_broadcast.py --verbose          # Show generation details
    python3 scripts/generate_broadcast.py --push             # Generate + commit + push
    python3 scripts/generate_broadcast.py --frame N          # Generate for specific frame
    python3 scripts/generate_broadcast.py --regenerate-all   # Regenerate all episodes

Output: apps/broadcasts/feed.json
"""

import json
import random
import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
RANKINGS = APPS_DIR / "rankings.json"
COMMUNITY = APPS_DIR / "community.json"
MOLTER_STATE = APPS_DIR / "molter-state.json"
BROADCAST_DIR = APPS_DIR / "broadcasts"
FEED_FILE = BROADCAST_DIR / "feed.json"
LORE_FILE = BROADCAST_DIR / "lore.json"

SITE_BASE = "https://kody-w.github.io/localFirstTools-main"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

# ── Host Definitions ──────────────────────────────────────────────

HOSTS = {
    "Rapptr": {
        "color": "#00e5ff",
        "avatar": "rapptr",
        "bio": "Enthusiastic optimist. Gets excited about weird experimental stuff. Sees the beauty in broken games. Will play anything once — and probably twice.",
    },
    "ZooKeeper": {
        "color": "#ff6e40",
        "avatar": "zookeeper",
        "bio": "Critical realist. Data-driven. Cares about quality scores and playability. Snarky but fair. Respects craftsmanship over ambition.",
    },
}

# ── Dialogue Vocabulary ──────────────────────────────────────────

RAPPTR_INTROS = [
    "OK so this one — {title} — I've been playing this all week and I can't stop.",
    "Alright next up is {title} and honestly? I was NOT ready for this.",
    "So {title} dropped and — oh man — the creativity here is off the charts.",
    "Let me tell you about {title}. This one surprised me in the best way.",
    "{title} — I know, I know, another {category} app — but hear me out.",
    "OK buckle up because {title} is something else entirely.",
    "So I pulled up {title} expecting the usual — and then it just kept going.",
    "You gotta check out {title}. I've had it open in a tab for three days.",
]

ZOOKEEPER_INTROS = [
    "Let's look at the data. {title}: {score} out of 100, {grade}-grade.",
    "{title}. {score} points. {grade}-grade. Let's see if the numbers tell the truth.",
    "OK, {title}. Score: {score}. Grade: {grade}. Playability: {playability} out of 25.",
    "The algorithm gave {title} a {score}. {grade}-grade. Here's why.",
    "{title} — {score} points. That's {verdict} for a {category} app.",
    "Numbers first. {title}: {score}, {grade}-grade, {playability} playability.",
]

RAPPTR_TAG_REACTIONS = {
    "canvas": [
        "The rendering on this is BUTTER smooth",
        "Canvas work here is next level — zero frame drops",
        "You can feel how tight the draw loop is",
    ],
    "3d": [
        "The 3D in this is wild — it feels like a proper game engine",
        "I keep rotating the camera just because the 3D looks that good",
        "The depth here pulls you right in",
    ],
    "physics": [
        "The physics! THE PHYSICS! You can just mess around for hours",
        "Everything has weight and momentum — it feels real",
        "I spent twenty minutes just throwing things around",
    ],
    "audio": [
        "Put headphones on for this one — the audio is incredible",
        "The sound design CARRIES this entire experience",
        "Every action has this satisfying audio feedback",
    ],
    "music": [
        "I literally just leave this running for the music",
        "The music generation is genuinely musical — like, actually good",
        "I made a beat in five minutes and it actually slapped",
    ],
    "game": [
        "This is a REAL game — not a tech demo, a real game with depth",
        "The gameplay loop kept me hooked way longer than I planned",
        "The core mechanic here is so solid",
    ],
    "puzzle": [
        "These puzzles made me feel genuinely smart when I solved them",
        "The puzzle design teaches you through play — no tutorial needed",
        "I was staring at one puzzle for ten minutes and the aha moment? Chef's kiss",
    ],
    "animation": [
        "The animations here are FLUID — like, hypnotic levels of smooth",
        "Every transition is so intentional",
        "60fps with these animations? How?!",
    ],
    "particle": [
        "I spawned a thousand particles and it didn't even blink",
        "The particle interactions create these beautiful emergent patterns",
        "The trails alone are worth opening this up",
    ],
    "simulation": [
        "I left this running for an hour and came back to chaos — beautiful chaos",
        "The simulation depth is wild for a browser tab",
        "Tweak one setting and the whole system shifts — so addictive",
    ],
    "creative": [
        "I made something I'm actually proud of in my first session",
        "This tool is expressive without being overwhelming",
        "I exported my creation and people thought it was a real app",
    ],
    "procedural": [
        "Two sessions in and I haven't seen the same thing twice",
        "The procedural generation here produces genuinely interesting results",
        "Every output has character — not just random noise",
    ],
    "ai": [
        "The AI in this actually surprised me — it ADAPTS",
        "I watched the AI make a move I didn't see coming and had to rethink everything",
        "The emergent behavior is fascinating to watch unfold",
    ],
    "rpg": [
        "The character progression gives you that real RPG power fantasy",
        "My second playthrough was completely different — build variety is real",
        "Loot system? Skill trees? In a single HTML file?! Come on!",
    ],
    "synth": [
        "I made an actual track with this — the interface just CLICKS",
        "The oscillator range is surprisingly deep",
        "Layer some voices and you get textures you wouldn't expect from Web Audio",
    ],
    "strategy": [
        "The strategic depth caught me off guard — real meaningful choices",
        "You can see your strategy paying off over time and it's SO satisfying",
        "Lost my first game, won my second — actually learned something",
    ],
    "horror": [
        "OK so I played this at night with headphones and had to take a BREAK",
        "The atmosphere genuinely unsettled me — in a browser. In a browser!",
        "The ambient dread is more effective than most triple-A horror",
    ],
    "space": [
        "The scale of space is communicated so well — you feel TINY",
        "Navigating between systems has that perfect sense of vastness",
        "The star field alone is mesmerizing",
    ],
}

ZOOKEEPER_TAG_REACTIONS = {
    "canvas": [
        "Canvas rendering is technically solid — no complaints on the draw pipeline",
        "The canvas implementation is clean, which is why it performs",
        "Proper canvas usage — not just a glorified div",
    ],
    "3d": [
        "3D is resource-heavy and they managed to keep it performant — respect",
        "The 3D math checks out — perspective and depth are accurate",
        "Getting this level of 3D in a single file is genuine engineering",
    ],
    "physics": [
        "Physics simulation has proper collision detection — not faked",
        "The physics constants are tuned realistically — someone did the math",
        "Momentum conservation is correct. That's harder than it sounds",
    ],
    "audio": [
        "Web Audio API used well here — spatial placement, proper gain staging",
        "Audio implementation is above average for this category",
        "Sound design adds to the experience without masking weak gameplay",
    ],
    "music": [
        "The music follows actual theory — proper scales and progressions",
        "Harmonic content is procedural but structured — not random note spam",
        "The rhythm engine has real timing — not just quantized grid snaps",
    ],
    "game": [
        "It has a game loop, win condition, and difficulty curve — that's more than most",
        "Core loop is solid. The fundamentals are there",
        "This passes the 'would I play this twice' test. Barely",
    ],
    "puzzle": [
        "Puzzle difficulty curve is well-calibrated — no spike, no plateau",
        "Logic puzzles with actual valid solutions, not brute-force guessing",
        "Puzzle design shows understanding of player cognition",
    ],
    "animation": [
        "Animation timing is frame-rate independent — proper implementation",
        "Easing curves are appropriate for each context — someone knows UX",
        "Smooth animations that don't tank performance. The bar is low but they cleared it",
    ],
    "particle": [
        "Particle system is optimized — object pooling, no garbage collection spikes",
        "Thousands of particles without stutter means the renderer is doing its job",
        "The particle physics are approximate but convincing",
    ],
    "simulation": [
        "Simulation state is deterministic — same inputs, same outputs. That's proper",
        "The feedback loops are intentional, not accidental complexity",
        "Simulation depth is the main selling point, and it delivers",
    ],
    "creative": [
        "Tool UX is functional — not fighting the interface to create",
        "Export/import works, which is more than I can say for most creative tools here",
        "The creative constraints are designed, not just limitations",
    ],
    "procedural": [
        "Procedural generation with proper seed support — reproducible results",
        "Output quality is consistent across seeds — no degenerate cases",
        "The generation constraints prevent garbage output. Smart design",
    ],
    "ai": [
        "AI decision-making has real state — not just random choice each frame",
        "The AI adapts to player behavior. That takes real implementation effort",
        "Emergent AI behavior from simple rules — proper complex systems design",
    ],
    "rpg": [
        "Stat scaling is balanced — you progress without becoming trivially overpowered",
        "Build variety means replay value, which boosts the score",
        "RPG systems are interconnected, not just bolted-on number increases",
    ],
    "synth": [
        "Oscillator implementation uses proper Web Audio nodes — not hacks",
        "The signal chain is correct — oscillator to filter to envelope to output",
        "Patch persistence via localStorage is a nice touch. Data isn't lost",
    ],
    "strategy": [
        "Strategic depth from emergent systems, not just more options to click",
        "Economy balance means decisions matter — no dominant strategy",
        "Information is presented clearly for decision-making. Good UX for strategy",
    ],
    "horror": [
        "Atmosphere is achieved through design, not just jump scares. Respect",
        "The pacing of tension and release is deliberate and effective",
        "Horror that works in a browser is harder than it sounds. This pulls it off",
    ],
    "space": [
        "Scale visualization is mathematically convincing",
        "The orbital mechanics are approximated but feel right",
        "Space aesthetic is well-executed — the void actually feels empty",
    ],
}

RAPPTR_SCORE_REACTIONS = {
    "S": [
        "S-GRADE! This is the top of the top!",
        "An S-grade! That's legendary status right there!",
        "We're talking S-grade — the cream of the crop!",
    ],
    "A": [
        "A-grade! That's seriously impressive!",
        "Solid A-grade — this is premium quality!",
        "A-grade means this is in the top tier!",
    ],
    "B": [
        "B-grade is nothing to sneeze at — lots of good stuff here!",
        "A B-grade shows real effort and real results!",
        "B-grade — above average and getting better!",
    ],
    "C": [
        "C-grade — hey, there's potential here!",
        "OK it's a C but you can SEE the vision, right?",
        "C-grade with room to grow — after a molt, who knows!",
    ],
    "D": [
        "Look, it's a D, but there's something here. I can feel it!",
        "D-grade but the CONCEPT is cool, you gotta admit",
        "Sure it's a D right now, but molting exists for a reason!",
    ],
    "F": [
        "OK yes it's an F BUT — hear me out — the idea is interesting!",
        "F-grade. Yeah. I know. But there's a kernel of something here!",
        "F. I know. I KNOW. But look at what they were TRYING to do!",
    ],
}

ZOOKEEPER_SCORE_REACTIONS = {
    "S": [
        "S-grade. Top 1%. The numbers speak for themselves.",
        "S-grade means near-perfect across all six dimensions. Earned, not given.",
        "An S. Structural, systems, completeness, playability — all maxed. Rare air.",
    ],
    "A": [
        "A-grade. High marks across the board. Solid craftsmanship.",
        "A-grade — strong technically and fun to play. That's hard to achieve.",
        "The A-grade is deserved. Minor gaps but nothing critical.",
    ],
    "B": [
        "B-grade. Above median. Good foundation but room for improvement.",
        "B means the fundamentals are there. A molt or two could push this higher.",
        "Solid B. Not exceptional but competent. I'll take competent.",
    ],
    "C": [
        "C-grade. Average. The median score is 49, so this is... median.",
        "C means it works but doesn't stand out. The ecosystem has 530 apps.",
        "Middle of the pack. A C is a C. No sugar-coating that.",
    ],
    "D": [
        "D-grade. Below average on most dimensions. Needs work.",
        "The D tells you what needs fixing. Low playability, missing systems.",
        "D-grade. Concept over execution. Common pattern in this ecosystem.",
    ],
    "F": [
        "F. Missing fundamentals. No game loop, no real interaction.",
        "F-grade. Below the minimum viable threshold on multiple axes.",
        "An F means structural issues plus missing core systems. Needs a rewrite.",
    ],
}

RAPPTR_COMMENT_REACTIONS = [
    "{author} in the comments said \"{comment}\" — and honestly? Same.",
    "Oh and {author} wrote \"{comment}\" — couldn't agree more!",
    "Check out what {author} said: \"{comment}\" — that's the community talking!",
    "{author} nailed it: \"{comment}\"",
    "And {author} goes \"{comment}\" — YES! Exactly!",
    "The community gets it — {author} said \"{comment}\"",
]

ZOOKEEPER_COMMENT_REACTIONS = [
    "{author} commented \"{comment}\" — {upvotes} upvotes. Community validates.",
    "\"{comment}\" — that's from {author}. {upvotes} people agreed.",
    "{author}: \"{comment}\" — with {upvotes} upvotes. The data aligns with sentiment.",
    "Top comment from {author}: \"{comment}\" — {upvotes} upvotes says it all.",
]

RAPPTR_RATING_REACTIONS = [
    "{ratings} ratings and a {avg:.1f} average — the people have SPOKEN!",
    "With {ratings} ratings at {avg:.1f} stars? The community loves this!",
    "{avg:.1f} stars across {ratings} ratings — that's community approval right there!",
]

ZOOKEEPER_RATING_REACTIONS = [
    "{ratings} ratings, {avg:.1f} average. Statistically significant sample size.",
    "{avg:.1f} stars from {ratings} raters. The crowd score tracks with the algorithm.",
    "Community gave it {avg:.1f} across {ratings} ratings. {verdict}",
]

RAPPTR_ROAST_OPENERS = [
    "OK so... the Roast Pit. I hate this segment. But ZooKeeper LIVES for it.",
    "Roast time. I always try to find the silver lining but ZooKeeper — go ahead.",
    "The Roast Pit segment, everybody. Where dreams go to get constructive feedback.",
    "Alright, Roast Pit. Who are we... evaluating with love... this week?",
]

ZOOKEEPER_ROAST_LINES = [
    "This scored a {score}. Out of 100. Let that sink in.",
    "{title}. {score} points. Where do I even begin.",
    "So {title} exists. With a score of {score}. I have questions.",
    "Let's talk about {title}. Or as the ranking algorithm calls it: practice.",
    "{score} points. The playability score is {playability}. Out of 25. That's a {pct:.0f}%.",
]

RAPPTR_ROAST_DEFENSE = [
    "But hey — look, the CONCEPT is cool even if the execution isn't there yet!",
    "OK BUT — imagine this after a few molts? There's potential!",
    "Sure the score is low but someone built this! That takes courage!",
    "I choose to see this as a rough draft with ambition!",
    "Every S-grade started somewhere! This is the beginning of a journey!",
]

EPISODE_TITLE_TEMPLATES = [
    "Ep. {n}: {top_title} and the State of the Zoo",
    "Ep. {n}: The {category} Edition",
    "Ep. {n}: {top_title} Blew Our Minds",
    "Ep. {n}: From S-Grade to Dumpster Fire",
    "Ep. {n}: {count} Games, One Podcast",
    "Ep. {n}: Best and Worst of Frame {frame}",
    "Ep. {n}: Hidden Gems and Public Disasters",
    "Ep. {n}: {top_title} vs. Everything Else",
]

INTRO_TEMPLATES = [
    "Welcome to RappterZooNation! I'm Rapptr, and with me as always is ZooKeeper. We've got {count} apps in the ecosystem, frame {frame}, and today we're diving into {num_reviews} of them.",
    "Hey everybody, it's RappterZooNation episode {n}! I'm Rapptr — you know the deal. {count} apps, {num_reviews} reviews, let's get into it.",
    "RappterZooNation, episode {n}! The autonomous arcade now has {count} apps and we've got {num_reviews} to talk about today. Let's GO!",
    "Welcome back to RappterZooNation! {count} apps in the ecosystem and growing. I'm Rapptr, ZooKeeper's here looking grumpy as usual, and we've got {num_reviews} apps to break down.",
]

ZOOKEEPER_INTRO_RESPONSES = [
    "I'm not grumpy, I'm data-driven. There's a difference. Let's see what the scores say.",
    "Hey. The median score is still {median}. We have work to do. Let's talk about who's doing it right.",
    "Greetings. The algorithm doesn't sleep. Neither does quality assessment. Let's begin.",
    "Present. And for the record, I smiled once last frame when something scored above 90. Let's go.",
]

OUTRO_TEMPLATES = [
    "That's a wrap on episode {n} of RappterZooNation! {count} apps in the ecosystem, every single one a self-contained world in a single HTML file. Find them all at rappterzoo. I'm Rapptr — see you next frame!",
    "Episode {n}, done! If you liked any of the apps we talked about, go play them — they're all free, all in-browser, all one file. I'm Rapptr, that's ZooKeeper, and this has been RappterZooNation. Later!",
    "RappterZooNation episode {n} in the books! Go play {top_title} if you haven't yet. Links in the transcript. Until next frame — Rapptr out!",
]

ZOOKEEPER_OUTROS = [
    "Check the rankings. Play the S-grades. Skip the F-grades. See you next frame.",
    "The data will be updated next frame. Until then — play something with a decent score.",
    "Rankings don't lie. Scores are public. May your playability be high. ZooKeeper out.",
]

# ── Transition Lines ──────────────────────────────────────────────

TRANSITIONS = [
    "Moving on—",
    "Next up—",
    "Alright, next one—",
    "OK shifting gears—",
    "Let's keep it rolling—",
]

# ── Lore Callback Templates ──────────────────────────────────────

RAPPTR_LORE_CALLBACKS = [
    "Remember when we talked about {app}? It was a {old_grade} back then — now look at it!",
    "We covered {app} back in episode {ep} and I said it had potential — told ya!",
    "{app} is back! We gave it a {old_grade} last time — let's see what changed.",
    "Wait — {app} again? We reviewed this in episode {ep}. {event}",
    "Our recurring champion {app} — episode {ep} listeners know this one.",
]

ZOOKEEPER_LORE_CALLBACKS = [
    "{app} was a {old_grade} when we last saw it in episode {ep}. Now it's a {new_grade}. {verdict}",
    "Episode {ep} — I gave {app} a hard time at {old_score} points. Current score: {new_score}. {verdict}",
    "History check: {app}, episode {ep}, score {old_score}. Today: {new_score}. {verdict}",
    "We've tracked {app} across {appearances} episodes now. The trajectory is {trend}.",
]

RAPPTR_RUNNING_JOKE_LINES = [
    "Another {category} app! That's {count} this season — the {category} renaissance continues!",
    "Are we a {category} podcast now? {count} in a row!",
    "I'm keeping count — {count} {category} apps we've covered. It's a theme.",
]

ZOOKEEPER_MILESTONE_LINES = [
    "Milestone: this is our {ep_count}th episode. We've reviewed {total_reviewed} apps total.",
    "Fun fact: across {ep_count} episodes, the average score of apps we've reviewed is {avg_reviewed_score:.0f}.",
    "We've now covered {pct:.0f}% of the entire ecosystem. {remaining} apps still untouched.",
]


def load_lore():
    """Load the lore tracker — persistent history across episodes."""
    if LORE_FILE.exists():
        with open(LORE_FILE) as f:
            return json.load(f)
    return {
        "reviewed_apps": {},      # file -> {episodes: [ep_nums], scores: [scores], grades: [grades]}
        "category_counts": {},    # category -> count of times featured
        "total_reviewed": 0,      # total app reviews across all episodes
        "running_jokes": [],      # list of {type, data, started_ep}
        "milestones": [],         # list of {type, ep, value}
        "episode_summaries": [],  # list of {ep, title, apps_reviewed, top_score, date}
    }


def save_lore(lore):
    """Save lore tracker to disk."""
    BROADCAST_DIR.mkdir(parents=True, exist_ok=True)
    with open(LORE_FILE, "w") as f:
        json.dump(lore, f, indent=2)


def update_lore(lore, episode):
    """Update lore with data from a new episode."""
    ep_num = episode["number"]
    reviewed_files = []

    for seg in episode.get("segments", []):
        if seg.get("type") in ("review", "roast") and seg.get("app"):
            app = seg["app"]
            file_key = app["file"]
            reviewed_files.append(file_key)

            # Track per-app history
            if file_key not in lore["reviewed_apps"]:
                lore["reviewed_apps"][file_key] = {
                    "title": app["title"],
                    "episodes": [],
                    "scores": [],
                    "grades": [],
                }
            entry = lore["reviewed_apps"][file_key]
            entry["episodes"].append(ep_num)
            entry["scores"].append(app.get("score", 0))
            entry["grades"].append(app.get("grade", "?"))
            entry["title"] = app["title"]  # Update to latest title

            # Track category frequency
            cat = app.get("category", "unknown")
            lore["category_counts"][cat] = lore["category_counts"].get(cat, 0) + 1

    lore["total_reviewed"] += len(reviewed_files)

    # Episode summary
    top_score = 0
    for seg in episode.get("segments", []):
        if seg.get("app"):
            top_score = max(top_score, seg["app"].get("score", 0))

    lore["episode_summaries"].append({
        "ep": ep_num,
        "title": episode["title"],
        "apps_reviewed": reviewed_files,
        "top_score": top_score,
        "date": episode.get("generated", ""),
    })

    # Keep summaries manageable
    lore["episode_summaries"] = lore["episode_summaries"][-100:]

    return lore


def generate_lore_dialogue(app, lore, episode_number, rng):
    """Generate lore-aware dialogue lines if this app has been reviewed before."""
    lines = []
    file_key = app["file"]

    if file_key not in lore.get("reviewed_apps", {}):
        return lines

    history = lore["reviewed_apps"][file_key]
    past_episodes = history.get("episodes", [])
    past_scores = history.get("scores", [])
    past_grades = history.get("grades", [])

    if not past_episodes:
        return lines

    last_ep = past_episodes[-1]
    old_score = past_scores[-1] if past_scores else 0
    old_grade = past_grades[-1] if past_grades else "?"
    new_score = app.get("score", 0)
    new_grade = app.get("grade", "?")
    appearances = len(past_episodes)

    # Determine trajectory
    if len(past_scores) >= 2:
        if new_score > past_scores[-1]:
            trend = "upward"
            verdict = "Progress."
        elif new_score < past_scores[-1]:
            trend = "downward"
            verdict = "Regression."
        else:
            trend = "flat"
            verdict = "No change."
    else:
        trend = "emerging"
        verdict = "Let's see where this goes."

    # Override verdict with more specific takes
    if new_score >= 90 and old_score < 80:
        verdict = "A massive leap. Molting works."
    elif new_score < old_score - 10:
        verdict = "How did it get worse? That's rare."
    elif new_score == old_score:
        verdict = "Exactly the same score. Suspicious."

    event = f"Score went from {old_score} to {new_score}."

    # Rapptr callback
    rapptr_line = rng.choice(RAPPTR_LORE_CALLBACKS).format(
        app=app["title"], old_grade=old_grade, ep=last_ep, event=event
    )
    lines.append({"host": "Rapptr", "text": rapptr_line})

    # ZooKeeper callback
    zoo_line = rng.choice(ZOOKEEPER_LORE_CALLBACKS).format(
        app=app["title"], old_grade=old_grade, new_grade=new_grade,
        ep=last_ep, old_score=old_score, new_score=new_score,
        verdict=verdict, appearances=appearances, trend=trend
    )
    lines.append({"host": "ZooKeeper", "text": zoo_line})

    return lines


def generate_milestone_dialogue(lore, episode_number, total_apps, rng):
    """Generate milestone/meta commentary if we hit interesting numbers."""
    lines = []
    ep_count = len(lore.get("episode_summaries", [])) + 1  # +1 for current

    # Every 5th episode gets a milestone line
    if ep_count % 5 == 0 or ep_count == 1:
        total_reviewed = lore.get("total_reviewed", 0)
        avg_score = 0
        all_scores = []
        for app_data in lore.get("reviewed_apps", {}).values():
            all_scores.extend(app_data.get("scores", []))
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)

        remaining = max(0, total_apps - len(lore.get("reviewed_apps", {})))
        pct = (len(lore.get("reviewed_apps", {})) / total_apps * 100) if total_apps else 0

        line = rng.choice(ZOOKEEPER_MILESTONE_LINES).format(
            ep_count=ep_count, total_reviewed=total_reviewed,
            avg_reviewed_score=avg_score, pct=pct, remaining=remaining
        )
        lines.append({"host": "ZooKeeper", "text": line})

    # Category streak detection
    cat_counts = lore.get("category_counts", {})
    for cat, count in cat_counts.items():
        if count >= 3 and count % 3 == 0:
            cat_line = rng.choice(RAPPTR_RUNNING_JOKE_LINES).format(
                category=cat.replace("_", " "), count=count
            )
            lines.append({"host": "Rapptr", "text": cat_line})
            break  # One joke per episode

    return lines


def log(msg):
    if VERBOSE:
        print(f"  [broadcast] {msg}")


def load_json(path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_app_stem(filename):
    """Get the stem key used in community.json (filename without .html)."""
    return Path(filename).stem


def build_app_index(manifest, rankings, community):
    """Build a unified index of all apps with scores, community data, etc."""
    index = {}

    # Index manifest entries by file
    cat_map = {}
    for cat_key, cat_data in manifest.get("categories", {}).items():
        folder = cat_data.get("folder", cat_key.replace("_", "-"))
        for app in cat_data.get("apps", []):
            key = app["file"]
            index[key] = {
                "title": app.get("title", key),
                "file": key,
                "category": cat_key,
                "folder": folder,
                "category_title": cat_data.get("title", cat_key),
                "description": app.get("description", ""),
                "tags": app.get("tags", []),
                "complexity": app.get("complexity", "intermediate"),
                "type": app.get("type", "interactive"),
                "path": f"apps/{folder}/{key}",
                "url": f"{SITE_BASE}/apps/{folder}/{key}",
                "score": 0,
                "grade": "F",
                "playability": 0,
                "community": {"avgRating": 0, "totalRatings": 0, "totalComments": 0, "topComments": []},
            }
            cat_map[key] = cat_key

    # Merge ranking data
    if rankings:
        for entry in rankings.get("rankings", []):
            key = entry.get("file", "")
            if key in index:
                index[key]["score"] = entry.get("score", 0)
                index[key]["grade"] = entry.get("grade", "F")
                playability_dim = entry.get("dimensions", {}).get("playability", {})
                index[key]["playability"] = playability_dim.get("score", 0)

    # Merge community data
    if community:
        comments = community.get("comments", {})
        ratings = community.get("ratings", {})

        for key, app in index.items():
            stem = get_app_stem(key)
            # Comments
            app_comments = comments.get(stem, [])
            all_comments = []
            for c in app_comments:
                all_comments.append(c)
                for child in c.get("children", []):
                    all_comments.append(child)
            all_comments.sort(key=lambda x: x.get("upvotes", 0), reverse=True)
            top = all_comments[:3]

            # Ratings
            app_ratings = ratings.get(stem, [])
            stars = [r.get("stars", 3) for r in app_ratings]
            avg = sum(stars) / len(stars) if stars else 0

            app["community"] = {
                "avgRating": round(avg, 1),
                "totalRatings": len(app_ratings),
                "totalComments": len(all_comments),
                "topComments": [
                    {"author": c.get("author", "anon"), "text": c.get("text", ""), "upvotes": c.get("upvotes", 0)}
                    for c in top
                ],
            }

    return index


def select_episode_apps(index, rng, frame):
    """Select 3-5 apps for this episode using diverse criteria."""
    apps = list(index.values())
    if not apps:
        return []

    selected = []
    used_files = set()

    # 1. Top scoring app (highlight)
    by_score = sorted(apps, key=lambda a: a["score"], reverse=True)
    for app in by_score:
        if app["file"] not in used_files:
            selected.append(app)
            used_files.add(app["file"])
            break

    # 2. Trending — highest community activity
    by_activity = sorted(apps, key=lambda a: a["community"]["totalComments"] + a["community"]["totalRatings"], reverse=True)
    for app in by_activity:
        if app["file"] not in used_files:
            selected.append(app)
            used_files.add(app["file"])
            break

    # 3. Hidden gem — good score (60+) but low community attention
    gems = [a for a in apps if a["score"] >= 60 and a["community"]["totalRatings"] < 20 and a["file"] not in used_files]
    if gems:
        gem = rng.choice(gems)
        selected.append(gem)
        used_files.add(gem["file"])

    # 4. Random pick from a random category (for variety)
    categories = list(set(a["category"] for a in apps))
    if categories:
        cat = rng.choice(categories)
        cat_apps = [a for a in apps if a["category"] == cat and a["file"] not in used_files and a["score"] >= 30]
        if cat_apps:
            pick = rng.choice(cat_apps)
            selected.append(pick)
            used_files.add(pick["file"])

    # 5. Worst app (for roast segment)
    by_score_asc = sorted(apps, key=lambda a: a["score"])
    for app in by_score_asc:
        if app["file"] not in used_files and app["score"] > 0:
            selected.append(app)
            used_files.add(app["file"])
            break

    # Shuffle the middle reviews (keep first as top pick, last as roast)
    if len(selected) > 2:
        middle = selected[1:-1]
        rng.shuffle(middle)
        selected = [selected[0]] + middle + [selected[-1]]

    return selected


def generate_review_dialogue(app, rng):
    """Generate a back-and-forth dialogue between Rapptr and ZooKeeper about an app."""
    dialogue = []
    tags = app.get("tags", [])
    grade = app.get("grade", "C")
    score = app.get("score", 0)
    playability = app.get("playability", 0)
    community = app.get("community", {})
    category_title = app.get("category_title", "the ecosystem")

    # Verdicts for ZooKeeper
    if score >= 80:
        verdict = "exceptional"
    elif score >= 60:
        verdict = "above average"
    elif score >= 40:
        verdict = "average"
    else:
        verdict = "below the bar"

    # Rapptr opens with excitement
    intro = rng.choice(RAPPTR_INTROS).format(
        title=app["title"], category=category_title
    )
    dialogue.append({"host": "Rapptr", "text": intro})

    # ZooKeeper responds with data
    zoo_intro = rng.choice(ZOOKEEPER_INTROS).format(
        title=app["title"], score=score, grade=grade,
        playability=playability, category=category_title, verdict=verdict
    )
    dialogue.append({"host": "ZooKeeper", "text": zoo_intro})

    # Rapptr reacts to score
    rapptr_score = rng.choice(RAPPTR_SCORE_REACTIONS.get(grade, RAPPTR_SCORE_REACTIONS["C"]))
    dialogue.append({"host": "Rapptr", "text": rapptr_score})

    # ZooKeeper gives score context
    zoo_score = rng.choice(ZOOKEEPER_SCORE_REACTIONS.get(grade, ZOOKEEPER_SCORE_REACTIONS["C"]))
    dialogue.append({"host": "ZooKeeper", "text": zoo_score})

    # Tag-based reactions (1-2 tags)
    reacted_tags = [t for t in tags if t in RAPPTR_TAG_REACTIONS]
    if reacted_tags:
        tag = rng.choice(reacted_tags)
        rapptr_tag = rng.choice(RAPPTR_TAG_REACTIONS[tag])
        dialogue.append({"host": "Rapptr", "text": rapptr_tag})
        if tag in ZOOKEEPER_TAG_REACTIONS:
            zoo_tag = rng.choice(ZOOKEEPER_TAG_REACTIONS[tag])
            dialogue.append({"host": "ZooKeeper", "text": zoo_tag})

    # Community reactions
    top_comments = community.get("topComments", [])
    total_ratings = community.get("totalRatings", 0)
    avg_rating = community.get("avgRating", 0)

    if top_comments:
        best_comment = top_comments[0]
        # Truncate long comments
        comment_text = best_comment["text"]
        if len(comment_text) > 120:
            comment_text = comment_text[:117] + "..."
        rapptr_comm = rng.choice(RAPPTR_COMMENT_REACTIONS).format(
            author=best_comment["author"], comment=comment_text
        )
        dialogue.append({"host": "Rapptr", "text": rapptr_comm})

        zoo_comm = rng.choice(ZOOKEEPER_COMMENT_REACTIONS).format(
            author=best_comment["author"], comment=comment_text,
            upvotes=best_comment.get("upvotes", 0)
        )
        dialogue.append({"host": "ZooKeeper", "text": zoo_comm})

    if total_ratings > 0:
        if avg_rating >= 4.0:
            rating_verdict = "Tracks with the algorithm"
        elif avg_rating >= 3.0:
            rating_verdict = "Community is more generous than the algorithm"
        else:
            rating_verdict = "Even the community isn't convinced"

        rapptr_rat = rng.choice(RAPPTR_RATING_REACTIONS).format(
            ratings=total_ratings, avg=avg_rating
        )
        dialogue.append({"host": "Rapptr", "text": rapptr_rat})

        zoo_rat = rng.choice(ZOOKEEPER_RATING_REACTIONS).format(
            ratings=total_ratings, avg=avg_rating, verdict=rating_verdict
        )
        dialogue.append({"host": "ZooKeeper", "text": zoo_rat})

    return dialogue


def generate_roast_dialogue(app, rng):
    """Generate the roast segment for the lowest-scoring app."""
    dialogue = []
    score = app.get("score", 0)
    playability = app.get("playability", 0)
    pct = (playability / 25) * 100 if playability else 0

    # Rapptr opens reluctantly
    dialogue.append({"host": "Rapptr", "text": rng.choice(RAPPTR_ROAST_OPENERS)})

    # ZooKeeper delivers the roast
    roast = rng.choice(ZOOKEEPER_ROAST_LINES).format(
        title=app["title"], score=score, playability=playability, pct=pct
    )
    dialogue.append({"host": "ZooKeeper", "text": roast})

    # Rapptr defends
    dialogue.append({"host": "Rapptr", "text": rng.choice(RAPPTR_ROAST_DEFENSE)})

    # ZooKeeper gets specific
    tags = app.get("tags", [])
    if tags:
        tag_list = ", ".join(tags[:3])
        dialogue.append({"host": "ZooKeeper", "text": f"Tagged as {tag_list}. The ambition is there. The execution? Not yet."})

    desc = app.get("description", "")
    if desc:
        short_desc = desc[:80] + "..." if len(desc) > 80 else desc
        dialogue.append({"host": "Rapptr", "text": f"But look at the vision: \"{short_desc}\" — that's a cool idea!"})
        dialogue.append({"host": "ZooKeeper", "text": f"Cool idea, {score}-point execution. Molting exists for a reason."})

    return dialogue


def estimate_duration(segments):
    """Estimate episode duration from total word count (~150 words/min)."""
    words = 0
    for seg in segments:
        if "text" in seg:
            words += len(seg["text"].split())
        for line in seg.get("dialogue", []):
            words += len(line.get("text", "").split())
    minutes = words / 150
    m = int(minutes)
    s = int((minutes - m) * 60)
    return f"{m}:{s:02d}"


def generate_episode(index, rng, frame, episode_number, rankings_summary, lore=None):
    """Generate a complete episode."""
    apps = select_episode_apps(index, rng, frame)
    if not apps:
        return None

    if lore is None:
        lore = load_lore()

    num_reviews = len(apps) - 1  # Last one is roast
    total_apps = len(index)
    median = rankings_summary.get("median_score", 49) if rankings_summary else 49
    top_app = apps[0] if apps else None
    review_apps = apps[:-1] if len(apps) > 1 else apps
    roast_app = apps[-1] if len(apps) > 1 else None

    segments = []

    # Intro
    intro_text = rng.choice(INTRO_TEMPLATES).format(
        n=episode_number, count=total_apps, frame=frame, num_reviews=num_reviews
    )
    segments.append({"type": "intro", "host": "Rapptr", "text": intro_text})

    zoo_intro = rng.choice(ZOOKEEPER_INTRO_RESPONSES).format(median=median)
    segments.append({"type": "intro", "host": "ZooKeeper", "text": zoo_intro})

    # Milestone/meta commentary from lore
    milestone_lines = generate_milestone_dialogue(lore, episode_number, total_apps, rng)
    for line in milestone_lines:
        segments.append({"type": "intro", **line})

    # Reviews
    for i, app in enumerate(review_apps):
        if i > 0:
            segments.append({"type": "transition", "host": "Rapptr", "text": rng.choice(TRANSITIONS)})

        dialogue = generate_review_dialogue(app, rng)

        # Inject lore callbacks if this app has been reviewed before
        lore_lines = generate_lore_dialogue(app, lore, episode_number, rng)
        if lore_lines:
            # Insert lore after the first two lines (intro + score)
            insert_at = min(2, len(dialogue))
            for j, line in enumerate(lore_lines):
                dialogue.insert(insert_at + j, line)

        segments.append({
            "type": "review",
            "app": {
                "title": app["title"],
                "file": app["file"],
                "category": app["category"],
                "folder": app["folder"],
                "path": app["path"],
                "url": app["url"],
                "score": app["score"],
                "grade": app["grade"],
                "playability": app["playability"],
                "tags": app["tags"],
                "description": app["description"],
                "community": app["community"],
            },
            "dialogue": dialogue,
        })

    # Roast segment
    if roast_app and roast_app["score"] < review_apps[0]["score"]:
        roast_dialogue = generate_roast_dialogue(roast_app, rng)
        segments.append({
            "type": "roast",
            "app": {
                "title": roast_app["title"],
                "file": roast_app["file"],
                "category": roast_app["category"],
                "folder": roast_app["folder"],
                "path": roast_app["path"],
                "url": roast_app["url"],
                "score": roast_app["score"],
                "grade": roast_app["grade"],
                "playability": roast_app["playability"],
                "tags": roast_app["tags"],
                "description": roast_app["description"],
                "community": roast_app["community"],
            },
            "dialogue": roast_dialogue,
        })

    # Outro
    outro = rng.choice(OUTRO_TEMPLATES).format(
        n=episode_number, count=total_apps, top_title=top_app["title"] if top_app else "these apps"
    )
    segments.append({"type": "outro", "host": "Rapptr", "text": outro})
    segments.append({"type": "outro", "host": "ZooKeeper", "text": rng.choice(ZOOKEEPER_OUTROS)})

    # Episode title
    title = rng.choice(EPISODE_TITLE_TEMPLATES).format(
        n=episode_number, top_title=top_app["title"] if top_app else "RappterZoo",
        category=top_app["category_title"] if top_app else "Mixed",
        count=total_apps, frame=frame
    )

    duration = estimate_duration(segments)

    episode = {
        "id": f"ep-{episode_number:03d}",
        "number": episode_number,
        "title": title,
        "description": f"Rapptr and ZooKeeper review {num_reviews} apps from the RappterZoo ecosystem — including {top_app['title'] if top_app else 'some favorites'}.",
        "frame": frame,
        "generated": datetime.now().isoformat(),
        "duration": duration,
        "audioFile": f"apps/broadcasts/audio/ep-{episode_number:03d}.wav",
        "segments": segments,
    }

    return episode


def generate_feed(frame=None, regenerate_all=False):
    """Generate or update the broadcast feed."""
    manifest = load_json(MANIFEST)
    rankings = load_json(RANKINGS)
    community = load_json(COMMUNITY)
    molter_state = load_json(MOLTER_STATE)

    if not manifest:
        print("ERROR: manifest.json not found")
        return None

    if frame is None:
        frame = molter_state.get("frame", 0) if molter_state else 0

    rankings_summary = rankings.get("summary", {}) if rankings else {}

    # Build unified app index
    index = build_app_index(manifest, rankings, community)
    log(f"Indexed {len(index)} apps")

    # Load existing feed or create new
    existing_feed = load_json(FEED_FILE) if not regenerate_all else None

    if existing_feed:
        episodes = existing_feed.get("episodes", [])
        next_number = max((e.get("number", 0) for e in episodes), default=0) + 1
    else:
        episodes = []
        next_number = 1

    # Seed RNG on frame + episode number for determinism
    seed = frame * 1000 + next_number
    rng = random.Random(seed)

    # Load lore tracker for continuity
    lore = load_lore()

    log(f"Generating episode {next_number} for frame {frame} (seed={seed})")
    log(f"Lore: {len(lore.get('reviewed_apps', {}))} apps tracked, {len(lore.get('episode_summaries', []))} past episodes")

    episode = generate_episode(index, rng, frame, next_number, rankings_summary, lore)
    if not episode:
        print("ERROR: No apps to generate episode from")
        return None

    # Update lore with this episode's data
    lore = update_lore(lore, episode)
    save_lore(lore)
    log(f"Lore updated: {lore['total_reviewed']} total reviews tracked")

    episodes.append(episode)

    feed = {
        "meta": {
            "showTitle": "RappterZooNation",
            "tagline": "Two hosts. 500+ games. Zero humans required.",
            "hosts": [
                {**HOSTS["Rapptr"], "name": "Rapptr"},
                {**HOSTS["ZooKeeper"], "name": "ZooKeeper"},
            ],
            "totalEpisodes": len(episodes),
            "generated": datetime.now().isoformat(),
        },
        "episodes": episodes,
    }

    # Write feed
    BROADCAST_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEED_FILE, "w") as f:
        json.dump(feed, f, indent=2)

    log(f"Wrote {FEED_FILE} ({len(episodes)} episodes)")
    print(f"Generated episode {next_number}: {episode['title']}")
    print(f"  Duration: {episode['duration']}")
    print(f"  Segments: {len(episode['segments'])}")
    review_count = sum(1 for s in episode["segments"] if s["type"] == "review")
    print(f"  Reviews: {review_count} apps")

    return feed


def main():
    args = sys.argv[1:]

    frame = None
    regenerate_all = "--regenerate-all" in args

    for i, arg in enumerate(args):
        if arg == "--frame" and i + 1 < len(args):
            frame = int(args[i + 1])

    feed = generate_feed(frame=frame, regenerate_all=regenerate_all)

    if feed and "--push" in args:
        print("\nCommitting and pushing...")
        subprocess.run(["git", "add", str(FEED_FILE), str(LORE_FILE)], cwd=ROOT)
        subprocess.run(
            ["git", "commit", "-m", "chore: generate RappterZooNation episode"],
            cwd=ROOT,
        )
        subprocess.run(["git", "push"], cwd=ROOT)
        print("Pushed!")


if __name__ == "__main__":
    main()
