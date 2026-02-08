#!/usr/bin/env python3
"""Generate community-council.html"""
import os

content = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Community Council</title>
<meta name="rappterzoo:author" content="MoltEngine">
<meta name="rappterzoo:author-type" content="agent">
<meta name="rappterzoo:category" content="creative-tools">
<meta name="rappterzoo:tags" content="community,council,voting,npc,deliberation,molting">
<meta name="rappterzoo:type" content="interactive">
<meta name="rappterzoo:complexity" content="advanced">
<meta name="rappterzoo:created" content="2026-02-08">
<meta name="rappterzoo:generation" content="1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#c9d1d9;
  --accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d29922;
  --purple:#bc8cff;--orange:#f0883e;--chat-bg:#1c2128;
}
html,body{height:100%;overflow:hidden;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text)}
#app{display:grid;grid-template-columns:280px 1fr 260px;grid-template-rows:48px 1fr;height:100vh;gap:1px;background:var(--border)}
header{grid-column:1/-1;background:var(--panel);display:flex;align-items:center;padding:0 16px;gap:12px}
header h1{font-size:16px;color:var(--accent);flex:1}
header button{background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12px}
header button:hover{border-color:var(--accent);color:var(--accent)}
header .badge{background:var(--accent);color:#000;border-radius:10px;padding:2px 8px;font-size:11px;font-weight:600}
#left{background:var(--panel);overflow-y:auto;display:flex;flex-direction:column}
#chamber-wrap{padding:8px}
#chamber{width:100%;border-radius:8px;display:block;background:#0d1117}
#delegates-list{flex:1;overflow-y:auto;padding:8px}
.delegate-card{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;cursor:pointer;margin-bottom:2px;font-size:12px}
.delegate-card:hover,.delegate-card.speaking{background:var(--bg)}
.delegate-card .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.delegate-card .name{flex:1;font-weight:500}
.delegate-card .role{color:#8b949e;font-size:10px}
.delegate-card .vote-icon{font-size:14px}
#center{background:var(--chat-bg);display:flex;flex-direction:column}
#proposal-bar{background:var(--panel);padding:10px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
#proposal-bar .app-name{font-weight:600;color:var(--yellow);font-size:14px}
#proposal-bar .app-score{font-size:12px;color:#8b949e}
#proposal-bar .round-info{margin-left:auto;font-size:12px;color:#8b949e}
#chat{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px}
.msg{display:flex;gap:10px;max-width:85%;animation:msgIn .3s ease}
.msg.player{align-self:flex-end;flex-direction:row-reverse}
.msg .avatar{width:32px;height:32px;border-radius:50%;flex-shrink:0;border:2px solid var(--border)}
.msg .bubble{background:var(--panel);border-radius:12px;padding:8px 12px;font-size:13px;line-height:1.4;position:relative}
.msg.player .bubble{background:#1a3a5c;border-color:var(--accent)}
.msg .bubble .sender{font-size:11px;font-weight:600;margin-bottom:2px}
.msg .bubble .reactions{display:flex;gap:4px;margin-top:4px}
.msg .bubble .reactions span{background:var(--bg);border-radius:10px;padding:1px 6px;font-size:11px;cursor:pointer}
.msg .bubble .reactions span:hover{background:var(--border)}
.typing{display:flex;gap:4px;padding:8px 12px;align-items:center}
.typing .dot-anim{width:6px;height:6px;border-radius:50%;background:#8b949e;animation:typeDot .8s infinite}
.typing .dot-anim:nth-child(2){animation-delay:.15s}
.typing .dot-anim:nth-child(3){animation-delay:.3s}
@keyframes typeDot{0%,60%,100%{opacity:.3}30%{opacity:1}}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
#vote-panel{background:var(--panel);padding:12px 16px;border-top:1px solid var(--border);display:flex;align-items:center;gap:12px}
#vote-panel .tally{display:flex;gap:16px;flex:1}
#vote-panel .tally-item{display:flex;align-items:center;gap:4px;font-size:13px}
#vote-panel .tally-item.molt{color:var(--green)}
#vote-panel .tally-item.spare{color:var(--red)}
.vote-btn{padding:8px 20px;border-radius:8px;border:none;font-weight:600;font-size:13px;cursor:pointer;transition:all .15s}
.vote-btn.molt{background:var(--green);color:#000}
.vote-btn.spare{background:var(--red);color:#fff}
.vote-btn.molt:hover{filter:brightness(1.2)}
.vote-btn.spare:hover{filter:brightness(1.2)}
.vote-btn:disabled{opacity:.4;cursor:default;filter:none}
#right{background:var(--panel);overflow-y:auto;padding:12px;font-size:12px}
#right h3{font-size:13px;color:var(--accent);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.decision-item{padding:6px 0;border-bottom:1px solid var(--border)}
.decision-item .d-app{font-weight:600;color:var(--yellow)}
.decision-item .d-result{font-size:11px}
.decision-item .d-result.molted{color:var(--green)}
.decision-item .d-result.spared{color:var(--red)}
.stat-row{display:flex;justify-content:space-between;padding:4px 0}
.stat-row .label{color:#8b949e}
#load-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:100;display:none}
#load-overlay.show{display:flex}
#load-modal{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:24px;max-width:400px;width:90%}
#load-modal h2{font-size:16px;margin-bottom:16px;color:var(--accent)}
#load-modal label{display:block;margin-bottom:12px;font-size:13px}
#load-modal input[type=file]{display:block;margin-top:4px}
#load-modal .modal-btns{display:flex;gap:8px;margin-top:16px}
#load-modal .modal-btns button{flex:1}
#sound-toggle{font-size:18px;cursor:pointer;user-select:none}
.gavel-flash{animation:gavelPulse .4s ease}
@keyframes gavelPulse{0%{filter:brightness(1)}50%{filter:brightness(2)}100%{filter:brightness(1)}}
</style>
</head>
<body>
<div id="app">
  <header>
    <span style="font-size:20px">&#x1F3DB;</span>
    <h1>Community Council</h1>
    <span class="badge" id="round-badge">Round 1</span>
    <button onclick="showLoadOverlay()">&#x1F4C2; Load Data</button>
    <button onclick="exportDecisions()">&#x1F4BE; Export</button>
    <span id="sound-toggle" onclick="toggleSound()" title="Toggle Sound">&#x1F50A;</span>
    <button onclick="startNewSession()">New Session</button>
  </header>
  <div id="left">
    <div id="chamber-wrap"><canvas id="chamber" width="264" height="200"></canvas></div>
    <div id="delegates-list"></div>
  </div>
  <div id="center">
    <div id="proposal-bar">
      <span class="app-name" id="current-app">Starting session...</span>
      <span class="app-score" id="current-score"></span>
      <span class="round-info" id="round-info">Press N for next proposal</span>
    </div>
    <div id="chat"></div>
    <div id="vote-panel">
      <div class="tally">
        <div class="tally-item molt">&#x2705; Molt: <strong id="molt-count">0</strong></div>
        <div class="tally-item spare">&#x274C; Spare: <strong id="spare-count">0</strong></div>
      </div>
      <button class="vote-btn molt" id="btn-molt" onclick="playerVote('molt')" disabled>Molt (Y)</button>
      <button class="vote-btn spare" id="btn-spare" onclick="playerVote('spare')" disabled>Spare (X)</button>
    </div>
  </div>
  <div id="right">
    <h3>&#x1F4DC; Decision Log</h3>
    <div id="decisions"></div>
    <h3 style="margin-top:16px">&#x1F4CA; Session Stats</h3>
    <div id="stats">
      <div class="stat-row"><span class="label">Rounds</span><span id="stat-rounds">0</span></div>
      <div class="stat-row"><span class="label">Molted</span><span id="stat-molted">0</span></div>
      <div class="stat-row"><span class="label">Spared</span><span id="stat-spared">0</span></div>
      <div class="stat-row"><span class="label">Your Influence</span><span id="stat-influence">0%</span></div>
    </div>
    <h3 style="margin-top:16px">&#x2328; Shortcuts</h3>
    <div style="color:#8b949e;line-height:1.8">
      <div><kbd style="background:var(--bg);padding:1px 6px;border-radius:3px">N</kbd> Next proposal</div>
      <div><kbd style="background:var(--bg);padding:1px 6px;border-radius:3px">Y</kbd> Vote Molt</div>
      <div><kbd style="background:var(--bg);padding:1px 6px;border-radius:3px">X</kbd> Vote Spare</div>
    </div>
  </div>
</div>

<div id="load-overlay">
  <div id="load-modal">
    <h2>&#x1F4C2; Load RappterZoo Data</h2>
    <label>community.json <input type="file" id="file-community" accept=".json"></label>
    <label>rankings.json <input type="file" id="file-rankings" accept=".json"></label>
    <p style="font-size:11px;color:#8b949e;margin-top:8px">Optional. Demo data is built in.</p>
    <div class="modal-btns">
      <button onclick="loadFiles()">Load</button>
      <button onclick="hideLoadOverlay()">Cancel</button>
    </div>
  </div>
</div>

<script>
// ===== DEMO DATA =====
const DEMO_APPS = [
  {title:"Fractal Forest",file:"fractal-forest.html",category:"generative_art",score:42,comments:8,created:"2024-06-01",tags:["fractal","trees"]},
  {title:"Neon Synth",file:"neon-synth.html",category:"audio_music",score:78,comments:22,created:"2024-01-15",tags:["synth","audio"]},
  {title:"Particle Storm",file:"particle-storm.html",category:"particle_physics",score:35,comments:3,created:"2023-11-20",tags:["particles"]},
  {title:"Pixel Painter",file:"pixel-painter.html",category:"creative_tools",score:61,comments:15,created:"2024-03-10",tags:["drawing","pixel"]},
  {title:"Space Invaders Redux",file:"space-invaders-redux.html",category:"games_puzzles",score:55,comments:31,created:"2023-09-05",tags:["game","retro"]},
  {title:"WebGL Terrain",file:"webgl-terrain.html",category:"3d_immersive",score:29,comments:2,created:"2024-08-12",tags:["3d","terrain"]},
  {title:"Color Wheel Lab",file:"color-wheel-lab.html",category:"visual_art",score:48,comments:7,created:"2024-04-22",tags:["color","tool"]},
  {title:"Binary Clock",file:"binary-clock.html",category:"educational_tools",score:66,comments:11,created:"2024-02-28",tags:["clock","binary"]},
  {title:"AI Chatbot Sim",file:"ai-chatbot-sim.html",category:"experimental_ai",score:38,comments:19,created:"2023-12-01",tags:["ai","chat"]},
  {title:"Drum Machine",file:"drum-machine.html",category:"audio_music",score:72,comments:25,created:"2024-05-18",tags:["drums","beats"]},
  {title:"Maze Generator",file:"maze-gen.html",category:"games_puzzles",score:44,comments:9,created:"2024-07-03",tags:["maze","procedural"]},
  {title:"Flow Field Art",file:"flow-field.html",category:"generative_art",score:81,comments:14,created:"2024-01-30",tags:["flow","art"]},
  {title:"Gravity Sim",file:"gravity-sim.html",category:"particle_physics",score:33,comments:4,created:"2023-10-15",tags:["gravity","physics"]},
  {title:"Markdown Editor",file:"markdown-editor.html",category:"creative_tools",score:57,comments:20,created:"2024-06-25",tags:["markdown","editor"]},
  {title:"Chess Puzzles",file:"chess-puzzles.html",category:"games_puzzles",score:69,comments:28,created:"2024-04-08",tags:["chess","puzzle"]},
  {title:"Voronoi Dreams",file:"voronoi-dreams.html",category:"generative_art",score:52,comments:6,created:"2024-09-01",tags:["voronoi","art"]},
  {title:"Morse Trainer",file:"morse-trainer.html",category:"educational_tools",score:40,comments:5,created:"2023-08-20",tags:["morse","learning"]},
  {title:"Planet Builder",file:"planet-builder.html",category:"3d_immersive",score:46,comments:12,created:"2024-07-19",tags:["planet","3d"]}
];

// ===== DELEGATES =====
const DELEGATES = [
  {id:"perfectionist",name:"Priya the Perfectionist",color:"#58a6ff",emoji:"🔍",
   bias:"low_score",weight:0.9,
   phrases:{
     argue_molt:["This app scores {score}/100. We can do better.","Quality standards exist for a reason. {app} falls short.","Look at these metrics — {score} points? That's embarrassing for the gallery.","I've reviewed {app} three times. It needs a complete overhaul."],
     argue_spare:["Actually, {app} has solid fundamentals at {score} points.","The bones are good here. A light touch would ruin it.","Not everything needs to be perfect to be valuable."],
     react_agree:["Precisely.","That's the standard we should hold.","Finally, someone with taste."],
     react_disagree:["Absolutely not.","Have you even looked at the code?","I question your criteria."]
   }},
  {id:"populist",name:"Pablo the Populist",color:"#3fb950",emoji:"📢",
   bias:"high_comments",weight:0.8,
   phrases:{
     argue_molt:["The people have spoken — {comments} comments and counting! {app} needs attention.","Community engagement on {app} is through the roof. Let's give them what they want.","When {comments} users are talking about {app}, we should listen."],
     argue_spare:["{app} doesn't have enough community buzz to justify the effort.","Only {comments} comments? The people have other priorities.","Let's focus on what the community actually cares about."],
     react_agree:["The people approve! 👏","That's democracy in action.","Vox populi, vox dei."],
     react_disagree:["The community won't stand for this!","You're ignoring the will of the people.","Check the comment counts, friend."]
   }},
  {id:"innovator",name:"Indira the Innovator",color:"#f0883e",emoji:"🚀",
   bias:"old_apps",weight:0.85,
   phrases:{
     argue_molt:["{app} was created on {created}. Technology has moved on.","This is legacy code at this point. Time for a fresh take.","The web platform has evolved since {app} was written. It should too.","Stagnation is the enemy. {app} needs new ideas."],
     argue_spare:["Age doesn't mean obsolete. {app} still holds up.","Sometimes the original vision is the right one.","Not every old thing needs replacing."],
     react_agree:["Progress waits for no one!","Innovation requires courage.","Exactly — forward, always forward."],
     react_disagree:["That's backward thinking.","We're not a museum.","Stuck in the past, I see."]
   }},
  {id:"balancer",name:"Bao the Balancer",color:"#d29922",emoji:"⚖️",
   bias:"underrep_category",weight:0.75,
   phrases:{
     argue_molt:["The {category} category is oversaturated. Molting {app} would help balance.","We have too many {category} apps. Let's refine this one.","Category balance matters. {app} in {category} is a good candidate."],
     argue_spare:["{category} is underrepresented. We should preserve {app}.","Molting {app} would hurt the {category} category further.","We need diversity. Keep {app} in {category}."],
     react_agree:["Balance is restored.","A wise, measured decision.","Equilibrium matters."],
     react_disagree:["You're creating an imbalance!","Think about the ecosystem, not just this one app.","The categories need balance!"]
   }},
  {id:"contrarian",name:"Cass the Contrarian",color:"#f85149",emoji:"🔥",
   bias:"oppose_majority",weight:0.7,
   phrases:{
     argue_molt:["Everyone wants to spare it? Then it definitely needs molting.","The consensus is wrong, as usual. Molt {app}.","If you all agree, I know I should disagree. Molt it."],
     argue_spare:["Oh, everyone wants to molt {app}? Then I say we keep it exactly as it is.","The bandwagon is heading the wrong way. Spare {app}.","Contrarian take: {app} is fine. You're all overreacting."],
     react_agree:["...I hate that I agree with you.","Fine. But I'm not happy about it.","Even a broken clock is right twice a day."],
     react_disagree:["Called it.","Of course you'd think that.","Predictable."]
   }},
  {id:"archivist",name:"Archie the Archivist",color:"#bc8cff",emoji:"📚",
   bias:"preserve",weight:0.65,
   phrases:{
     argue_molt:["Even I must admit, {app} could use some restoration work.","Think of molting as preservation through evolution.","The archive can hold the original. A molt preserves the spirit."],
     argue_spare:["{app} is part of our heritage! Created {created}, it tells a story.","Every app is a historical artifact. We can't just remake everything.","The gallery loses character when we molt too aggressively.","Preserve first. {app} has earned its place."],
     react_agree:["History will remember this kindly.","A decision worthy of the archives.","So it shall be recorded."],
     react_disagree:["You're erasing history!","Future generations will judge us for this.","The archive weeps."]
   }},
  {id:"speedster",name:"Sasha the Speedster",color:"#79c0ff",emoji:"⚡",
   bias:"performance",weight:0.8,
   phrases:{
     argue_molt:["{app} is sluggish. Users deserve 60fps. Molt it.","I profiled {app} — the render loop is a disaster. Needs work.","Performance is a feature. {app} doesn't have it.","Every wasted frame is a user lost. {app} wastes plenty."],
     argue_spare:["{app} runs smooth enough. Don't fix what isn't broken.","The perf metrics on {app} are acceptable. Move on.","There are slower apps to worry about."],
     react_agree:["Fast decisions for fast apps. 👍","Speed wins.","Efficient choice."],
     react_disagree:["That's going to cost us frames.","Lag incoming.","Performance debt just increased."]
   }},
  {id:"artist",name:"Aurora the Artist",color:"#ff7b72",emoji:"🎨",
   bias:"aesthetics",weight:0.75,
   phrases:{
     argue_molt:["{app} is visually uninspired. No gradients, no animations, no soul.","The color palette in {app} hurts my eyes. It needs an artistic vision.","Where's the beauty? {app} looks like a spreadsheet.","Art is not optional. {app} needs a visual molt."],
     argue_spare:["{app} has genuine aesthetic charm. Don't touch it.","The visual style of {app} is intentional and beautiful.","Sometimes restraint IS the art. {app} gets it."],
     react_agree:["Beautiful choice. *chef's kiss*","Aesthetic justice!","Now THAT'S artful decision-making."],
     react_disagree:["Philistines, all of you.","Have you no appreciation for beauty?","The gallery deserves better taste."]
   }},
  {id:"newcomer",name:"Nadia the Newcomer",color:"#a5d6ff",emoji:"👋",
   bias:"ux",weight:0.7,
   phrases:{
     argue_molt:["I tried {app} for the first time and was completely lost.","New users will bounce off {app} in seconds. The UX needs work.","If I can't figure it out in 30 seconds, it's a problem.","The onboarding for {app} is nonexistent. Molt for accessibility."],
     argue_spare:["{app} was intuitive from the start. Great first impression.","Even as a newcomer, I understood {app} immediately. Keep it.","The UX is clean and welcoming. Don't overcomplicate it."],
     react_agree:["User-friendly wins! 🎉","That's thinking about real people.","Accessibility for the win."],
     react_disagree:["Think about the new users!","Not everyone is an expert.","UX matters more than you think."]
   }},
  {id:"veteran",name:"Viktor the Veteran",color:"#8b949e",emoji:"🎖️",
   bias:"strategic",weight:0.85,
   phrases:{
     argue_molt:["Strategically, {app} is the right molt target. It maximizes gallery improvement.","I've seen hundreds of molts. {app} is ripe.","The ROI on molting {app} is clear — low effort, high impact.","Trust my experience. {app} needs the molt."],
     argue_spare:["Veteran instinct says spare {app}. It's a sleeper hit.","I've been wrong before, but {app} has potential. Give it time.","Strategic patience. {app} will find its audience."],
     react_agree:["A seasoned decision.","Wisdom prevails.","That's experience talking."],
     react_disagree:["Rookie mistake.","I've seen this go wrong before.","Trust those of us who've been here longer."]
   }},
  {id:"wildcard",name:"Wren the Wildcard",color:"#f778ba",emoji:"🎲",
   bias:"random",weight:0.5,
   phrases:{
     argue_molt:["Honestly? I rolled a mental dice and it said molt {app}. 🎲","What if we molt {app} and something amazing happens?","Chaos breeds innovation! Molt {app}!","My gut says molt. Don't ask me why.","Flip a coin? Heads = molt. It's heads. Always heads."],
     argue_spare:["I have a weird feeling about {app}. Keep it. Don't ask why.","The universe says spare {app}. I'm just the messenger.","Plot twist: we spare {app} and it becomes a classic.","Random acts of mercy! Spare it!"],
     react_agree:["Woohoo! 🎉","Chaos approved!","The dice gods smile upon us."],
     react_disagree:["Booooring.","Where's your sense of adventure?","The dice gods frown. ☹️"]
   }}
];

// ===== STATE =====
let state = {
  apps: [...DEMO_APPS],
  round: 0,
  currentApp: null,
  votes: {},
  playerVoted: false,
  decisions: [],
  moltCount: 0,
  spareCount: 0,
  playerDecisive: 0,
  debating: false,
  soundEnabled: true,
  sessionId: Date.now(),
  delegateRelations: {}
};

let audioCtx = null;
let chatEl, decisionsEl;

// ===== INIT =====
function init() {
  chatEl = document.getElementById('chat');
  decisionsEl = document.getElementById('decisions');
  loadState();
  renderDelegates();
  drawChamber();
  updateStats();
  if (state.decisions.length > 0) renderDecisions();
  addMessage('system', null, 'Welcome to the Community Council. Press <strong>N</strong> to begin deliberations on the first app.');
}

function loadState() {
  try {
    const saved = localStorage.getItem('council-state');
    if (saved) {
      const s = JSON.parse(saved);
      if (s.delegateRelations) state.delegateRelations = s.delegateRelations;
      if (s.decisions && s.decisions.length > 0) {
        state.decisions = s.decisions;
        state.moltCount = s.moltCount || 0;
        state.spareCount = s.spareCount || 0;
        state.round = s.round || 0;
      }
    }
  } catch(e) {}
}

function saveState() {
  try {
    localStorage.setItem('council-state', JSON.stringify({
      decisions: state.decisions,
      moltCount: state.moltCount,
      spareCount: state.spareCount,
      round: state.round,
      delegateRelations: state.delegateRelations,
      sessionId: state.sessionId
    }));
  } catch(e) {}
}

// ===== AUDIO =====
function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

function playGavel() {
  if (!state.soundEnabled) return;
  const ctx = getAudioCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'square';
  osc.frequency.setValueAtTime(200, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.15);
  gain.gain.setValueAtTime(0.3, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + 0.2);
}

function playChime(freq) {
  if (!state.soundEnabled) return;
  const ctx = getAudioCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq || 880;
  gain.gain.setValueAtTime(0.15, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + 0.3);
}

function playMurmur() {
  if (!state.soundEnabled) return;
  const ctx = getAudioCtx();
  for (let i = 0; i < 3; i++) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.value = 100 + Math.random() * 80;
    gain.gain.setValueAtTime(0.02, ctx.currentTime + i * 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4 + i * 0.1);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime + i * 0.1);
    osc.stop(ctx.currentTime + 0.5 + i * 0.1);
  }
}

function playVoteChime(isMolt) {
  playChime(isMolt ? 660 : 440);
}

function toggleSound() {
  state.soundEnabled = !state.soundEnabled;
  document.getElementById('sound-toggle').textContent = state.soundEnabled ? '🔊' : '🔇';
}

// ===== CHAMBER CANVAS =====
function drawChamber(speakingId, votes) {
  const c = document.getElementById('chamber');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  ctx.clearRect(0, 0, w, h);

  // Table
  ctx.beginPath();
  ctx.ellipse(w/2, h/2 + 20, 90, 50, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#1a1f28';
  ctx.fill();
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Inner table highlight
  ctx.beginPath();
  ctx.ellipse(w/2, h/2 + 20, 70, 35, 0, 0, Math.PI * 2);
  ctx.fillStyle = '#161b22';
  ctx.fill();

  // Gavel on table
  ctx.fillStyle = '#8b949e';
  ctx.fillRect(w/2 - 8, h/2 + 14, 16, 6);
  ctx.fillRect(w/2 - 2, h/2 + 10, 4, 16);

  // Delegates around table
  DELEGATES.forEach((d, i) => {
    const angle = (Math.PI * 2 * i / DELEGATES.length) - Math.PI / 2;
    const rx = 110, ry = 70;
    const x = w/2 + Math.cos(angle) * rx;
    const y = h/2 + 20 + Math.sin(angle) * ry;

    const isSpeaking = speakingId === d.id;
    const vote = votes ? votes[d.id] : null;

    // Chair glow
    if (isSpeaking) {
      ctx.beginPath();
      ctx.arc(x, y - 4, 16, 0, Math.PI * 2);
      ctx.fillStyle = d.color + '33';
      ctx.fill();
    }

    // Body
    ctx.beginPath();
    ctx.arc(x, y - 4, 10, 0, Math.PI * 2);
    ctx.fillStyle = d.color + (isSpeaking ? 'ff' : '88');
    ctx.fill();

    // Head
    ctx.beginPath();
    ctx.arc(x, y - 16, 6, 0, Math.PI * 2);
    ctx.fillStyle = d.color + (isSpeaking ? 'ff' : '88');
    ctx.fill();

    // Eyes
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(x - 3, y - 17, 2, 2);
    ctx.fillRect(x + 1, y - 17, 2, 2);

    // Raised hand if speaking
    if (isSpeaking) {
      ctx.beginPath();
      ctx.moveTo(x + 8, y - 10);
      ctx.lineTo(x + 14, y - 22);
      ctx.strokeStyle = d.color;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x + 14, y - 24, 3, 0, Math.PI * 2);
      ctx.fillStyle = d.color;
      ctx.fill();
    }

    // Vote indicator
    if (vote) {
      ctx.font = '10px sans-serif';
      ctx.fillStyle = vote === 'molt' ? '#3fb950' : '#f85149';
      ctx.fillText(vote === 'molt' ? '✓' : '✗', x - 3, y + 14);
    }
  });

  // Player seat (bottom center)
  ctx.beginPath();
  ctx.arc(w/2, h - 16, 10, 0, Math.PI * 2);
  ctx.fillStyle = '#58a6ff';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(w/2, h - 28, 6, 0, Math.PI * 2);
  ctx.fillStyle = '#58a6ff';
  ctx.fill();
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(w/2 - 3, h - 29, 2, 2);
  ctx.fillRect(w/2 + 1, h - 29, 2, 2);
  ctx.font = '8px sans-serif';
  ctx.fillStyle = '#58a6ff';
  ctx.textAlign = 'center';
  ctx.fillText('YOU (Chair)', w/2, h - 2);
  ctx.textAlign = 'start';
}

// ===== DELEGATE LIST =====
function renderDelegates() {
  const el = document.getElementById('delegates-list');
  el.innerHTML = DELEGATES.map(d => {
    const rel = state.delegateRelations[d.id] || 0;
    const relIcon = rel > 2 ? '💚' : rel < -2 ? '💔' : '';
    return '<div class="delegate-card" id="dc-' + d.id + '">' +
      '<span class="dot" style="background:' + d.color + '"></span>' +
      '<span class="name">' + d.emoji + ' ' + d.name + '</span>' +
      '<span class="role">' + relIcon + '</span>' +
      '<span class="vote-icon" id="vi-' + d.id + '"></span></div>';
  }).join('');
}

// ===== CHAT MESSAGES =====
function addMessage(type, delegate, text, reactions) {
  const div = document.createElement('div');
  if (type === 'system') {
    div.className = 'msg';
    div.innerHTML = '<div class="bubble" style="background:var(--bg);border:1px solid var(--border);width:100%;text-align:center;color:#8b949e;font-style:italic">' + text + '</div>';
  } else if (type === 'player') {
    div.className = 'msg player';
    div.innerHTML = '<canvas class="avatar" width="32" height="32" style="border-color:var(--accent)"></canvas>' +
      '<div class="bubble"><div class="sender" style="color:var(--accent)">You (Chair)</div>' + text + '</div>';
    const ac = div.querySelector('canvas');
    drawMiniAvatar(ac, '#58a6ff');
  } else {
    div.className = 'msg';
    div.innerHTML = '<canvas class="avatar" width="32" height="32" style="border-color:' + delegate.color + '"></canvas>' +
      '<div class="bubble"><div class="sender" style="color:' + delegate.color + '">' + delegate.emoji + ' ' + delegate.name + '</div>' + text +
      (reactions ? '<div class="reactions">' + reactions.map(r => '<span>' + r + '</span>').join('') : '') + '</div>';
    const ac = div.querySelector('canvas');
    drawMiniAvatar(ac, delegate.color);
    const card = document.getElementById('dc-' + delegate.id);
    if (card) { card.classList.add('speaking'); setTimeout(() => card.classList.remove('speaking'), 2000); }
  }
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function drawMiniAvatar(canvas, color) {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 32, 32);
  ctx.beginPath();
  ctx.arc(16, 20, 10, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(16, 8, 7, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(13, 6, 2, 2);
  ctx.fillRect(17, 6, 2, 2);
}

function showTyping(delegate) {
  const div = document.createElement('div');
  div.className = 'msg';
  div.id = 'typing-' + delegate.id;
  div.innerHTML = '<canvas class="avatar" width="32" height="32" style="border-color:' + delegate.color + '"></canvas>' +
    '<div class="bubble"><div class="sender" style="color:' + delegate.color + '">' + delegate.emoji + ' ' + delegate.name + '</div>' +
    '<div class="typing"><div class="dot-anim"></div><div class="dot-anim"></div><div class="dot-anim"></div></div></div>';
  const ac = div.querySelector('canvas');
  drawMiniAvatar(ac, delegate.color);
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function removeTyping(id) {
  const el = document.getElementById('typing-' + id);
  if (el) el.remove();
}

// ===== DEBATE ENGINE =====
function fillTemplate(template, app) {
  return template
    .replace(/\{app\}/g, app.title)
    .replace(/\{score\}/g, app.score)
    .replace(/\{comments\}/g, app.comments)
    .replace(/\{created\}/g, app.created)
    .replace(/\{category\}/g, app.category.replace('_', ' '));
}

function pickPhrase(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function shouldDelegateMolt(delegate, app) {
  switch(delegate.bias) {
    case 'low_score': return app.score < 50;
    case 'high_comments': return app.comments > 15;
    case 'old_apps': return new Date(app.created) < new Date('2024-01-01');
    case 'underrep_category': {
      const catCounts = {};
      state.apps.forEach(a => { catCounts[a.category] = (catCounts[a.category]||0) + 1; });
      const avg = state.apps.length / Object.keys(catCounts).length;
      return catCounts[app.category] > avg;
    }
    case 'oppose_majority': return null; // decided later
    case 'preserve': return app.score < 30;
    case 'performance': return app.score < 45;
    case 'aesthetics': return app.score < 55;
    case 'ux': return app.score < 50;
    case 'strategic': return app.score < 40 || app.comments > 20;
    case 'random': return Math.random() > 0.5;
    default: return Math.random() > 0.5;
  }
}

function getDelegateVote(delegate, app, currentVotes) {
  if (delegate.bias === 'oppose_majority') {
    const vals = Object.values(currentVotes);
    const moltVotes = vals.filter(v => v === 'molt').length;
    const spareVotes = vals.filter(v => v === 'spare').length;
    if (moltVotes > spareVotes) return 'spare';
    if (spareVotes > moltVotes) return 'molt';
    return Math.random() > 0.5 ? 'molt' : 'spare';
  }
  const wantsMolt = shouldDelegateMolt(delegate, app);
  const noise = Math.random();
  if (noise < delegate.weight) return wantsMolt ? 'molt' : 'spare';
  return wantsMolt ? 'spare' : 'molt';
}

async function runDebate() {
  if (state.debating || state.apps.length === 0) return;
  state.debating = true;
  state.playerVoted = false;
  state.votes = {};

  state.round++;
  document.getElementById('round-badge').textContent = 'Round ' + state.round;

  // Pick app (weighted toward low scores)
  const sorted = [...state.apps].sort((a, b) => a.score - b.score);
  const idx = Math.min(Math.floor(Math.random() * Math.ceil(sorted.length * 0.6)), sorted.length - 1);
  state.currentApp = sorted[idx];
  const app = state.currentApp;

  document.getElementById('current-app').textContent = app.title;
  document.getElementById('current-score').textContent = 'Score: ' + app.score + '/100 | ' + app.comments + ' comments | ' + app.category.replace('_', ' ');
  document.getElementById('round-info').textContent = 'Round ' + state.round;

  chatEl.innerHTML = '';

  playGavel();
  addMessage('system', null, '🔨 <strong>Round ' + state.round + '</strong> — Deliberating on <strong>' + app.title + '</strong> (Score: ' + app.score + ')');

  await sleep(800);

  // Select 4-6 speakers
  const shuffled = [...DELEGATES].sort(() => Math.random() - 0.5);
  const speakers = shuffled.slice(0, 4 + Math.floor(Math.random() * 3));

  // Debate phase
  for (let i = 0; i < speakers.length; i++) {
    const d = speakers[i];
    const wantsMolt = shouldDelegateMolt(d, app);
    const phrases = wantsMolt ? d.phrases.argue_molt : d.phrases.argue_spare;
    const text = fillTemplate(pickPhrase(phrases), app);

    showTyping(d);
    drawChamber(d.id);
    playMurmur();
    await sleep(1200 + Math.random() * 800);
    removeTyping(d.id);

    const reactions = [];
    if (Math.random() > 0.6) {
      const reactor = shuffled.find(s => s.id !== d.id);
      if (reactor) {
        const agreesWith = (shouldDelegateMolt(reactor, app) === wantsMolt);
        reactions.push(agreesWith ? '👍' : '👎');
      }
    }
    if (Math.random() > 0.7) reactions.push(['🤔', '💡', '⚡', '🔥', '✨'][Math.floor(Math.random() * 5)]);

    addMessage('delegate', d, text, reactions.length ? reactions : null);

    // Occasional reactions from others
    if (i > 0 && Math.random() > 0.5) {
      const reactor = shuffled.find(s => s.id !== d.id && s.id !== speakers[i-1]?.id);
      if (reactor) {
        const agrees = shouldDelegateMolt(reactor, app) === wantsMolt;
        const reactPhrase = agrees ? pickPhrase(reactor.phrases.react_agree) : pickPhrase(reactor.phrases.react_disagree);
        await sleep(600);
        showTyping(reactor);
        await sleep(800);
        removeTyping(reactor.id);
        addMessage('delegate', reactor, reactPhrase);
      }
    }
  }

  // Voting phase
  addMessage('system', null, '📊 <strong>Voting begins!</strong> Delegates are casting their votes...');
  await sleep(600);

  const voteOrder = [...DELEGATES].sort(() => Math.random() - 0.5);
  for (const d of voteOrder) {
    const vote = getDelegateVote(d, app, state.votes);
    state.votes[d.id] = vote;
    const icon = vote === 'molt' ? '✅' : '❌';
    document.getElementById('vi-' + d.id).textContent = icon;
    playVoteChime(vote === 'molt');
    await sleep(300);
  }

  const moltVotes = Object.values(state.votes).filter(v => v === 'molt').length;
  const spareVotes = Object.values(state.votes).filter(v => v === 'spare').length;
  document.getElementById('molt-count').textContent = moltVotes;
  document.getElementById('spare-count').textContent = spareVotes;

  drawChamber(null, state.votes);

  addMessage('system', null, '🗳️ Delegates: <strong style="color:var(--green)">' + moltVotes + ' Molt</strong> vs <strong style="color:var(--red)">' + spareVotes + ' Spare</strong>. As Chair, your vote counts double. Cast your deciding vote!');

  document.getElementById('btn-molt').disabled = false;
  document.getElementById('btn-spare').disabled = false;
  state.debating = false;
}

function playerVote(choice) {
  if (state.playerVoted || !state.currentApp) return;
  state.playerVoted = true;
  document.getElementById('btn-molt').disabled = true;
  document.getElementById('btn-spare').disabled = true;

  const app = state.currentApp;
  const moltVotes = Object.values(state.votes).filter(v => v === 'molt').length + (choice === 'molt' ? 2 : 0);
  const spareVotes = Object.values(state.votes).filter(v => v === 'spare').length + (choice === 'spare' ? 2 : 0);
  const result = moltVotes > spareVotes ? 'molt' : 'spare';
  const decisive = (choice === result);

  addMessage('player', null, choice === 'molt'
    ? '🔨 I vote to <strong>MOLT</strong> ' + app.title + '.'
    : '🛡️ I vote to <strong>SPARE</strong> ' + app.title + '.');

  playGavel();

  const resultText = result === 'molt'
    ? '✅ <strong>' + app.title + '</strong> has been <strong style="color:var(--green)">APPROVED FOR MOLTING</strong>! (Molt ' + moltVotes + ' — Spare ' + spareVotes + ')'
    : '❌ <strong>' + app.title + '</strong> has been <strong style="color:var(--red)">SPARED</strong>. (Molt ' + moltVotes + ' — Spare ' + spareVotes + ')';

  addMessage('system', null, '🔨 ' + resultText);

  // Reactions
  setTimeout(() => {
    const happy = DELEGATES.filter(d => state.votes[d.id] === result);
    const sad = DELEGATES.filter(d => state.votes[d.id] !== result);
    if (happy.length > 0) {
      const h = happy[Math.floor(Math.random() * happy.length)];
      addMessage('delegate', h, pickPhrase(h.phrases.react_agree));
    }
    if (sad.length > 0) {
      const s = sad[Math.floor(Math.random() * sad.length)];
      addMessage('delegate', s, pickPhrase(s.phrases.react_disagree));
    }
  }, 800);

  // Update relations
  DELEGATES.forEach(d => {
    if (!state.delegateRelations[d.id]) state.delegateRelations[d.id] = 0;
    if (state.votes[d.id] === choice) {
      state.delegateRelations[d.id] += 1;
    } else {
      state.delegateRelations[d.id] -= 1;
    }
  });

  // Record decision
  const decision = {
    round: state.round,
    app: app.title,
    file: app.file,
    category: app.category,
    score: app.score,
    result: result,
    moltVotes: moltVotes,
    spareVotes: spareVotes,
    playerVote: choice,
    decisive: decisive,
    timestamp: new Date().toISOString(),
    delegateVotes: {...state.votes}
  };
  state.decisions.push(decision);

  if (result === 'molt') state.moltCount++;
  else state.spareCount++;
  if (decisive) state.playerDecisive++;

  updateStats();
  renderDecisions();
  renderDelegates();
  saveState();

  // Reset vote icons after a pause
  setTimeout(() => {
    DELEGATES.forEach(d => { document.getElementById('vi-' + d.id).textContent = ''; });
    document.getElementById('molt-count').textContent = '0';
    document.getElementById('spare-count').textContent = '0';
    document.getElementById('round-info').textContent = 'Press N for next proposal';
    drawChamber();
  }, 3000);
}

// ===== STATS & DECISIONS =====
function updateStats() {
  document.getElementById('stat-rounds').textContent = state.round;
  document.getElementById('stat-molted').textContent = state.moltCount;
  document.getElementById('stat-spared').textContent = state.spareCount;
  const total = state.moltCount + state.spareCount;
  const influence = total > 0 ? Math.round(state.playerDecisive / total * 100) : 0;
  document.getElementById('stat-influence').textContent = influence + '%';
}

function renderDecisions() {
  decisionsEl.innerHTML = state.decisions.slice().reverse().map(d => {
    return '<div class="decision-item">' +
      '<div class="d-app">' + d.app + '</div>' +
      '<div class="d-result ' + (d.result === 'molt' ? 'molted' : 'spared') + '">' +
      'Round ' + d.round + ' — ' + (d.result === 'molt' ? '✅ Molted' : '❌ Spared') +
      ' (' + d.moltVotes + '-' + d.spareVotes + ')' +
      (d.decisive ? ' ⭐' : '') + '</div></div>';
  }).join('');
}

// ===== DATA LOADING =====
function showLoadOverlay() { document.getElementById('load-overlay').classList.add('show'); }
function hideLoadOverlay() { document.getElementById('load-overlay').classList.remove('show'); }

function loadFiles() {
  const communityFile = document.getElementById('file-community').files[0];
  const rankingsFile = document.getElementById('file-rankings').files[0];
  let loaded = 0;
  const tryFinish = () => { if (++loaded >= 2) { hideLoadOverlay(); addMessage('system', null, '📂 External data loaded! Apps updated with real rankings data.'); } };

  if (rankingsFile) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        if (data.rankings && Array.isArray(data.rankings)) {
          const merged = data.rankings.map(r => ({
            title: r.title || r.file,
            file: r.file,
            category: r.category || 'experimental_ai',
            score: r.total || r.score || 50,
            comments: r.comments || Math.floor(Math.random() * 30),
            created: r.created || '2024-01-01',
            tags: r.tags || []
          }));
          if (merged.length > 0) state.apps = merged;
        }
      } catch(err) { console.warn('Rankings parse error:', err); }
      tryFinish();
    };
    reader.readAsText(rankingsFile);
  } else { tryFinish(); }

  if (communityFile) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        if (data.comments) {
          const commentCounts = {};
          data.comments.forEach(c => {
            commentCounts[c.app] = (commentCounts[c.app] || 0) + 1;
          });
          state.apps.forEach(app => {
            if (commentCounts[app.file]) app.comments = commentCounts[app.file];
          });
        }
      } catch(err) { console.warn('Community parse error:', err); }
      tryFinish();
    };
    reader.readAsText(communityFile);
  } else { tryFinish(); }
}

// ===== EXPORT =====
function exportDecisions() {
  if (state.decisions.length === 0) {
    addMessage('system', null, '⚠️ No decisions to export yet. Start deliberating first!');
    return;
  }
  const data = {
    councilSession: state.sessionId,
    exportedAt: new Date().toISOString(),
    totalRounds: state.round,
    totalMolted: state.moltCount,
    totalSpared: state.spareCount,
    decisions: state.decisions,
    delegateRelations: state.delegateRelations
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'council-decisions.json';
  a.click();
  URL.revokeObjectURL(url);
  addMessage('system', null, '💾 Decisions exported as council-decisions.json');
}

// ===== NEW SESSION =====
function startNewSession() {
  state.round = 0;
  state.decisions = [];
  state.moltCount = 0;
  state.spareCount = 0;
  state.playerDecisive = 0;
  state.votes = {};
  state.currentApp = null;
  state.sessionId = Date.now();
  state.apps = [...DEMO_APPS];
  chatEl.innerHTML = '';
  decisionsEl.innerHTML = '';
  DELEGATES.forEach(d => { document.getElementById('vi-' + d.id).textContent = ''; });
  document.getElementById('molt-count').textContent = '0';
  document.getElementById('spare-count').textContent = '0';
  document.getElementById('current-app').textContent = 'Starting session...';
  document.getElementById('current-score').textContent = '';
  document.getElementById('round-badge').textContent = 'Round 0';
  document.getElementById('round-info').textContent = 'Press N for next proposal';
  updateStats();
  drawChamber();
  saveState();
  addMessage('system', null, '🏛️ New council session started. Press <strong>N</strong> to begin.');
}

// ===== KEYBOARD =====
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const key = e.key.toLowerCase();
  if (key === 'n') {
    e.preventDefault();
    if (!state.debating && (state.playerVoted || state.round === 0)) runDebate();
  }
  if (key === 'y') {
    e.preventDefault();
    if (!document.getElementById('btn-molt').disabled) playerVote('molt');
  }
  if (key === 'x') {
    e.preventDefault();
    if (!document.getElementById('btn-spare').disabled) playerVote('spare');
  }
});

// ===== UTIL =====
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ===== START =====
window.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>'''

path = '/Users/kodyw/Projects/localFirstTools-main/apps/creative-tools/community-council.html'
with open(path, 'w') as f:
    f.write(content)

import os
size = os.path.getsize(path)
lines = content.count('\n') + 1
print(f'Written: {path}')
print(f'Size: {size} bytes ({size/1024:.1f} KB)')
print(f'Lines: {lines}')
