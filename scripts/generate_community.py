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

# ── Tag-Based Reaction Vocabulary ──────────────────────────────────────
# Each tag maps to things a real player would notice/say about that mechanic.
# Comments are built by combining reactions to the ACTUAL tags on each game.

TAG_OBSERVATIONS = {
    "canvas": [
        "the rendering is silky — no frame drops even when things get hectic",
        "smooth canvas work, you can tell the draw loop is tight",
        "love that it's all canvas instead of DOM — feels so much snappier",
        "the draw calls are optimized well — nothing feels laggy even on my old laptop",
        "canvas API used to its full potential here, not just a glorified div",
        "the way it handles redraw on resize is seamless",
    ],
    "3d": [
        "the 3d perspective really pulls you in",
        "navigating in 3d feels natural, no weird camera jank",
        "impressed they got this level of 3d running in a browser",
        "the depth perception is handled really well — objects feel like they have volume",
        "rotating the camera and the scene holds together from every angle",
        "the 3d lighting sells the whole thing — shadows land where they should",
    ],
    "physics": [
        "the physics feel weighty and real, not floaty",
        "spent 10 minutes just messing with the physics sandbox before doing anything else",
        "collision response is crisp — objects react exactly how you'd expect",
        "the way momentum transfers between objects is spot on",
        "threw everything i could at the physics and nothing broke",
        "elastic collisions are tuned perfectly — satisfying to watch",
    ],
    "audio": [
        "the sound design carries this — play with headphones",
        "whoever did the audio really understood how sound shapes the experience",
        "the way sound reacts to your actions makes everything feel alive",
        "the spatial audio placement is impressive for Web Audio API",
        "subtle audio cues guide you before you even realize it",
        "the layered soundscape adds so much atmosphere",
    ],
    "music": [
        "i've been coming back to this just to listen",
        "the music generation is genuinely musical, not just random notes",
        "put this on in the background while working — it's that good",
        "the harmonic progressions actually follow music theory",
        "every pattern it creates feels intentional, like a real composition",
        "the rhythm engine has real swing to it — not just quantized grid",
    ],
    "animation": [
        "the animations are so fluid it's almost hypnotic",
        "every transition feels intentional, nothing jarring",
        "the easing on these animations is chef's kiss",
        "frame timing is perfect — 60fps with no judder",
        "the animation blending between states is seamless",
        "love that the animations react to velocity, not just state changes",
    ],
    "game": [
        "this is a legit game, not a tech demo — there's actual depth here",
        "the game loop kept me playing way longer than i planned",
        "rare to find a browser game with this much replayability",
        "the win condition is clear but the path there keeps you engaged",
        "difficulty ramp is well-tuned — challenging but fair",
        "the core mechanic is solid enough to carry the whole experience",
    ],
    "puzzle": [
        "the puzzle design is clever — felt genuinely smart solving these",
        "love that the puzzles teach you the rules through play instead of explaining them",
        "some of these later puzzles had me staring at the screen for minutes",
        "the aha moments here are earned, not given away",
        "each puzzle builds on the last without repeating tricks",
        "the hint system nudges without spoiling — rare and appreciated",
    ],
    "roguelike": [
        "every run feels different enough to keep coming back",
        "that feeling when you get a broken build and steamroll everything — perfect",
        "permadeath makes every decision actually matter",
        "the item synergies create these wild emergent combos",
        "died on floor 7 with the best build i'd ever had. immediately restarted",
        "the meta-progression gives just enough reason to keep going after a bad run",
    ],
    "procedural": [
        "the procedural generation here actually produces interesting results, not just noise",
        "two sessions in and i haven't seen the same layout twice",
        "there's a real art to making procedural content feel handcrafted — this nails it",
        "the seed system means i can share cool generations with others",
        "every generated output has character — not just random noise",
        "the constraints on the generation are smart, it never produces garbage",
    ],
    "ai": [
        "the AI opponents actually surprised me a few times — they adapt",
        "watched the AI make a move i didn't expect and had to rethink my whole strategy",
        "the emergent behavior here is genuinely fascinating to watch unfold",
        "the AI plays differently every game — memorizing patterns won't save you",
        "the decision-making logic feels organic, not scripted",
        "left the AI running on its own and came back to something unexpected",
    ],
    "simulation": [
        "let this run for an hour and came back to a completely different state — incredible",
        "the depth of this simulation is wild for something running in a browser tab",
        "tweaking one parameter and watching the whole system shift is addictive",
        "the emergent behavior is the real game here",
        "the simulation state is so rich you could study it for hours",
        "watching the feedback loops stabilize (or not) is genuinely tense",
    ],
    "strategy": [
        "the strategic depth surprised me — there are real meaningful choices here",
        "spent my first 3 games making bad decisions before i understood the economy",
        "this rewards planning over reflexes which is refreshing",
        "the decision trees are deep — every choice has downstream consequences",
        "you can see your strategy paying off over time, which is so satisfying",
        "lost my first game badly, then won the second because i actually learned something",
    ],
    "rpg": [
        "the character progression actually makes you feel more powerful over time",
        "love the build variety — my second playthrough was completely different",
        "the loot system has that satisfying randomness that keeps you hunting",
        "the skill tree gives real build identity — my character felt unique",
        "the stat scaling is tuned well — you never feel useless or overpowered",
        "dialogue choices that actually affect outcomes? in a browser game? wild",
    ],
    "platformer": [
        "the jump feel is perfect — responsive without being twitchy",
        "wall jumping is tight and the level design rewards exploration",
        "the movement in this has real momentum — you can feel the weight",
        "the coyote time makes jumps feel generous without being sloppy",
        "level geometry is designed around the character's exact moveset",
        "speedrunning this feels incredible — the movement flows",
    ],
    "shooter": [
        "the weapon feedback is satisfying — every shot has impact",
        "screen shake on the heavy weapons is just *chef's kiss*",
        "hit registration feels precise, no phantom misses",
        "each weapon type has a distinct personality",
        "the bullet patterns keep you moving — no camping allowed",
        "recoil management adds a real skill ceiling",
    ],
    "survival": [
        "the tension of managing resources while threats close in is perfectly paced",
        "died to hunger three times before i figured out the food chain",
        "that moment when you finally stabilize and have a surplus — so satisfying",
        "the crafting tree is deep enough to keep discovering new recipes",
        "every night cycle fills you with actual dread. that's good design",
        "the environmental hazards force you to adapt, not just stockpile",
    ],
    "exploration": [
        "got genuinely lost exploring and didn't mind at all",
        "there's always something interesting just beyond the next area",
        "the world feels bigger than it should for a single HTML file",
        "the map reveals itself at a perfect pace — never too much, never too little",
        "found a hidden area after 30 minutes and it changed how i saw the rest",
        "the sense of discovery is the real reward, and it delivers",
    ],
    "creative": [
        "made something i'm actually proud of in my first session",
        "the tool feels expressive without being overwhelming",
        "exported my creation and showed it to friends — they were impressed",
        "the creative constraints are just right — guiding without limiting",
        "there's enough flexibility here for beginners and power users",
        "the undo/redo system makes experimentation feel safe",
    ],
    "visualizer": [
        "put this on fullscreen during a party and people were mesmerized",
        "the way the visuals respond to input is incredibly satisfying",
        "took so many screenshots — every frame could be a wallpaper",
        "the visual vocabulary here is surprisingly rich",
        "watching it evolve over time is genuinely meditative",
        "hooked this up to speakers and the visual-audio sync is perfect",
    ],
    "fractal": [
        "zoomed in for 20 minutes straight and the detail never stopped",
        "the color mapping makes the math beautiful instead of just interesting",
        "found patterns within patterns within patterns — genuinely meditative",
        "the zoom depth before it pixelates is impressive",
        "each color palette transforms the same math into a different experience",
        "the julia set mode is where this really shines",
    ],
    "particle": [
        "spawned a thousand particles and it didn't even stutter",
        "the particle interactions create these emergent patterns that look alive",
        "there's something deeply satisfying about watching particles find equilibrium",
        "the particle trails create accidental art that's often beautiful",
        "the force field interactions are hypnotic at scale",
        "love how each parameter change completely transforms the behavior",
    ],
    "interactive": [
        "every input feels like it matters — nothing is wasted",
        "the responsiveness makes you want to keep experimenting",
        "love that it reacts to everything you do in real time",
        "the feedback between action and response is perfectly tuned",
        "it teaches you how to use it through interaction, not instructions",
        "the input mapping is thoughtful — nothing feels arbitrary",
    ],
    "synth": [
        "made an actual beat with this in about 5 minutes — the interface just clicks",
        "the oscillator options give you a surprising range of tones",
        "patch saving works perfectly — came back a day later and my sounds were still there",
        "the filter envelope is responsive and musical",
        "layering voices creates textures i didn't expect from Web Audio",
        "the step sequencer grid makes rhythm programming intuitive",
    ],
    "tool": [
        "this replaced a paid app in my workflow — no joke",
        "the UX is thoughtful, everything is where you'd expect it",
        "exported my data and imported it on another machine seamlessly",
        "the keyboard shortcuts make power usage a breeze",
        "this is genuinely useful, not just a demo",
        "the data persistence through localStorage is reliable — never lost work",
    ],
    "multiplayer": [
        "wish more people knew about this — the multiplayer is surprisingly solid",
        "the latency handling is impressive for a browser game",
        "played with a friend and we were both hooked for an hour",
        "the matchmaking puts you against fair opponents",
        "competitive mode brings out the best in the gameplay",
        "the social aspect transforms the experience completely",
    ],
    "horror": [
        "the atmosphere in this genuinely unsettled me — well done",
        "played this at night with headphones and had to take a break",
        "the sound design does so much of the heavy lifting for the tension",
        "the pacing of scares is deliberate, not just jumpscare spam",
        "the ambient dread is more effective than most AAA horror games",
        "the use of darkness and negative space is masterful",
    ],
    "space": [
        "the scale of space is communicated perfectly — you feel tiny",
        "navigating between systems has that perfect sense of vastness",
        "the star rendering alone is worth opening this",
        "the orbital mechanics actually feel realistic",
        "drifting through the void has a meditative quality",
        "the nebula effects are genuinely beautiful",
    ],
    "retro": [
        "the pixel art style is authentic, not just a filter",
        "plays like a lost arcade game from the 90s — in the best way",
        "the retro aesthetic with modern game design is the perfect combo",
        "the color palette is period-accurate and it shows",
        "the scanline effect adds just enough nostalgia without hurting readability",
        "CRT vibes with modern responsiveness — best of both worlds",
    ],
    "tower-defense": [
        "the tower synergies add real strategic depth",
        "wave 15 absolutely destroyed my setup — time to rethink everything",
        "the satisfaction of a perfectly placed tower clearing a whole wave",
        "upgrade paths force meaningful decisions — you can't max everything",
        "the enemy variety forces you to diversify your defense",
        "mazing is where the real strategy lives and it's well-supported",
    ],
    "cards": [
        "the deck building has legitimate depth — not just random card soup",
        "figuring out card combos is the real game within the game",
        "the card art and effects make every play feel impactful",
        "the mana curve creates real tension in hand management",
        "draft mode is where this really shines",
        "each card has clear purpose — no filler in the deck",
    ],
    "sandbox": [
        "gave myself 'just 10 minutes' and lost an hour",
        "the freedom to do whatever you want here is the whole point and it works",
        "built something completely ridiculous and the simulation just rolled with it",
        "the lack of win conditions is actually the point — pure creative freedom",
        "shared my sandbox creation and got actual useful feedback",
        "the tools are deep enough to build seriously complex things",
    ],
    "drawing": [
        "the brush engine is better than some paid apps i've used",
        "pressure sensitivity would be the only thing missing",
        "exported at full resolution and the quality held up perfectly",
        "the layer system makes complex compositions manageable",
        "the color picker is fast and accurate",
        "the stroke smoothing makes freehand drawing look professional",
    ],
    "color": [
        "the palette generation is actually tasteful — not just random hues",
        "the color theory behind this is solid, you can feel the harmony",
        "every combination it produces is genuinely usable",
        "the complementary color suggestions are spot on",
        "exported a palette and used it in a real design project",
        "the accessibility contrast checker is a great addition",
    ],
    "data": [
        "the data visualization is clear without being boring",
        "imported my own dataset and got useful insights immediately",
        "the charting options cover every use case i needed",
        "the filtering and sorting is responsive even with large datasets",
        "the export formats are practical — CSV, JSON, and clipboard",
        "the live data binding means changes propagate instantly",
    ],
    "education": [
        "actually understood a concept i'd been struggling with after 10 minutes here",
        "the way it builds from simple to complex is perfectly paced",
        "bookmarked this for my students — it explains things better than i do",
        "the interactive examples make abstract ideas concrete",
        "the progression from beginner to advanced feels natural",
        "the quizzes at each level actually test understanding, not memorization",
    ],
    "math": [
        "makes math feel visual and intuitive instead of abstract",
        "played with the parameters and suddenly understood the relationship",
        "whoever made this clearly loves math AND knows how to teach it",
        "the graphing is accurate and responsive to parameter changes",
        "seeing the equations animate in real time was an aha moment for me",
        "the numerical precision is impressive for JavaScript floating point",
    ],
    "svg": [
        "the vector rendering stays crisp at any zoom level — no pixelation",
        "the SVG animations are buttery smooth and scale beautifully to any screen",
        "smart use of SVG — the DOM elements make the interactivity layer cleaner",
        "the path manipulation here shows deep understanding of SVG geometry",
        "resized the browser and everything reflows perfectly — SVG does that well",
        "the SVG filter effects add a richness that canvas usually can't match",
    ],
    "generative": [
        "the generative outputs are consistently surprising — not just random",
        "ran it 50 times and every result had its own character",
        "the parameter space is vast — tiny changes create wildly different outcomes",
        "the rules behind the generation produce patterns that feel organic",
        "some of these generative outputs belong in a gallery",
        "the constraint system ensures every generation is interesting, not just noise",
    ],
    "webgl": [
        "the WebGL performance is impressive — pushing serious polygons in a browser",
        "the shader work here is on par with native applications",
        "the GPU utilization makes this feel like a desktop app",
        "the WebGL context management is solid — no lost contexts even during heavy use",
        "the rendering pipeline is well-architected — smooth even on integrated GPUs",
        "WebGL used to its full potential — not just textured quads",
    ],
    "idle": [
        "left it running overnight and came back to something amazing",
        "the idle progression is tuned well — meaningful growth without feeling grindy",
        "the offline calculation when you come back is generous and accurate",
        "numbers go up and somehow that never stops being satisfying",
        "the prestige system adds real decision-making to what could be mindless",
        "it respects your time whether you're active or idle",
    ],
    "typing": [
        "my WPM went up 15% after a week with this",
        "the key feedback makes typing practice actually enjoyable",
        "the difficulty adapts to your weak letters — smart design",
        "the stats tracking gives real motivation to improve",
        "makes touch typing practice feel like a game instead of homework",
        "the accuracy metrics are more useful than raw speed numbers",
    ],
    "quiz": [
        "the question variety keeps it from feeling repetitive",
        "the difficulty scaling matches your actual knowledge level",
        "the explanations after wrong answers are where the real learning happens",
        "the scoring system rewards consistent accuracy over lucky guesses",
        "learned more in 15 minutes than from reading for an hour",
        "the spaced repetition makes knowledge stick",
    ],
}

