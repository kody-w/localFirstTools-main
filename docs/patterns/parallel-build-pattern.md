# Parallel App Build Pattern

Standard operating procedure for building multiple self-contained HTML apps in parallel using Copilot CLI subagents.

## When to Use

Whenever the user requests multiple apps/games built simultaneously. This pattern handles: planning, validation, manifest updates, and deployment.

## The Pattern

### Step 1: Launch Parallel Build Agents

Spawn one `general-purpose` subagent per app in `background` mode. Each agent prompt MUST include:

1. **Full spec** of what to build
2. **Exact file path**: `apps/<category>/<filename>.html`
3. **Technical rules block** (copy verbatim):

```
TECHNICAL RULES:
- Single .html file, ALL CSS and JS inline
- NO external dependencies, NO CDN links, NO imports
- Must have <!DOCTYPE html>, <title>, <meta name="viewport">
- Wrap all JS in an IIFE: (()=>{ ... })();
- Use ONLY integer math for array indices (never float random for tile coords)
- Keep file under 100KB
- DO NOT create or modify any other files (especially not manifest.json)
```

4. **Self-validation requirement** — append this to every agent prompt:

```
BEFORE YOU FINISH, validate your own output by running:

node -e "
const h=require('fs').readFileSync('YOUR_FILE_PATH','utf8');
let br=0,pr=0,bk=0;
for(const c of h){if(c==='{')br++;if(c==='}')br--;if(c==='(')pr++;if(c===')')pr--;if(c==='[')bk++;if(c===']')bk--;}
const ok=br===0&&pr===0&&bk===0;
console.log(ok?'✅ PASS':'❌ FAIL','braces:'+br,'parens:'+pr,'brackets:'+bk);
console.log('DOCTYPE:',/<!DOCTYPE html>/i.test(h)?'✅':'❌');
console.log('Title:',/<title>.+<\/title>/.test(h)?'✅':'❌');
console.log('No CDN:',!/cdnjs|jsdelivr|unpkg/.test(h)?'✅':'❌');
console.log('IIFE:',/\(\(\)=>\{/.test(h)?'✅':'❌');
console.log('Size:',Math.round(h.length/1024)+'KB');
"

If ANY check fails, fix the issue and re-validate. Do NOT finish until all checks pass.
```

### Step 2: Launch Publish Agent

After all build agents are launched, launch ONE `general-purpose` agent in `background` mode that:

1. **Waits** — sleeps 90-120 seconds to let builders finish
2. **Checks which files exist** in the target directory
3. **Validates each file** using the node script above
4. **Updates manifest.json** — adds entries ONLY for files that exist AND pass validation
5. **Commits and pushes**:
```bash
git add -A
git commit -m "Add N new apps to gallery"
git push
```

The publish agent should ONLY add to manifest — never modify or delete existing entries.

### Step 3: Report Status

After agents complete, report:
- ✅ Which apps were built and deployed successfully
- ❌ Which apps failed (and why)
- 🌐 The live URL where user can test

## Manifest Entry Template

```python
{
    "title": "Human Readable Title",
    "file": "kebab-case-filename.html",
    "description": "One sentence description",
    "tags": ["tag1", "tag2", "tag3"],
    "complexity": "simple|intermediate|advanced",
    "type": "game|visual|audio|interactive|interface",
    "featured": True,
    "created": "YYYY-MM-DD"
}
```

## Category Reference

| Key | Folder | Use for |
|-----|--------|---------|
| `games_puzzles` | `games-puzzles` | Games, puzzles, interactive play |
| `visual_art` | `visual-art` | Drawing, visual effects, design |
| `3d_immersive` | `3d-immersive` | Three.js, WebGL, 3D worlds |
| `audio_music` | `audio-music` | Synths, music tools, audio viz |
| `generative_art` | `generative-art` | Procedural, algorithmic art |
| `particle_physics` | `particle-physics` | Physics sims, particles |
| `creative_tools` | `creative-tools` | Productivity, utilities |
| `experimental_ai` | `experimental-ai` | AI experiments, catch-all |

## Key Lessons Learned

- **Always use `rngI()` (integer) for array indices** — float indices cause `Cannot set properties of undefined`
- **Limit PointLights** — too many exceed `MAX_FRAGMENT_UNIFORM_VECTORS(1024)`. Use emissive MeshBasicMaterial instead
- **Splash screen z-index blocks clicks** — add click listeners on overlay elements, not just canvas behind them
- **Always wrap in IIFE** — `(()=>{ ... })();` — bare `const` at top level can collide
- **Validate brace/paren/bracket balance** before declaring done
- **CDN links are OK for Three.js** (`cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`) but nothing else. Prefer zero CDN when possible
