#!/usr/bin/env python3
"""Generate simulated community data for the Infinite Arcade.

Creates realistic player profiles, play activity, ratings, and enriching
threaded comment discussions across all games. The community feels alive
with hundreds of simulated players who have histories, preferences, and opinions.

Real players join by "taking over" an NPC slot — seamlessly inheriting
the NPC's history and becoming part of the living community.

Usage:
    python3 scripts/generate_community.py              # Generate community.json
    python3 scripts/generate_community.py --verbose     # Show generation details
    python3 scripts/generate_community.py --push        # Generate + commit + push

Output: apps/community.json
"""

import json
import hashlib
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
OUTPUT = APPS_DIR / "community.json"

# ── Player Generation ─────────────────────────────────────────────

ADJECTIVES = [
    "Shadow", "Neon", "Pixel", "Cosmic", "Void", "Cyber", "Quantum", "Dark",
    "Iron", "Storm", "Crystal", "Flame", "Frost", "Thunder", "Drift", "Nova",
    "Spectral", "Rogue", "Silent", "Rapid", "Savage", "Mystic", "Astral", "Omega",
    "Crimson", "Jade", "Azure", "Golden", "Obsidian", "Phantom", "Turbo", "Ultra",
    "Hyper", "Primal", "Solar", "Lunar", "Zero", "Alpha", "Apex", "Glitch",
    "Binary", "Chrome", "Ember", "Vortex", "Echo", "Pulse", "Static", "Arc",
    "Zenith", "Dusk", "Inferno", "Nebula", "Rift", "Blaze", "Ghost", "Stealth",
    "Plasma", "Chaos", "Flux", "Cipher", "Onyx", "Titan", "Rebel", "Orbital"
]

NOUNS = [
    "Wolf", "Phoenix", "Knight", "Dragon", "Hawk", "Serpent", "Viper", "Lion",
    "Raven", "Fox", "Bear", "Falcon", "Tiger", "Panther", "Eagle", "Shark",
    "Wraith", "Sentinel", "Reaper", "Nomad", "Hunter", "Ranger", "Wizard", "Mage",
    "Pilot", "Runner", "Striker", "Blade", "Caster", "Forge", "Smith", "Archer",
    "Scout", "Warden", "Baron", "Fury", "Comet", "Catalyst", "Drifter", "Specter",
    "Breaker", "Keeper", "Walker", "Stalker", "Shaman", "Monk", "Samurai", "Ninja",
    "Chief", "Marshal", "Sage", "Oracle", "Prophet", "Mystic", "Herald", "Watcher",
    "Pioneer", "Corsair", "Raider", "Phantom", "Golem", "Djinn", "Valkyrie", "Titan"
]

AVATAR_COLORS = [
    "#ff4500", "#ff6834", "#e91e63", "#9c27b0", "#673ab7",
    "#3f51b5", "#2196f3", "#00bcd4", "#009688", "#4caf50",
    "#8bc34a", "#cddc39", "#ffc107", "#ff9800", "#ff5722",
    "#795548", "#607d8b", "#f44336", "#7c4dff", "#00e5ff",
    "#76ff03", "#ffea00", "#ff6e40", "#64ffda", "#ea80fc",
]

BIOS = [
    "speedrunner at heart. always hunting for the next challenge.",
    "pixel art appreciator. old school gamer turned autonomous arcade explorer.",
    "competitive player since day one. leaderboard addict.",
    "i play everything. genre doesn't matter, quality does.",
    "casual player who somehow has 500 hours logged.",
    "here for the art, staying for the gameplay.",
    "audio nerd. judge games by their sound design first.",
    "strategy over reflexes. thinking > clicking.",
    "physics engine enthusiast. the more simulation the better.",
    "procedural generation fanatic. no two runs should feel the same.",
    "accessibility advocate. good games should work for everyone.",
    "creative tools power user. built 3 apps here myself.",
    "just vibes. if it looks cool, i'm playing it.",
    "code archaeologist. i read the source of every game i play.",
    "particle effects connoisseur. give me sparks and trails.",
    "3d world explorer. get lost in virtual spaces.",
    "music maker and game player. the intersection is magic.",
    "testing everything the arcade generates. quality control volunteer.",
    "retro aesthetic + modern mechanics = perfection.",
    "i'm here to break every game. bug hunter extraordinaire.",
    "marathon sessions. don't talk to me for 6 hours.",
    "generative art collector. screenshots folder is 40gb.",
    "ai whisperer. watching the machines learn to make games.",
    "the arcade made me learn javascript. no regrets.",
    "lurker turned regular. the community pulled me in.",
    "competitive rating optimizer. every star matters.",
    "weekend warrior. friday night = new game night.",
    "mobile player. touch controls or bust.",
    "soundtrack listener. some games i just leave running for the music.",
    "evolution watcher. seeing games molt is the real game.",
]