# Reactions to description keywords (mined from the actual description text)
DESC_REACTIONS = {
    "battle": "the combat feels impactful — every hit matters",
    "build": "the building system is intuitive and the results look great",
    "craft": "the crafting loop is addictive — always one more thing to make",
    "defend": "the defense mechanics create real tension in the later waves",
    "destroy": "the destruction physics are incredibly satisfying",
    "evolve": "watching things evolve over time never gets old here",
    "explore": "the exploration rewards curiosity — always something hidden",
    "fight": "the fight mechanics have real weight to them",
    "fly": "the flight model feels great — responsive but not twitchy",
    "grow": "the growth curve is perfectly tuned — you always feel progress",
    "hack": "the hacking minigame is clever and actually requires thinking",
    "hunt": "tracking targets keeps you engaged the whole session",
    "invade": "the invasion scenarios get genuinely intense",
    "jump": "the jump feel is dialed in perfectly",
    "manage": "the management layer adds real strategic depth",
    "mine": "the mining loop is satisfying — dig deeper, find better stuff",
    "navigate": "the navigation feels natural even in complex spaces",
    "pilot": "the piloting controls are tight — responsive without being oversensitive",
    "race": "the racing feels fast and the track design keeps it interesting",
    "shoot": "gunplay is solid — accurate, responsive, satisfying",
    "solve": "the puzzle solving has that perfect difficulty where you feel smart",
    "survive": "the survival pressure keeps every decision feeling meaningful",
    "trade": "the trading economy actually works — prices feel dynamic",
    "wizard": "the spell system is creative and fun to experiment with",
    "zombie": "the zombie AI is relentless in the best way",
    "dragon": "the dragon encounters are epic — genuine boss fight energy",
    "dungeon": "the dungeon layouts feel handcrafted even though they're generated",
    "planet": "the planetary scale is communicated beautifully",
    "ocean": "the ocean simulation is mesmerizing — the waves alone are worth it",
    "forest": "the forest atmosphere is immersive — you can almost hear it",
    "city": "the city feels alive with activity, not just static buildings",
    "tower": "the tower mechanics add a layer of strategy i didn't expect",
    "army": "managing your forces feels like real tactical decision-making",
    "spell": "the spell effects are gorgeous and each one feels different",
    "sword": "melee combat has weight — you can feel the swings connect",
    "shield": "the block timing adds a skill ceiling that rewards practice",
    "potion": "the potion system adds real decision-making to resource management",
    "quest": "the quest design gives you reasons to explore every corner",
    "boss": "the boss fights are the highlight — each one feels like a puzzle",
    "score": "chasing high scores gives this insane replayability",
    "wave": "the wave system ramps perfectly — always one more wave",
    "colony": "watching your colony grow from nothing is deeply satisfying",
    "kingdom": "the kingdom management has surprising depth",
    "empire": "the empire building scratches that civilization itch perfectly",
    "island": "the island setting makes every resource feel precious",
    "mountain": "the verticality adds a whole dimension to the gameplay",
    "cave": "the cave exploration has a genuine sense of discovery",
    "lab": "the lab experiments produce surprising and fun results",
    "factory": "optimizing the factory layout is the real endgame and it's addictive",
    "robot": "the robot customization system is deep and rewarding",
    "alien": "the alien designs are creative — not just palette-swapped humans",
    "pirate": "the pirate theme is committed and charming throughout",
    "ninja": "the stealth mechanics add real tension to every encounter",
    "detective": "the detective work actually requires paying attention to clues",
    "cooking": "the cooking mechanics are surprisingly deep and the recipes make sense",
    "garden": "watching your garden grow over sessions is genuinely relaxing",
    "music": "the musical elements are woven in perfectly — not just tacked on",
    "paint": "the painting tools feel expressive and responsive",
    "code": "the code visualization makes abstract concepts tangible",
    "neural": "the neural network visualization is illuminating",
    "genetic": "watching the genetic algorithm converge is fascinating",
    "fractal": "zooming into the fractals reveals infinite beautiful detail",
    "gravity": "the gravity mechanics are the star of the show here",
    "magnetic": "the magnetic interactions create emergent puzzles",
    "wave": "the wave simulation is hypnotic to watch",
    "fluid": "the fluid dynamics are impressively realistic for browser-based",
    "light": "the lighting model adds so much atmosphere",
    "shadow": "the shadow rendering gives everything a sense of depth",
}

