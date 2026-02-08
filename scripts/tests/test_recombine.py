"""Tests for recombine.py — all mocked, no network, no LLM calls."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from recombine import (
    GENE_PATTERNS,
    build_synthesis_prompt,
    crossover,
    detect_genes,
    extract_gene_samples,
    inject_lineage_tags,
    load_experience,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHYSICS_GAME = """<!DOCTYPE html>
<html><head><title>Physics Game</title></head><body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

class Ball {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.vx = Math.random() * 4 - 2;
        this.vy = 0;
    }
    update(dt) {
        this.vy += gravity * dt;
        this.x += this.vx * dt;
        this.y += this.vy * dt;
        if (this.y > canvas.height) {
            this.y = canvas.height;
            this.vy *= -bounce;
        }
        if (checkCollision(this, player)) {
            this.vy = -10;
        }
    }
    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, 10, 0, Math.PI * 2);
        ctx.fill();
    }
}

const gravity = 0.5;
const bounce = 0.8;
const friction = 0.99;
let player = { x: 400, y: 500 };
let balls = [new Ball(100, 100), new Ball(300, 50)];

function checkCollision(a, b) {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return Math.sqrt(dx*dx + dy*dy) < 30;
}

addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') player.x -= 10;
    if (e.key === 'ArrowRight') player.x += 10;
});

function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let b of balls) {
        b.update(1);
        b.draw();
    }
    ctx.fillRect(player.x - 15, player.y - 5, 30, 10);
    requestAnimationFrame(gameLoop);
}
gameLoop();
</script>
</body></html>"""

AUDIO_GAME = """<!DOCTYPE html>
<html><head><title>Audio Game</title></head><body>
<script>
const audioCtx = new AudioContext();

function playSound(freq, duration) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.frequency.value = freq;
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
    osc.stop(audioCtx.currentTime + duration);
}

function playNote(note) { playSound(440 * Math.pow(2, note/12), 0.3); }
function playSFX(type) { playSound(type === 'hit' ? 200 : 800, 0.1); }
function playTone(freq) { playSound(freq, 0.5); }
function playAudio(freq) { playSound(freq, 0.2); }
function playChord(notes) { notes.forEach(n => playNote(n)); }

let gameState = 'playing';
let score = 0;
let keys = {};

addEventListener('keydown', e => {
    keys[e.key] = true;
    playNote(Math.floor(Math.random() * 12));
    score += 10;
});
addEventListener('keyup', e => { keys[e.key] = false; });

function update() {
    if (gameState === 'playing') {
        score += 1;
    }
}

setInterval(update, 100);
</script>
</body></html>"""

PARTICLE_GAME = """<!DOCTYPE html>
<html><head><title>Particles</title></head><body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

class Particle {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.vx = (Math.random() - 0.5) * 5;
        this.vy = (Math.random() - 0.5) * 5;
        this.lifetime = 1.0;
        this.maxLife = 1.0;
        this.age = 0;
        this.alpha = 1;
    }
    update(dt) {
        this.x += this.vx * dt;
        this.y += this.vy * dt;
        this.age += dt;
        this.lifetime -= dt;
        this.alpha = this.lifetime / this.maxLife;
    }
    draw(ctx) {
        ctx.globalAlpha = Math.max(0, this.alpha);
        ctx.fillStyle = '#ff0';
        ctx.fillRect(this.x - 2, this.y - 2, 4, 4);
        ctx.globalAlpha = 1;
    }
}

let particles = [];

function emit(x, y, count) {
    for (let i = 0; i < count; i++) {
        particles.push(new Particle(x, y));
    }
}

function burst(x, y) {
    emit(x, y, 50);
}

function spawn(x, y) {
    emit(x, y, 10);
}

canvas.addEventListener('mousemove', e => {
    spawn(e.clientX, e.clientY);
});

canvas.addEventListener('click', e => {
    burst(e.clientX, e.clientY);
});