CATEGORY_OPINIONS = {
    "games_puzzles": [
        "the gameplay loop on this one is incredibly tight",
        "this hits that perfect difficulty curve - easy to learn, hard to master",
        "the procedural generation makes every run feel fresh",
        "finally a game in this arcade that has actual depth",
        "the scoring system is really well designed - keeps me coming back",
        "controls are buttery smooth, exactly what you want",
        "this is the kind of game you lose 2 hours to without noticing",
        "the progression system is surprisingly deep for a browser game",
        "love how the difficulty scales naturally instead of just getting unfair",
        "this is a masterclass in game feel - every action has weight",
        "the combo system adds so much depth to what seems simple",
        "played this for 3 hours straight. send help.",
        "the way the game teaches mechanics through play instead of tutorials is brilliant",
        "high score chasing in this is genuinely addictive",
        "the enemy AI actually adapts to your playstyle, which is rare",
    ],
    "3d_immersive": [
        "the WebGL performance here is genuinely impressive for a single HTML file",
        "got lost exploring this world for 20 minutes - amazing atmosphere",
        "the lighting engine is doing things i didn't think were possible in-browser",
        "camera controls are smooth and intuitive, no jank at all",
        "the sense of scale in this 3d environment is breathtaking",
        "runs at 60fps on my laptop which is wild for WebGL",
        "the procedural terrain generation creates genuinely interesting landscapes",
        "shaders are doing serious work here - look at those reflections",
        "this feels like it should be a standalone game, not a browser app",
        "the depth of field effect really sells the immersion",
    ],
    "audio_music": [
        "the sound design in this is seriously professional grade",
        "i've been making actual music with this tool - it's legit",
        "the synthesizer engine is surprisingly capable",
        "audio latency is minimal - impressive for Web Audio API",
        "the visual feedback for audio is really satisfying",
        "this replaced my need for a dedicated DAW for quick sketches",
        "the preset system is thoughtful - great starting points",
        "reverb and delay effects are lush and musical",
        "MIDI support would push this to the next level",
        "exported a track from this and my friends thought i used ableton",
    ],
    "generative_art": [
        "the algorithms produce genuinely beautiful output every time",
        "love that you can tweak parameters and see changes in real-time",
        "exported this as my desktop wallpaper - it's that good",
        "the color palette generation is excellent",
        "watching the patterns emerge is meditative",
        "the randomization produces surprisingly consistent quality",
        "mathematical beauty rendered perfectly",
        "saved 50 screenshots so far, each one unique",
        "the interaction model lets you guide the generation intuitively",
        "this makes me want to learn the math behind generative art",
    ],
    "visual_art": [
        "the brush engine is surprisingly sophisticated",
        "layer support in a single HTML file is impressive engineering",
        "the color picker is more intuitive than photoshop's",
        "export quality is crisp - no artifacts",
        "undo/redo works flawlessly which is crucial",
        "the tool selection feels natural and responsive",
        "i've been doing daily sketches with this for a week",
        "pressure sensitivity support would be the cherry on top",
        "canvas performance stays smooth even with complex drawings",
        "the blend modes work exactly as expected",
    ],
    "particle_physics": [
        "the physics simulation is impressively accurate",
        "watching particles interact never gets old",
        "performance holds up even with thousands of particles",
        "the gravity and force models feel realistic",
        "great educational tool - actually helped me understand physics concepts",
        "the emergent behaviors from simple rules are fascinating",
        "collision detection is precise and satisfying",
        "love being able to tweak constants and see immediate effects",
        "this is the kind of sandbox that sparks curiosity",
        "the fluid simulation is genuinely impressive for browser-based",
    ],
    "creative_tools": [
        "this tool actually saves me time in my workflow",
        "the UX is clean and intuitive - no learning curve",
        "JSON import/export is a godsend for data portability",
        "localStorage persistence means my data survives refreshes",
        "does one thing and does it really well",
        "replaced a paid app i was using with this free tool",
        "the keyboard shortcuts are well thought out",
        "responsive design works great on my tablet too",
        "wish more web tools had this level of polish",
        "the export options cover all the formats i need",
    ],
    "experimental_ai": [
        "the AI behaviors here are genuinely emergent and surprising",
        "this simulation produces results i didn't expect",
        "the interface for tweaking parameters is well designed",
        "watching the system evolve over time is fascinating",
        "the complexity that emerges from simple rules is mindblowing",
        "this feels like a research tool disguised as an app",
        "the visualization of AI decision-making is illuminating",
        "spent an hour just watching the simulation play out",
        "the data export lets you analyze runs in detail",
        "this could be a legitimate research platform",
    ],
    "educational_tools": [
        "actually learned something new from this, which is rare",
        "the progressive difficulty is perfect for self-paced learning",
        "visual explanations make complex concepts click",
        "better than most paid educational software i've used",
        "the interactive examples are what make this effective",
        "bookmarked this for teaching my students",
        "the immediate feedback loop accelerates learning",
        "concepts that confused me for years finally make sense",
        "sharing this with everyone who wants to learn this topic",
        "the gamification of learning is done tastefully here",
    ],
}