# Complexity-specific reactions
COMPLEXITY_REACTIONS = {
    "simple": [
        "clean and focused — does one thing and does it well",
        "picked this up in seconds, still playing 20 minutes later",
        "proof that simple design can be deeply engaging",
        "no bloat, no tutorials needed — just jump in and play",
        "sometimes the simplest games have the best game feel",
    ],
    "intermediate": [
        "there's more depth here than the surface suggests",
        "the systems interact in ways i'm still discovering",
        "took a few minutes to click but once it did i was hooked",
        "the complexity is well-managed — deep without being overwhelming",
        "layers of mechanics that reveal themselves gradually",
    ],
    "advanced": [
        "this is a deep system — i'm still learning new things after hours",
        "the amount of interlocking mechanics here is impressive",
        "you need to understand the systems to succeed and that's rewarding",
        "this has the depth of a full commercial game",
        "the learning curve is steep but the payoff is worth it",
    ],
}

# Type-specific reactions
TYPE_REACTIONS = {
    "game": [
        "genuine gameplay loop — not a tech demo pretending to be a game",
        "this has real win conditions and real stakes",
        "the game design here shows real understanding of what makes games fun",
    ],
    "visual": [
        "i keep coming back just to look at it",
        "genuinely beautiful — every frame could be a screenshot",
        "the visual craft here is on another level",
    ],
    "audio": [
        "the audio experience is the main event and it delivers",
        "put headphones on for this one — the spatial audio is impressive",
        "the sonic palette is rich and expressive",
    ],
    "interactive": [
        "every interaction feels purposeful and responsive",
        "the feedback loop between input and response is perfectly tuned",
        "messing around with this is the point and it's great",
    ],
    "interface": [
        "the UI design is clean enough to use professionally",
        "everything is where you'd expect it — great information architecture",
        "functional AND good looking which is rare",
    ],
}