function loop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles = particles.filter(p => p.lifetime > 0);
    for (let p of particles) {
        p.update(0.016);
        p.draw(ctx);
    }
    ctx.fillStyle = '#fff';
    ctx.fillText('Particles: ' + particles.length, 10, 20);
    requestAnimationFrame(loop);
}
loop();
</script>
</body></html>"""


SAMPLE_EXPERIENCE = {
    "id": "discovery",
    "emotion": "The thrill of finding something hidden",
    "description": "The player stumbles upon secrets...",
    "mechanical_hints": ["Hidden areas", "Procedural secrets"],
    "anti_patterns": ["Don't put arrows pointing to secrets"],
    "color_mood": ["deep blues", "warm golds"],
    "audio_mood": "ambient with subtle melodic hints",
}


# ---------------------------------------------------------------------------
# Tests: Gene Detection
# ---------------------------------------------------------------------------
class TestDetectGenes:
    def test_physics_genes(self):
        genes = detect_genes(PHYSICS_GAME)
        assert genes["physics_engine"]["present"] is True
        assert genes["physics_engine"]["strength"] >= 2
        assert genes["render_pipeline"]["present"] is True
        assert genes["entity_system"]["present"] is True

    def test_audio_genes(self):
        genes = detect_genes(AUDIO_GAME)
        assert genes["audio_engine"]["present"] is True
        assert genes["audio_engine"]["strength"] >= 2
        assert genes["input_handler"]["present"] is True

    def test_particle_genes(self):
        genes = detect_genes(PARTICLE_GAME)
        assert genes["particle_system"]["present"] is True
        assert genes["particle_system"]["strength"] >= 2
        assert genes["render_pipeline"]["present"] is True

    def test_absent_genes(self):
        genes = detect_genes(AUDIO_GAME)
        # Audio game has no canvas/render pipeline
        assert genes["render_pipeline"]["present"] is False
        assert genes["render_pipeline"]["strength"] == 0

    def test_all_gene_types_detected(self):
        """Every gene type in GENE_PATTERNS should be detectable."""
        for gene_name in GENE_PATTERNS:
            genes = detect_genes(PHYSICS_GAME)
            assert gene_name in genes
            assert "present" in genes[gene_name]
            assert "strength" in genes[gene_name]
            assert "weight" in genes[gene_name]


# ---------------------------------------------------------------------------
# Tests: Gene Extraction
# ---------------------------------------------------------------------------
class TestExtractGeneSamples:
    def test_extract_physics(self):
        sample = extract_gene_samples(PHYSICS_GAME, "physics_engine")
        assert sample is not None
        assert len(sample) > 0

    def test_extract_particles(self):
        sample = extract_gene_samples(PARTICLE_GAME, "particle_system")
        assert sample is not None
        assert "Particle" in sample

    def test_extract_absent_gene(self):
        sample = extract_gene_samples(AUDIO_GAME, "particle_system")
        # Audio game has no particle system
        assert sample is None

    def test_max_chars_limit(self):
        sample = extract_gene_samples(PHYSICS_GAME, "render_pipeline", max_chars=100)
        if sample:
            assert len(sample) <= 100

    def test_invalid_gene_name(self):
        sample = extract_gene_samples(PHYSICS_GAME, "nonexistent_gene")
        assert sample is None


# ---------------------------------------------------------------------------
# Tests: Crossover
# ---------------------------------------------------------------------------
class TestCrossover:
    def test_complementary_crossover(self):
        """Crossover should pick the strongest gene from each parent."""
        parents = [
            {
                "file": "physics.html",
                "score": 75,
                "genes": detect_genes(PHYSICS_GAME),
                "content": PHYSICS_GAME,
            },
            {
                "file": "audio.html",
                "score": 60,
                "genes": detect_genes(AUDIO_GAME),
                "content": AUDIO_GAME,
            },
        ]
        genome = crossover(parents)

        # Physics parent should contribute physics_engine
        if "physics_engine" in genome:
            assert genome["physics_engine"]["source_file"] == "physics.html"

        # Audio parent should contribute audio_engine
        if "audio_engine" in genome:
            assert genome["audio_engine"]["source_file"] == "audio.html"

    def test_genome_structure(self):
        parents = [
            {
                "file": "a.html",
                "score": 70,
                "genes": detect_genes(PHYSICS_GAME),
                "content": PHYSICS_GAME,
            },
        ]
        genome = crossover(parents)
        for gene_name, gene_data in genome.items():
            assert "source_file" in gene_data
            assert "source_score" in gene_data
            assert "strength" in gene_data

    def test_three_parents(self):
        parents = [
            {"file": "physics.html", "score": 75, "genes": detect_genes(PHYSICS_GAME), "content": PHYSICS_GAME},
            {"file": "audio.html", "score": 60, "genes": detect_genes(AUDIO_GAME), "content": AUDIO_GAME},
            {"file": "particles.html", "score": 65, "genes": detect_genes(PARTICLE_GAME), "content": PARTICLE_GAME},
        ]
        genome = crossover(parents)
        # Should have genes from multiple sources
        sources = set(g["source_file"] for g in genome.values())
        assert len(sources) >= 2


# ---------------------------------------------------------------------------
# Tests: Lineage Tag Injection
# ---------------------------------------------------------------------------
class TestLineageTags:
    def test_inject_into_head(self):
        html = "<!DOCTYPE html><html><head><title>Test</title></head><body></body></html>"
        result = inject_lineage_tags(html, ["parent-a.html", "parent-b.html"], ["physics", "audio"], "discovery")
        assert 'rappterzoo:parents' in result
        assert 'rappterzoo:genes' in result
        assert 'rappterzoo:experience' in result
        assert 'rappterzoo:author' in result
        assert 'recombination-engine' in result

    def test_inject_without_experience(self):
        html = "<!DOCTYPE html><html><head></head><body></body></html>"
        result = inject_lineage_tags(html, ["p.html"], ["physics"])
        assert 'rappterzoo:experience' not in result
        assert 'rappterzoo:parents' in result

    def test_inject_preserves_content(self):
        html = '<!DOCTYPE html><html><head><title>My Game</title></head><body><p>Content</p></body></html>'
        result = inject_lineage_tags(html, ["p.html"], ["physics"])
        assert "<title>My Game</title>" in result
        assert "<p>Content</p>" in result


# ---------------------------------------------------------------------------
# Tests: Experience Loading
# ---------------------------------------------------------------------------
class TestLoadExperience:
    def test_load_by_id(self, tmp_path):
        palette_path = tmp_path / "palette.json"
        palette_path.write_text(json.dumps({"experiences": [SAMPLE_EXPERIENCE]}))
        with patch("recombine.EXPERIENCE_PALETTE", palette_path):
            exp = load_experience("discovery")
            assert exp is not None
            assert exp["id"] == "discovery"
            assert exp["emotion"] == "The thrill of finding something hidden"

    def test_load_random(self, tmp_path):
        palette_path = tmp_path / "palette.json"
        palette_path.write_text(json.dumps({"experiences": [SAMPLE_EXPERIENCE]}))
        with patch("recombine.EXPERIENCE_PALETTE", palette_path):
            exp = load_experience()
            assert exp is not None

    def test_load_missing_id(self, tmp_path):
        palette_path = tmp_path / "palette.json"
        palette_path.write_text(json.dumps({"experiences": [SAMPLE_EXPERIENCE]}))
        with patch("recombine.EXPERIENCE_PALETTE", palette_path):
            exp = load_experience("nonexistent")
            assert exp is None

    def test_load_no_file(self, tmp_path):
        with patch("recombine.EXPERIENCE_PALETTE", tmp_path / "missing.json"):
            exp = load_experience()
            assert exp is None


# ---------------------------------------------------------------------------
# Tests: Synthesis Prompt
# ---------------------------------------------------------------------------
class TestBuildSynthesisPrompt:
    def test_prompt_includes_genes(self):
        genome = {
            "physics_engine": {
                "source_file": "physics.html",
                "source_score": 75,
                "strength": 3,
                "sample": "const gravity = 0.5;",
            },
        }
        prompt = build_synthesis_prompt(genome)
        assert "physics_engine" in prompt
        assert "physics.html" in prompt
        assert "gravity" in prompt

    def test_prompt_includes_experience(self):
        genome = {"physics_engine": {"source_file": "a.html", "source_score": 70, "strength": 2, "sample": None}}
        prompt = build_synthesis_prompt(genome, SAMPLE_EXPERIENCE)
        assert "EXPERIENCE TARGET" in prompt
        assert "thrill of finding something hidden" in prompt
        assert "Don't put arrows" in prompt

    def test_prompt_includes_category(self):
        genome = {"physics_engine": {"source_file": "a.html", "source_score": 70, "strength": 2, "sample": None}}
        prompt = build_synthesis_prompt(genome, target_category="games_puzzles")
        assert "games_puzzles" in prompt

    def test_prompt_has_rules(self):
        genome = {"physics_engine": {"source_file": "a.html", "source_score": 70, "strength": 2, "sample": None}}
        prompt = build_synthesis_prompt(genome)
        assert "<!DOCTYPE html>" in prompt
        assert "ZERO external dependencies" in prompt
        assert "single self-contained html" in prompt.lower()