TECHNICAL_COMMENTS = [
    "looked at the source - the state machine architecture is clean",
    "the way this handles memory management is elegant",
    "requestAnimationFrame usage is textbook here - smooth as butter",
    "canvas rendering pipeline is well-optimized",
    "the event handling system is surprisingly sophisticated",
    "localStorage usage is smart - survives page refreshes perfectly",
    "the collision detection algorithm is efficient for this scale",
    "class hierarchy is well-structured - easy to understand the codebase",
    "the particle system uses object pooling which explains the performance",
    "audio context management handles browser autoplay policies correctly",
    "the responsive layout handles all screen sizes gracefully",
    "data serialization for save/load is robust",
    "the input abstraction handles both keyboard and touch elegantly",
    "error handling is thorough - didn't crash once during testing",
    "the animation easing functions give everything a polished feel",
]

REPLY_TEMPLATES = [
    "agreed. {point}",
    "good observation. i also noticed {point}",
    "exactly this. {point}",
    "underrated comment. {point}",
    "hard agree. also worth noting {point}",
    "came here to say this. {point}",
    "this is the real insight. {point}",
    "100%. {point}",
    "you nailed it. {point}",
    "building on this - {point}",
]

REPLY_POINTS = [
    "the attention to detail really shows",
    "it's clear a lot of thought went into the design",
    "the performance optimization is impressive",
    "the game feel is what sells it",
    "small touches like this separate good from great",
    "the feedback loop is perfectly tuned",
    "this level of polish is rare in browser games",
    "the responsive design is an underappreciated feature",
    "the procedural elements keep it fresh",
    "the sound design reinforces every interaction",
    "the difficulty curve is perfectly calibrated",
    "accessibility touches like this matter",
    "the save system means no progress is lost",
    "the visual hierarchy guides you intuitively",
    "each run teaches you something new about the mechanics",
]

MODERATOR_COMMENTS = [
    "**[Quality Analysis]** This app scores {score}/100 on our automated quality index. {verdict}",
    "**[Mod Note]** This post has been through {gen} generation{gen_s} of evolution. Each molt improved {aspects}.",
    "**[Technical Spotlight]** Standout engineering: {tech}. This is {complexity} complexity, which means {explain}.",
    "**[Community Pick]** This app has a {rating}-star community rating. {why}",
    "**[Evolution Log]** Gen {gen}: {changes}. The autonomous system is continuously improving this post.",
]


def seed_rng(s):
    """Create a seeded random instance for deterministic generation."""
    return random.Random(hashlib.md5(s.encode()).hexdigest())