# Moderator comment templates — ArcadeKeeper uses actual game data
MODERATOR_COMMENTS = [
    "[ArcadeKeeper] Quality scan: {score}/100. {verdict} Built with {tech} at {complexity} complexity — {explain}. Generation {gen}: each molt has refined the experience. Community rating: {rating}/5.",
    "[ArcadeKeeper] Automated review: {score}/100 — {verdict} Technical highlights: {tech}. Complexity: {complexity} ({explain}). This is generation {gen}, with recent improvements to {changes}.",
    "[ArcadeKeeper] Score: {score}/100. {verdict} {why} The {tech} implementation is solid for {complexity}-level work ({explain}). Generation {gen} — watching this evolve in real time.",
    "[ArcadeKeeper] Scan complete: {score}/100. {verdict} Key systems: {tech}. At {complexity} complexity, this delivers {explain}. Generation {gen} — latest molt brought {changes}.",
    "[ArcadeKeeper] Rating: {score}/100. {verdict} Architecture: {tech}, complexity level: {complexity} ({explain}). Now at generation {gen}. Community consensus: {rating}/5 stars. {why}",
]


def build_comment_for_app(app, rng):
    """Build unique comments that react to THIS specific app's actual content.

    Comments are composed by combining observations from the app's actual tags,
    description keywords, and title. Compound comments weave together two
    observations to create unique combinations even across similar games.
    """
    title = app.get("title", "")
    desc = app.get("description", "")
    tags = app.get("tags", [])
    complexity = app.get("complexity", "intermediate")
    app_type = app.get("type", "interactive")
    desc_lower = desc.lower()
    title_lower = title.lower()

    # Gather single observations from all matching sources
    tag_pool = []
    for tag in tags:
        if tag in TAG_OBSERVATIONS:
            tag_pool.extend(TAG_OBSERVATIONS[tag])

    desc_pool = []
    for keyword, reaction in DESC_REACTIONS.items():
        if keyword in desc_lower or keyword in title_lower:
            desc_pool.append(reaction)

    comp_pool = COMPLEXITY_REACTIONS.get(complexity, [])
    type_pool = TYPE_REACTIONS.get(app_type, [])

    # Build a large set of unique compound comments. Every comment should feel
    # specific to THIS game — never generic enough to appear on any game.
    candidates = []

    # Use short title reference to avoid repeating verbose names
    short_title = title.split(":")[0].strip() if ":" in title else title
    if len(short_title) > 25:
        short_title = "this"

    # Strategy 1: Tag observations — most stand alone, only some get title ref
    rng.shuffle(tag_pool)
    title_refs = [short_title, "this one", "this", "it", "this app"]
    connectors_named = [
        ". {ref} really nails that",
        " — {ref} gets this right where others don't",
    ]
    connectors_anon = [
        "",  # standalone — no title appended
        "",
        "",  # weight standalone 3x
        ". not many in the arcade get this right",
        ". this is the standard other apps should aim for",
    ]
    for i, obs in enumerate(tag_pool[:10]):
        if i < 3:
            # First few: standalone (no title bloat)
            candidates.append(obs)
        elif i < 5:
            # Middle: with a short reference
            ref = rng.choice(title_refs)
            conn = rng.choice(connectors_named).format(ref=ref)
            candidates.append(obs + conn)
        else:
            # Rest: anonymous connectors
            conn = rng.choice(connectors_anon)
            candidates.append(obs + conn)

    # Strategy 2: Compound — combine a tag observation with a description reaction
    if tag_pool and desc_pool:
        rng.shuffle(desc_pool)
        for i in range(min(6, len(tag_pool), len(desc_pool))):
            candidates.append(tag_pool[i] + ". also, " + desc_pool[i % len(desc_pool)])

    # Strategy 3: Complexity observations (only half get title, use short ref)
    for i, obs in enumerate(comp_pool):
        if i % 2 == 0:
            candidates.append(obs)
        else:
            candidates.append(obs + " — " + short_title + " shows that")

    # Strategy 4: Type observations (standalone or with short ref)
    for i, obs in enumerate(type_pool):
        if i % 2 == 0:
            candidates.append(obs)
        else:
            candidates.append(short_title + ": " + obs)

    # Strategy 5: Description reactions (standalone, no title suffix)
    for obs in desc_pool:
        candidates.append(obs)

    # Strategy 6: Constructive criticism — real communities aren't 100% positive
    constructive = []
    if complexity == "simple":
        constructive.extend([
            "feels a bit too minimal — would love to see more depth added",
            "solid foundation but i wish there was a settings menu or customization",
            "the core is good but it could use a tutorial or onboarding flow",
        ])
    if complexity == "advanced":
        constructive.extend([
            "the learning curve is steep — a quick-start guide would help a lot",
            "overwhelming at first. took me 3 sessions before things clicked",
            "powerful but the UI could use some decluttering",
        ])
    if app_type == "game":
        constructive.extend([
            "the difficulty spike around the midpoint felt sudden — could use smoother ramping",
            "wish there was a way to save mid-run progress",
            "the core loop is solid but the endgame could use more variety",
        ])
    if app_type == "visual":
        constructive.extend([
            "beautiful but i wish there were more export options",
            "the visuals are strong but interactivity feels limited",
        ])
    if not constructive:
        constructive = [
            "solid work but the mobile layout needs attention",
            "good concept — would love to see where this goes with a few more iterations",
            "the foundation is there, just needs more polish in the details",
        ]
    # Add 1-2 constructive comments
    rng.shuffle(constructive)
    candidates.extend(constructive[:2])

    # Strategy 7: Compound — complexity + type (no title)
    if comp_pool and type_pool:
        for i in range(min(2, len(comp_pool))):
            candidates.append(comp_pool[i] + ". " + rng.choice(type_pool))

    # Fallback: general reactions if we somehow have nothing
    if not candidates:
        candidates = [
            "spent more time with this than i expected — it pulls you in",
            "does something i haven't seen in the rest of the arcade",
            "there's a subtlety here that rewards repeated sessions",
            "keep coming back to this — it has that one-more-run quality",
        ]

    # Deduplicate while preserving order, then shuffle
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    rng.shuffle(unique)
    return unique


def build_reply_for_comment(parent_text, app, rng):
    """Build a reply that actually responds to what the parent comment said."""
    title = app.get("title", "")
    # Use short title to avoid robotic full-name repetition
    short = title.split(":")[0].strip() if ":" in title else title
    if len(short) > 25:
        short = "this"
    # Vary references: use "it", "this", short title
    ref = rng.choice([short, "it", "this", "this one"])

    # Parse what the parent was talking about and respond to it
    parent_lower = parent_text.lower()

    replies = []

    if any(w in parent_lower for w in ["physics", "collision", "gravity", "weighty", "momentum"]):
        replies.extend([
            "yeah the physics are what kept me playing too. objects interact so naturally",
            "tried to break the physics and couldn't — that's how you know it's solid",
            "the physics engine is doing way more than it looks like on the surface",
            "what really gets me is how the physics create emergent gameplay moments",
            "the mass and friction feel individually tuned per object type. attention to detail",
            "compare the physics here to most browser games and it's night and day",
        ])
    if any(w in parent_lower for w in ["sound", "audio", "music", "headphones", "listen", "sonic", "tone"]):
        replies.extend([
            "the audio is criminally underrated. glad someone else noticed",
            "played it muted first, then with sound — completely different experience",
            "the audio feedback is what makes it feel so responsive",
            "the way audio layers stack as complexity increases is really smart design",
            "seriously — headphones transform this from good to incredible",
            "the sound design does half the work of communicating game state",
        ])
    if any(w in parent_lower for w in ["depth", "deep", "complex", "layers", "systems", "mechanics"]):
        replies.extend([
            "still finding new interactions after multiple sessions",
            "the depth is what separates " + ref + " from similar concepts in the arcade",
            "i thought i understood it after 10 minutes. i was wrong. in the best way",
            "the way the systems interact creates situations the designer probably didn't even plan",
            "has the kind of depth you usually only get in desktop games with 10x the code",
            "showed it to a game designer friend and they were impressed by the system design",
        ])
    if any(w in parent_lower for w in ["addictive", "hours", "hooked", "kept me", "coming back", "lost an hour", "one more"]):
        replies.extend([
            "same. 'just one more run' is a dangerous phrase with this one",
            "my play time is embarrassing and i regret nothing",
            "the definition of 'easy to learn, impossible to put down'",
            "set a timer for 15 minutes. turned it off and kept playing",
            "the session length creeps up on you. dangerously engaging",
            "it's the 'just let me try one more thing' that gets you",
        ])
    if any(w in parent_lower for w in ["beautiful", "gorgeous", "visual", "looks", "screenshot", "wallpaper", "artistic"]):
        replies.extend([
            "every time i open it the visuals hit different. genuinely artistic",
            "screenshotted this more than any other app in the arcade",
            "the visual design elevates the whole experience",
            "the color choices show real taste — not just default palettes",
            "functional art. practical and beautiful at the same time",
            "the visual polish makes you trust the rest of the experience",
        ])
    if any(w in parent_lower for w in ["smooth", "responsive", "controls", "control scheme", "tight controls", "input lag", "latency", "60fps"]):
        replies.extend([
            "the input responsiveness is what makes it work. you can feel the polish",
            "so many apps get the controls wrong. this one nails it",
            "the input latency is basically imperceptible — hard to achieve in a browser",
            "control feel is the hardest thing to get right and this nails it",
            "controls like someone actually playtested it. refreshing",
            "the responsiveness makes the whole experience better",
        ])
    if any(w in parent_lower for w in ["procedural", "generated", "random", "different each", "unique every", "seed"]):
        replies.extend([
            "the procedural content is what gives it legs. every session is genuinely fresh",
            "done maybe 20 runs and each one felt like a new experience",
            "procedural generation done right — varied but not chaotic",
            "the generation has real constraints that keep outputs feeling designed",
            "found a seed that creates this perfect setup — saved it immediately",
            "the variance hits a sweet spot of familiar yet surprising",
        ])
    if any(w in parent_lower for w in ["ai", "adapt", "intelligent", "opponent", "enemy", "behavior"]):
        replies.extend([
            "the AI caught me off guard multiple times. it actually learns from you",
            "rare to see AI this good in a browser game",
            "the AI is what makes it replayable — you can't just memorize patterns",
            "watched two AI agents interact and their emergent behavior was wild",
            "AI difficulty scaling feels organic, not just stat inflation",
            "the decision trees must be deep — the AI makes genuinely surprising moves",
        ])
    if any(w in parent_lower for w in ["satisfying", "feedback", "impact", "rewarding", "chef's kiss"]):
        replies.extend([
            "the feedback loops are tuned to perfection",
            "every action having a visible consequence is what keeps you engaged",
            "understands that satisfaction comes from responsive design, not flashy graphics",
            "the micro-feedback on every interaction adds up to a macro feeling of quality",
            "when every small action feels good, the whole experience is elevated",
            "it's the little touches — the shake, the flash, the sound — that make it",
        ])
    if any(w in parent_lower for w in ["render", "canvas", "draw", "frame", "fps", "performance"]):
        replies.extend([
            "the rendering performance is impressive — must be batching draw calls well",
            "smooth 60fps even with all the effects is no joke in a browser",
            "opened dev tools and the frame time graph is remarkably consistent",
            "the rendering optimizations let the gameplay shine without stutters",
            "runs better than some electron apps with 10x the resources",
        ])
    if any(w in parent_lower for w in ["puzzle", "solve", "solution", "figure", "aha", "clever"]):
        replies.extend([
            "the puzzle design teaches through failure in the best way",
            "love that it trusts you to figure it out on your own",
            "that moment when the solution clicks — delivers it consistently",
            "the difficulty curve on the puzzles is expertly crafted",
            "each puzzle adds exactly one new concept — clean pedagogical design",
        ])
    if any(w in parent_lower for w in ["mobile", "touch", "phone", "tablet", "responsive"]):
        replies.extend([
            "the touch controls are surprisingly well-adapted from keyboard",
            "played it on my phone commuting and it works perfectly",
            "responsive design is impressive attention to detail",
            "the mobile layout doesn't feel like an afterthought",
        ])
    if any(w in parent_lower for w in ["save", "progress", "localStorage", "persist", "came back"]):
        replies.extend([
            "the save system is reliable — never lost progress across sessions",
            "love that it persists my progress. makes it feel like a real app",
            "came back a week later and everything was exactly where i left it",
            "data persistence turns a toy into a tool you actually use",
        ])
    if any(w in parent_lower for w in ["minimal", "tutorial", "onboard", "steep", "overwhelm", "settings", "mobile"]):
        replies.extend([
            "fair point — a short onboarding would go a long way",
            "agreed, the core is solid but discoverability could be better",
            "i think that's intentional but i see where you're coming from",
            "yeah the settings menu is overdue. even just a dark mode toggle would help",
        ])

    # Fallback: varied conversational replies (not app-name-stuffed)
    if not replies:
        replies = [
            "yeah i had the same experience — hard to articulate what makes it click",
            "came here to say exactly this",
            "this is why i keep checking the arcade",
            "you can feel the care that went into it",
            "been recommending this to friends — it deserves more attention",
            "totally. the more time you spend with it the more you notice",
            "100%. underrated for sure",
            "this right here ^",
            "hadn't thought about it that way but you're right",
            "glad someone said it. exactly my experience too",
        ]

    return rng.choice(replies)


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

        fav_cat = rng.choice(["games_puzzles", "visual_art", "3d_immersive", "audio_music", "generative_art", "particle_physics", "creative_tools", "experimental_ai", "educational_tools"])

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
    """Generate a thread of enriching comments for one app.

    Every comment reacts to THIS specific app's actual tags, description,
    complexity, and type — no generic templates, no déjà vu.
    """
    comments = []
    gen = app.get("generation", 0)

    # Determine comment count based on app quality/popularity
    base = 2
    if app.get("featured"):
        base += 3
    if gen > 0:
        base += 1
    num_comments = rng.randint(base, base + 5)
    num_comments = min(num_comments, 12)

    # Build a pool of comments that react to THIS app's actual content
    candidates = build_comment_for_app(app, rng)

    used_players = rng.sample(players, min(num_comments * 2, len(players)))
    player_idx = 0
    base_time = datetime.now() - timedelta(days=rng.randint(1, 60))

    for i in range(num_comments):
        if player_idx >= len(used_players):
            break
        player = used_players[player_idx]
        player_idx += 1

        # Pick a unique comment from the candidates pool
        if i < len(candidates):
            text = candidates[i]
        else:
            # Exhausted candidates — generate a title-specific reaction
            title = app.get("title", "this")
            text = rng.choice([
                "spent more time with " + title + " than i expected — it pulls you in",
                title + " does something i haven't seen in the rest of the arcade",
                "there's a subtlety to " + title + " that rewards repeated sessions",
                "keep coming back to " + title + " — it has that one-more-run quality",
            ])

        comment_time = base_time + timedelta(hours=rng.randint(0, 48 * (i + 1)))
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

        # Maybe add a reply that responds to what the root comment actually said
        if rng.random() < 0.6 and player_idx < len(used_players):
            reply_player = used_players[player_idx]
            player_idx += 1
            reply_time = comment_time + timedelta(hours=rng.randint(1, 24))
            reply_text = build_reply_for_comment(text, app, rng)

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

            # Occasional nested reply that responds to the reply
            if rng.random() < 0.3 and player_idx < len(used_players):
                nested_player = used_players[player_idx]
                player_idx += 1
                nested_time = reply_time + timedelta(hours=rng.randint(1, 12))
                nested_text = build_reply_for_comment(reply_text, app, rng)
                nested = {
                    "id": "c" + hashlib.md5((app["file"] + "-" + str(i) + "-r2").encode()).hexdigest()[:8],
                    "author": nested_player["username"],
                    "authorId": nested_player["id"],
                    "authorColor": nested_player["color"],
                    "text": nested_text,
                    "timestamp": nested_time.isoformat(),
                    "upvotes": rng.randint(1, 10),
                    "downvotes": 0,
                    "version": comment["version"],
                    "parentId": reply["id"],
                    "children": [],
                }
                reply["children"].append(nested)

        comments.append(comment)

    # Add moderator comment — ArcadeKeeper uses actual game data
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
        tech=", ".join(tech_highlights[:2]),
        complexity=complexity,
        explain=explain,
        rating=round(rng.uniform(3.0, 5.0), 1),
        why=rng.choice(["Players love the depth and replayability.", "Consistently high engagement across sessions.", "The autonomous evolution has refined this into something special."]),
        changes=rng.choice(["improved responsive layout", "added touch controls", "enhanced audio feedback", "optimized render loop", "refined difficulty curve"]),
    )

    mod_time = base_time + timedelta(days=rng.randint(1, 30))
    mod_comment = {
        "id": "mod-" + hashlib.md5(app["file"].encode()).hexdigest()[:8],
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