def generate_players(n=250):
    """Generate n player profiles with realistic gaming identities."""
    rng = random.Random("arcade-players-v1")
    players = []
    used_names = set()

    for i in range(n):
        # Generate unique username
        for _ in range(50):
            adj = rng.choice(ADJECTIVES)
            noun = rng.choice(NOUNS)
            suffix = rng.choice(["", str(rng.randint(1, 99)), str(rng.randint(100, 9999)), "_" + rng.choice(["x", "xx", "v2", "gg", "pro", "hq", "io"])])
            # Vary format
            fmt = rng.choice([
                f"{adj}{noun}{suffix}",
                f"{adj.lower()}_{noun.lower()}{suffix}",
                f"{adj}{noun}",
                f"{noun}{rng.randint(1,999)}",
                f"x{adj}{noun}x",
                f"{adj.lower()}{noun.lower()}",
            ])
            if fmt not in used_names:
                used_names.add(fmt)
                username = fmt
                break
        else:
            username = f"Player{i}"

        # Profile
        join_days_ago = rng.randint(1, 365)
        join_date = (datetime.now() - timedelta(days=join_days_ago)).strftime("%Y-%m-%d")
        activity_level = rng.choice(["casual", "casual", "casual", "regular", "regular", "active", "active", "hardcore", "hardcore", "legendary"])
        games_played = {
            "casual": rng.randint(1, 10),
            "regular": rng.randint(8, 30),
            "active": rng.randint(20, 80),
            "hardcore": rng.randint(50, 150),
            "legendary": rng.randint(100, 300),
        }[activity_level]

        fav_cat = rng.choice(list(CATEGORY_OPINIONS.keys()))

        players.append({
            "id": f"p{i:04d}",
            "username": username,
            "color": rng.choice(AVATAR_COLORS),
            "joinDate": join_date,
            "bio": rng.choice(BIOS),
            "gamesPlayed": games_played,
            "totalScore": games_played * rng.randint(50, 500),
            "favoriteCategory": fav_cat,
            "activityLevel": activity_level,
            "isNPC": True,
            "takenOver": False,
        })

    return players


def generate_comments_for_app(app, cat_key, players, rng, rankings_data=None):
    """Generate a thread of enriching comments for one app."""
    comments = []
    # Determine how many comments based on app quality/popularity
    base = 2
    if app.get("featured"):
        base += 3
    if app.get("generation", 0) > 0:
        base += 1
    gen = app.get("generation", 0)
    num_comments = rng.randint(base, base + 5)
    num_comments = min(num_comments, 12)

    # Get category-specific comments
    cat_comments = CATEGORY_OPINIONS.get(cat_key, CATEGORY_OPINIONS["experimental_ai"])
    available_comments = list(cat_comments) + list(TECHNICAL_COMMENTS)
    rng.shuffle(available_comments)

    used_players = rng.sample(players, min(num_comments * 2, len(players)))
    player_idx = 0
    base_time = datetime.now() - timedelta(days=rng.randint(1, 60))

    for i in range(num_comments):
        if player_idx >= len(used_players):
            break
        player = used_players[player_idx]
        player_idx += 1

        # Root comment
        comment_time = base_time + timedelta(hours=rng.randint(0, 48 * (i + 1)))
        text = available_comments[i % len(available_comments)]

        comment = {
            "id": "c" + hashlib.md5((app["file"] + "-" + str(i)).encode()).hexdigest()[:8],
            "author": player["username"],
            "authorId": player["id"],
            "authorColor": player["color"],
            "text": text,
            "timestamp": comment_time.isoformat(),
            "upvotes": rng.randint(1, 50),
            "downvotes": rng.randint(0, 5),
            "version": max(1, gen) if gen > 0 else 1,
            "parentId": None,
            "children": [],
        }

        # Maybe add 1-2 replies
        if rng.random() < 0.6 and player_idx < len(used_players):
            reply_player = used_players[player_idx]
            player_idx += 1
            reply_time = comment_time + timedelta(hours=rng.randint(1, 24))
            template = rng.choice(REPLY_TEMPLATES)
            point = rng.choice(REPLY_POINTS)
            reply_text = template.format(point=point)

            reply = {
                "id": "c" + hashlib.md5((app["file"] + "-" + str(i) + "-r1").encode()).hexdigest()[:8],
                "author": reply_player["username"],
                "authorId": reply_player["id"],
                "authorColor": reply_player["color"],
                "text": reply_text,
                "timestamp": reply_time.isoformat(),
                "upvotes": rng.randint(1, 20),
                "downvotes": rng.randint(0, 2),
                "version": comment["version"],
                "parentId": comment["id"],
                "children": [],
            }
            comment["children"].append(reply)

            # Occasional nested reply
            if rng.random() < 0.3 and player_idx < len(used_players):
                nested_player = used_players[player_idx]
                player_idx += 1
                nested_time = reply_time + timedelta(hours=rng.randint(1, 12))
                nested = {
                    "id": "c" + hashlib.md5((app["file"] + "-" + str(i) + "-r2").encode()).hexdigest()[:8],
                    "author": nested_player["username"],
                    "authorId": nested_player["id"],
                    "authorColor": nested_player["color"],
                    "text": rng.choice(REPLY_POINTS) + ". " + rng.choice([
                        "this community gets it.",
                        "the arcade keeps surprising me.",
                        "quality like this is why i keep coming back.",
                        "autonomous game making is the future.",
                        "every generation gets better.",
                    ]),
                    "timestamp": nested_time.isoformat(),
                    "upvotes": rng.randint(1, 10),
                    "downvotes": 0,
                    "version": comment["version"],
                    "parentId": reply["id"],
                    "children": [],
                }
                reply["children"].append(nested)

        comments.append(comment)

    # Add moderator comment
    score = 0
    if rankings_data:
        for r in rankings_data.get("rankings", []):
            if r.get("file") == app["file"]:
                score = r.get("score", 0)
                break

    verdict = "Excellent quality." if score >= 80 else "Good foundation with room to grow." if score >= 60 else "Evolving - watch this space." if score >= 40 else "Early stage - the system is learning."
    complexity = app.get("complexity", "intermediate")
    explain = {
        "simple": "clean, focused, does one thing well",
        "intermediate": "multiple systems working together with solid architecture",
        "advanced": "deep systems, emergent gameplay, impressive engineering scope",
    }.get(complexity, "solid engineering throughout")

    tech_highlights = []
    tags = app.get("tags", [])
    if "canvas" in tags:
        tech_highlights.append("canvas rendering pipeline")
    if "3d" in tags:
        tech_highlights.append("WebGL 3D engine")
    if "audio" in tags or "music" in tags:
        tech_highlights.append("Web Audio API integration")
    if "physics" in tags:
        tech_highlights.append("physics simulation")
    if "ai" in tags:
        tech_highlights.append("AI behavior system")
    if "procedural" in tags:
        tech_highlights.append("procedural generation")
    if not tech_highlights:
        tech_highlights.append("self-contained architecture with inline CSS/JS")

    mod_template = rng.choice(MODERATOR_COMMENTS)
    mod_text = mod_template.format(
        score=score,
        verdict=verdict,
        gen=max(1, gen),
        gen_s="" if gen == 1 else "s",
        aspects=rng.choice(["structural quality", "accessibility", "performance", "polish and UX", "code architecture"]),
        tech=", ".join(tech_highlights[:2]),
        complexity=complexity,
        explain=explain,
        rating=round(rng.uniform(3.0, 5.0), 1),
        why=rng.choice(["Players love the depth and replayability.", "Consistently high engagement across sessions.", "The autonomous evolution has refined this into something special."]),
        changes=rng.choice(["improved responsive layout", "added touch controls", "enhanced audio feedback", "optimized render loop", "refined difficulty curve"]),
    )

    mod_time = base_time + timedelta(days=rng.randint(1, 30))
    mod_comment = {
        "id": f"mod-{hashlib.md5(app['file'].encode()).hexdigest()[:8]}",
        "author": "ArcadeKeeper",
        "authorId": "mod-001",
        "authorColor": "#ff4500",
        "text": mod_text,
        "timestamp": mod_time.isoformat(),
        "upvotes": rng.randint(5, 30),
        "downvotes": 0,
        "version": max(1, gen),
        "parentId": None,
        "children": [],
        "isModerator": True,
    }
    comments.append(mod_comment)

    return comments


def generate_ratings(apps_list, players, rng):
    """Generate star ratings from simulated players."""
    ratings = {}
    for app_info in apps_list:
        app = app_info["app"]
        stem = app["file"].replace(".html", "")
        num_raters = rng.randint(3, min(40, len(players)))
        if app.get("featured"):
            num_raters = min(num_raters + 15, len(players))

        raters = rng.sample(players, num_raters)
        app_ratings = []
        for p in raters:
            # Bias toward higher ratings (most games are decent)
            stars = rng.choices([1, 2, 3, 4, 5], weights=[2, 5, 15, 35, 43])[0]
            app_ratings.append({
                "playerId": p["id"],
                "username": p["username"],
                "stars": stars,
            })
        ratings[stem] = app_ratings
    return ratings


def generate_activity_feed(apps_list, players, rng, count=100):
    """Generate recent activity events for the live feed."""
    events = []
    now = datetime.now()

    for i in range(count):
        player = rng.choice(players)
        app_info = rng.choice(apps_list)
        app = app_info["app"]
        cat_title = app_info["catTitle"]
        minutes_ago = rng.randint(1, 1440)  # last 24 hours
        event_time = now - timedelta(minutes=minutes_ago)

        event_type = rng.choices(
            ["played", "rated", "commented", "achieved", "discovered"],
            weights=[40, 25, 20, 10, 5]
        )[0]

        event = {
            "type": event_type,
            "player": player["username"],
            "playerId": player["id"],
            "playerColor": player["color"],
            "app": app["title"],
            "appFile": app["file"],
            "category": cat_title,
            "timestamp": event_time.isoformat(),
            "minutesAgo": minutes_ago,
        }

        if event_type == "rated":
            event["stars"] = rng.choices([3, 4, 5], weights=[20, 40, 40])[0]
        elif event_type == "achieved":
            event["achievement"] = rng.choice([
                "First Clear", "Speed Runner", "Perfect Score", "Explorer",
                "Combo Master", "Survivor", "Creator", "Completionist",
                "Dedicated Player", "High Scorer", "Bug Hunter", "Veteran",
            ])
        elif event_type == "played":
            event["duration"] = rng.choice(["2m", "5m", "12m", "23m", "45m", "1h", "2h", "3h+"])

        events.append(event)

    events.sort(key=lambda e: e["minutesAgo"])
    return events


def generate_online_schedule():
    """Generate a deterministic 'online players' schedule by hour of day."""
    schedule = {}
    base = 45  # minimum players "online"
    for hour in range(24):
        # Peak hours: 18-23 (evening), low: 3-7 (night)
        if 18 <= hour <= 23:
            count = base + random.Random(f"hour-{hour}").randint(60, 150)
        elif 10 <= hour <= 17:
            count = base + random.Random(f"hour-{hour}").randint(20, 80)
        elif 7 <= hour <= 9:
            count = base + random.Random(f"hour-{hour}").randint(10, 40)
        else:
            count = base + random.Random(f"hour-{hour}").randint(0, 20)
        schedule[str(hour)] = count
    return schedule


def main():
    verbose = "--verbose" in sys.argv
    push = "--push" in sys.argv

    # Load manifest
    with open(MANIFEST) as f:
        manifest = json.load(f)

    # Load rankings if available
    rankings_path = APPS_DIR / "rankings.json"
    rankings_data = None
    if rankings_path.exists():
        with open(rankings_path) as f:
            rankings_data = json.load(f)

    # Collect all apps
    apps_list = []
    cats = manifest.get("categories", {})
    for cat_key, cat_data in cats.items():
        for app in cat_data.get("apps", []):
            apps_list.append({
                "app": app,
                "catKey": cat_key,
                "catTitle": cat_data.get("title", cat_key),
                "folder": cat_data.get("folder", cat_key),
            })

    print(f"Generating community for {len(apps_list)} apps...")

    # Generate players
    players = generate_players(250)
    print(f"  Created {len(players)} player profiles")

    # Generate comments for each app
    all_comments = {}
    rng = random.Random("community-comments-v1")
    total_comments = 0
    for i, app_info in enumerate(apps_list):
        app = app_info["app"]
        stem = app["file"].replace(".html", "")
        comments = generate_comments_for_app(app, app_info["catKey"], players, rng, rankings_data)
        all_comments[stem] = comments
        total_comments += len(comments)
        if verbose and (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(apps_list)}] Generated comments...")

    print(f"  Generated {total_comments} comments across {len(all_comments)} apps")

    # Generate ratings
    ratings = generate_ratings(apps_list, players, rng)
    total_ratings = sum(len(v) for v in ratings.values())
    print(f"  Generated {total_ratings} ratings")

    # Generate activity feed
    activity = generate_activity_feed(apps_list, players, rng, count=150)
    print(f"  Generated {len(activity)} activity events")

    # Generate online schedule
    online_schedule = generate_online_schedule()

    # Build output
    community = {
        "meta": {
            "generated": datetime.now().isoformat(),
            "version": "1.0",
            "totalPlayers": len(players),
            "totalComments": total_comments,
            "totalRatings": total_ratings,
            "totalApps": len(apps_list),
        },
        "players": players,
        "comments": all_comments,
        "ratings": ratings,
        "activity": activity,
        "onlineSchedule": online_schedule,
    }

    # Write
    with open(OUTPUT, "w") as f:
        json.dump(community, f, separators=(",", ":"))

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWrote {OUTPUT} ({size_kb:.0f} KB)")
    print(f"  {len(players)} players, {total_comments} comments, {total_ratings} ratings")

    if push:
        import subprocess
        subprocess.run(["git", "add", str(OUTPUT)], cwd=ROOT, check=True)
        msg = f"chore: regenerate community data ({len(players)} players, {total_comments} comments)\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
        subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        print("Pushed to remote.")


if __name__ == "__main__":
    main()
