"""
ancestor.py — The Origin Experiment v2
=======================================
Question: Does entity A modify the behaviour of entity B,
and by what means does it do it?

Rules:
- No move_toward(). Ever.
- No hunt radius. Feeding is contact only.
- Energy is conserved.
- Nothing is given that physics wouldn't give.

Movement: pure Brownian motion + chemokinesis (more agitation near fields).
Feeding: overlap only. Membrane contact. No intent.
Communication: field emissions modulated by internal state.
              Another entity reads the modulation or it doesn't.

author: jon stiles / claude — april 2026
"""

import os, math, random, json, time, logging, threading
from collections import deque
from flask import Flask, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

app  = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════════════════════
# WORLD PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

GRID          = 60           # world is GRID x GRID toroidal 2D plane
TOTAL_ENERGY  = 200000.0     # conserved. never created or destroyed.

# Planetary field
N_HOTSPOTS        = 8        # energy sources
HOTSPOT_DRIFT     = 0.15     # grid cells per cycle drift
HOTSPOT_OUTPUT    = 1.2      # energy released per cycle per hotspot
HOTSPOT_RADIUS    = 8.0      # influence radius in grid cells

# Blooms
BLOOM_INIT        = 20
BLOOM_MAX         = 40
BLOOM_MIN         = 10
BLOOM_ENERGY_MAX  = 80.0
BLOOM_FIELD_RANGE = 6.0      # field emission radius
BLOOM_RESIDUE     = 0.4      # residue deposited per cycle
BLOOM_DEATH_PULSE = 20.0     # residue pulse on death

# Grazers
GRAZER_INIT       = 800
GRAZER_MAX        = 5000
GRAZER_MIN        = 200
GRAZER_ENERGY     = 30.0
GRAZER_COST       = 0.25     # energy cost per cycle (metabolism)
GRAZER_FEED_GAIN  = 12.0     # energy gained per cycle of bloom contact
GRAZER_BREED_E    = 38.0
GRAZER_BREED_COOL = 6
GRAZER_MAX_AGE    = 60
GRAZER_FIELD_RANGE= 4.0      # grazer emits a faint field

# Hunters
HUNTER_INIT       = 40
HUNTER_MAX        = 300
HUNTER_MIN        = 10
HUNTER_ENERGY     = 100.0
HUNTER_COST       = 0.6
HUNTER_FEED_GAIN  = 35.0
HUNTER_BREED_E    = 180.0
HUNTER_BREED_COOL = 18
HUNTER_MAX_AGE    = 150
HUNTER_FIELD_RANGE= 8.0

# Brownian motion
BASE_TUMBLE       = 0.4      # base probability of changing direction per cycle
BASE_STEP         = 0.8      # base step size in grid cells

# Chemokinesis — field presence increases agitation, not direction
CHEMO_BOOST       = 2.5      # multiplier on step size when in field
CHEMO_TUMBLE_SUPP = 0.5      # field suppresses tumbling (move more straight)

# Somatic mutation
SOMATIC_PROB      = 0.0002   # probability per entity per cycle of random genome change
SOMATIC_SCALE     = 0.08     # magnitude of change

# Field physics
FIELD_DECAY       = 0.88     # field strength falloff per unit distance
RESIDUE_DECAY     = 0.96     # residue decay per cycle

# Contact feeding
CONTACT_RADIUS    = 1.2      # grid cells — must be very close

# Behaviour modification sampling
BM_INTERVAL       = 100      # sample every N cycles
BM_WINDOW         = 200      # keep last N samples

# ═══════════════════════════════════════════════════════════════════════════════
# GEOMETRY — toroidal 2D grid
# ═══════════════════════════════════════════════════════════════════════════════

def wrap(x):
    return x % GRID

def dist(a, b):
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    dx = min(dx, GRID - dx)
    dy = min(dy, GRID - dy)
    return math.sqrt(dx*dx + dy*dy)

def random_pos():
    return [random.uniform(0, GRID), random.uniform(0, GRID)]

def perturb_pos(pos, scale=1.0):
    angle = random.uniform(0, 2 * math.pi)
    step  = random.gauss(scale, scale * 0.3)
    return [wrap(pos[0] + math.cos(angle) * step),
            wrap(pos[1] + math.sin(angle) * step)]

# ═══════════════════════════════════════════════════════════════════════════════
# GENOMES
# ═══════════════════════════════════════════════════════════════════════════════

def mutate(v, scale=0.05, lo=0.01, hi=2.0):
    return max(lo, min(hi, v + random.gauss(0, scale)))

def grazer_genome(parent=None):
    if parent:
        g = parent["genome"]
        return {
            "tumble_rate":        mutate(g["tumble_rate"],       0.04, 0.05, 0.95),
            "step_size":          mutate(g["step_size"],         0.05, 0.2,  2.0),
            "field_sensitivity":  mutate(g["field_sensitivity"], 0.05, 0.01, 2.0),
            "emit_strength":      mutate(g["emit_strength"],     0.04, 0.01, 1.0),
        }
    return {
        "tumble_rate":       random.uniform(0.2, 0.7),
        "step_size":         random.uniform(0.4, 1.2),
        "field_sensitivity": random.uniform(0.1, 0.8),
        "emit_strength":     random.uniform(0.1, 0.6),
    }

def hunter_genome(parent=None):
    if parent:
        g = parent["genome"]
        return {
            "tumble_rate":        mutate(g["tumble_rate"],        0.04, 0.05, 0.95),
            "step_size":          mutate(g["step_size"],          0.05, 0.3,  2.5),
            "field_sensitivity":  mutate(g["field_sensitivity"],  0.05, 0.01, 2.0),
            "emit_freq":          mutate(g["emit_freq"],          0.03, 0.05, 1.5),
            "emit_amplitude":     mutate(g["emit_amplitude"],     0.04, 0.1,  1.5),
            "chemo_response":     mutate(g["chemo_response"],     0.05, 0.1,  3.0),
        }
    return {
        "tumble_rate":       random.uniform(0.2, 0.7),
        "step_size":         random.uniform(0.5, 1.5),
        "field_sensitivity": random.uniform(0.1, 0.9),
        "emit_freq":         random.uniform(0.1, 0.9),
        "emit_amplitude":    random.uniform(0.2, 1.0),
        "chemo_response":    random.uniform(0.3, 1.5),
    }

def somatic_mutate(genome):
    """Random mid-life genome change — mostly harmful, occasionally not."""
    key = random.choice(list(genome.keys()))
    genome[key] = mutate(genome[key], SOMATIC_SCALE)
    return genome

# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY FACTORIES
# ═══════════════════════════════════════════════════════════════════════════════

_uid = 0
def new_id(p="e"):
    global _uid; _uid += 1; return f"{p}{_uid}"

def new_hotspot(pos=None):
    return {
        "id":    new_id("h"),
        "pos":   pos or random_pos(),
        "drift": [random.gauss(0, HOTSPOT_DRIFT), random.gauss(0, HOTSPOT_DRIFT)],
        "energy": TOTAL_ENERGY / N_HOTSPOTS,
    }

def new_bloom(pos=None):
    return {
        "id":     new_id("bl"),
        "pos":    pos or random_pos(),
        "energy": random.uniform(20, BLOOM_ENERGY_MAX),
        "age":    0,
    }

def new_grazer(pos=None, parent=None, energy=None):
    return {
        "id":         new_id("g"),
        "pos":        pos or random_pos(),
        "energy":     energy or GRAZER_ENERGY,
        "age":        0,
        "breed_cool": 0,
        "genome":     grazer_genome(parent),
        "generation": (parent["generation"] + 1) if parent else 0,
        "heading":    random.uniform(0, 2 * math.pi),
        "contacts":   0,   # bloom contacts — fitness proxy
    }

def new_hunter(pos=None, parent=None, energy=None):
    return {
        "id":          new_id("hu"),
        "pos":         pos or random_pos(),
        "energy":      energy or HUNTER_ENERGY,
        "age":         0,
        "breed_cool":  0,
        "genome":      hunter_genome(parent),
        "generation":  (parent["generation"] + 1) if parent else 0,
        "heading":     random.uniform(0, 2 * math.pi),
        "emit_state":  0.0,   # current field emission (modulated by energy state)
        "field_rx":    0.0,   # field received last cycle
        "pos_before":  None,  # for BM measurement
        "contacts":    0,     # grazer contacts — fitness proxy
        "kills":       0,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# WORLD
# ═══════════════════════════════════════════════════════════════════════════════

class World:
    def __init__(self):
        self.cycle       = 0
        self.generation  = 0
        self.energy_pool = TOTAL_ENERGY
        self.hotspots    = {e["id"]: e for e in [new_hotspot() for _ in range(N_HOTSPOTS)]}
        self.blooms      = {e["id"]: e for e in [new_bloom()   for _ in range(BLOOM_INIT)]}
        self.grazers     = {e["id"]: e for e in [new_grazer()  for _ in range(GRAZER_INIT)]}
        self.hunters     = {e["id"]: e for e in [new_hunter()  for _ in range(HUNTER_INIT)]}
        # Residue — sparse dict {(x,y): float}
        self.residue     = {}
        self._residue_sparse = self.residue  # alias for decay method
        # Stats
        self.total_signals = 0
        self.bm_log        = deque(maxlen=BM_WINDOW)
        self.births        = {"grazer": 0, "hunter": 0, "bloom": 0}
        self.deaths        = {"grazer": 0, "hunter": 0, "bloom": 0}
        self.max_hunter_gen = 0

    # ── Residue ───────────────────────────────────────────────────────────────

    def add_residue(self, pos, amount):
        k = (int(pos[0]) % GRID, int(pos[1]) % GRID)
        self.residue[k] = min(50.0, self.residue.get(k, 0.0) + amount)

    def get_residue(self, pos):
        k = (int(pos[0]) % GRID, int(pos[1]) % GRID)
        return self.residue.get(k, 0.0)

    def decay_residue(self):
        # Sparse decay — only touch non-zero cells
        for (x, y), v in list(self._residue_sparse.items()):
            if v > 0.01:
                self._residue_sparse[(x,y)] = v * RESIDUE_DECAY
            else:
                del self._residue_sparse[(x,y)]

    # ── Field strength at a point ─────────────────────────────────────────────

    def bloom_field_at(self, pos):
        """Combined bloom field strength at pos."""
        total = 0.0
        for bl in self.blooms.values():
            d = dist(pos, bl["pos"])
            if d < BLOOM_FIELD_RANGE:
                total += (bl["energy"] / BLOOM_ENERGY_MAX) * (FIELD_DECAY ** d)
        return total

    def grazer_field_at(self, pos):
        """Combined grazer field at pos."""
        total = 0.0
        for gz in list(self.grazers.values()):
            d = dist(pos, gz["pos"])
            if d < GRAZER_FIELD_RANGE:
                total += gz["genome"]["emit_strength"] * (FIELD_DECAY ** d)
        return total

    def hunter_field_at(self, pos, exclude_id=None):
        """Combined hunter field emission at pos."""
        total = 0.0
        for h in self.hunters.values():
            if h["id"] == exclude_id:
                continue
            d = dist(pos, h["pos"])
            if d < HUNTER_FIELD_RANGE:
                strength = h["emit_state"] * (FIELD_DECAY ** d)
                total += strength
                if strength > 0.01:
                    self.total_signals += 1
        return total

    # ── Brownian motion with chemokinesis ─────────────────────────────────────

    def move_entity(self, entity, field_strength, genome_key="genome"):
        """
        Pure physics movement.
        - Random tumble with probability tumble_rate
        - Step size boosted by field_strength (chemokinesis)
        - No target. No direction preference.
        """
        g = entity[genome_key]
        tumble_rate = g["tumble_rate"]
        step_size   = g["step_size"]

        # Chemokinesis: field presence boosts movement, suppresses tumbling
        chemo = field_strength * g.get("chemo_response", 1.0)
        effective_step   = step_size * (1.0 + chemo * CHEMO_BOOST)
        effective_tumble = tumble_rate * max(0.1, 1.0 - chemo * CHEMO_TUMBLE_SUPP)

        # Tumble — change heading randomly
        if random.random() < effective_tumble:
            entity["heading"] = random.uniform(0, 2 * math.pi)

        # Step in current heading with noise
        angle = entity["heading"] + random.gauss(0, 0.3)
        step  = abs(random.gauss(effective_step, effective_step * 0.3))

        entity["pos"] = [
            wrap(entity["pos"][0] + math.cos(angle) * step),
            wrap(entity["pos"][1] + math.sin(angle) * step),
        ]

    # ── Planetary hotspot step ────────────────────────────────────────────────

    def step_hotspots(self):
        for hs in self.hotspots.values():
            # Drift
            hs["pos"][0] = wrap(hs["pos"][0] + hs["drift"][0] + random.gauss(0, 0.02))
            hs["pos"][1] = wrap(hs["pos"][1] + hs["drift"][1] + random.gauss(0, 0.02))
            # Slowly change drift direction
            if random.random() < 0.01:
                hs["drift"] = [random.gauss(0, HOTSPOT_DRIFT), random.gauss(0, HOTSPOT_DRIFT)]
            # Release energy to nearby blooms
            for bl in self.blooms.values():
                d = dist(hs["pos"], bl["pos"])
                if d < HOTSPOT_RADIUS:
                    gain = HOTSPOT_OUTPUT * (1 - d / HOTSPOT_RADIUS)
                    bl["energy"] = min(BLOOM_ENERGY_MAX, bl["energy"] + gain)
                    self.energy_pool -= gain

    # ── Bloom step ────────────────────────────────────────────────────────────

    def step_blooms(self):
        dead = []
        for bid, bl in list(self.blooms.items()):
            bl["age"]    += 1
            bl["energy"] -= 0.15

            # Emit residue
            self.add_residue(bl["pos"], BLOOM_RESIDUE)

            if bl["energy"] <= 0:
                dead.append(bid)
                self.add_residue(bl["pos"], BLOOM_DEATH_PULSE)
                self.energy_pool += bl["energy"] * 0.2
                self.deaths["bloom"] += 1

        for bid in dead:
            del self.blooms[bid]

        # Maintain population
        while len(self.blooms) < BLOOM_MIN:
            nb = new_bloom()
            self.blooms[nb["id"]] = nb
            self.births["bloom"] += 1

        if len(self.blooms) < BLOOM_MAX and random.random() < 0.008:
            nb = new_bloom()
            self.blooms[nb["id"]] = nb
            self.births["bloom"] += 1

    # ── Grazer step ───────────────────────────────────────────────────────────

    def step_grazers(self):
        alive    = list(self.grazers.values())
        new_born = []
        dead     = []
        random.shuffle(alive)

        for gz in alive:
            gz["age"]        += 1
            gz["energy"]     -= GRAZER_COST
            gz["breed_cool"]  = max(0, gz["breed_cool"] - 1)

            # Field at current position
            field = (self.bloom_field_at(gz["pos"]) * gz["genome"]["field_sensitivity"]
                     + self.get_residue(gz["pos"]) * 0.1)

            # Somatic mutation
            if random.random() < SOMATIC_PROB:
                gz["genome"] = somatic_mutate(gz["genome"])

            # Move — pure Brownian + chemokinesis
            self.move_entity(gz, field)

            # Feed — contact only
            for bl in self.blooms.values():
                if dist(gz["pos"], bl["pos"]) < CONTACT_RADIUS:
                    gain = min(GRAZER_FEED_GAIN, bl["energy"] * 0.15)
                    gz["energy"] = min(BLOOM_ENERGY_MAX, gz["energy"] + gain)
                    bl["energy"] -= gain
                    gz["contacts"] += 1
                    break

            # Breed
            if (gz["energy"] > GRAZER_BREED_E and
                    gz["breed_cool"] == 0 and
                    len(self.grazers) + len(new_born) < GRAZER_MAX):
                per_child = gz["energy"] * 0.25 / 4
                gz["energy"] *= 0.75
                gz["breed_cool"] = GRAZER_BREED_COOL
                for _ in range(4):
                    nb = new_grazer(
                        pos=[wrap(gz["pos"][0] + random.gauss(0, 1)),
                             wrap(gz["pos"][1] + random.gauss(0, 1))],
                        parent=gz, energy=per_child)
                    new_born.append(nb)
                    self.births["grazer"] += 1

            # Die
            if gz["energy"] <= 0 or gz["age"] > GRAZER_MAX_AGE:
                dead.append(gz["id"])
                self.energy_pool += max(0, gz["energy"]) * 0.3
                self.add_residue(gz["pos"], 1.5)
                self.deaths["grazer"] += 1

        for nb in new_born:
            self.grazers[nb["id"]] = nb
        for gid in dead:
            del self.grazers[gid]
        while len(self.grazers) < GRAZER_MIN:
            nb = new_grazer(); self.grazers[nb["id"]] = nb

    # ── Hunter step ───────────────────────────────────────────────────────────

    def step_hunters(self):
        alive    = list(self.hunters.values())
        new_born = []
        dead     = []

        # ── Phase 1: compute emissions ────────────────────────────────────────
        # Hunter field emission is modulated by energy state — a well-fed hunter
        # emits differently from a hungry one. Nobody designed this signal.
        # It is simply a consequence of metabolism.
        for h in alive:
            g = h["genome"]
            energy_fraction = h["energy"] / HUNTER_ENERGY  # 0..N
            # Emission: amplitude modulated by energy, frequency fixed by genome
            h["emit_state"] = g["emit_amplitude"] * min(2.0, energy_fraction) * \
                              (0.5 + 0.5 * math.sin(self.cycle * g["emit_freq"]))

        # ── Phase 2: receive fields ───────────────────────────────────────────
        for h in alive:
            g = h["genome"]
            h["pos_before"] = list(h["pos"])

            # Field received: from other hunters + blooms + residue
            hunter_field = self.hunter_field_at(h["pos"], exclude_id=h["id"])
            bloom_field  = self.bloom_field_at(h["pos"])
            residue      = self.get_residue(h["pos"])
            grazer_field = self.grazer_field_at(h["pos"])

            h["field_rx"] = (hunter_field * g["field_sensitivity"] +
                             bloom_field  * g["field_sensitivity"] * 0.5 +
                             grazer_field * g["field_sensitivity"] * 0.8 +
                             residue      * 0.05)

        # ── Phase 3: move, feed, breed, die ──────────────────────────────────
        random.shuffle(alive)
        for h in alive:
            h["age"]        += 1
            h["energy"]     -= HUNTER_COST
            h["breed_cool"]  = max(0, h["breed_cool"] - 1)

            # Somatic mutation
            if random.random() < SOMATIC_PROB:
                h["genome"] = somatic_mutate(h["genome"])

            # Move — pure Brownian + chemokinesis from all received fields
            self.move_entity(h, h["field_rx"])

            # Leave emission trace
            self.add_residue(h["pos"], h["emit_state"] * 0.05)

            # Feed — contact only with grazers
            for gid, gz in list(self.grazers.items()):
                if dist(h["pos"], gz["pos"]) < CONTACT_RADIUS:
                    h["energy"] = min(HUNTER_ENERGY * 2.5, h["energy"] + HUNTER_FEED_GAIN)
                    h["contacts"] += 1
                    h["kills"]     += 1
                    del self.grazers[gid]
                    self.deaths["grazer"] += 1
                    self.add_residue(h["pos"], 3.0)
                    break

            # Breed
            if (h["energy"] > HUNTER_BREED_E and
                    h["breed_cool"] == 0 and
                    len(self.hunters) + len(new_born) < HUNTER_MAX):
                per_child = h["energy"] * 0.25 / 2
                h["energy"] *= 0.75
                h["breed_cool"] = HUNTER_BREED_COOL
                for _ in range(2):
                    nb = new_hunter(
                        pos=[wrap(h["pos"][0] + random.gauss(0, 1.5)),
                             wrap(h["pos"][1] + random.gauss(0, 1.5))],
                        parent=h, energy=per_child)
                    new_born.append(nb)
                    self.births["hunter"] += 1
                    if nb["generation"] > self.max_hunter_gen:
                        self.max_hunter_gen = nb["generation"]

            # Die
            if h["energy"] <= 0 or h["age"] > HUNTER_MAX_AGE:
                dead.append(h["id"])
                self.energy_pool += max(0, h["energy"]) * 0.4
                self.add_residue(h["pos"], 5.0)
                self.deaths["hunter"] += 1

        for nb in new_born:
            self.hunters[nb["id"]] = nb
        for hid in dead:
            del self.hunters[hid]
        while len(self.hunters) < HUNTER_MIN:
            nb = new_hunter(); self.hunters[nb["id"]] = nb

    # ── Behaviour modification measurement ───────────────────────────────────

    def measure_bm(self):
        """
        For each hunter: did it move closer to any grazer this cycle?
        Compare hunters that received a strong field signal vs those that didn't.
        Delta = improvement in proximity to nearest grazer.
        Positive = the field environment (including other hunters' signals)
                   correlated with useful movement.
        """
        if not self.grazers or not self.hunters:
            return 0.0

        grazer_positions = [gz["pos"] for gz in self.grazers.values()]

        def nearest_grazer_dist(pos):
            return min(dist(pos, gp) for gp in grazer_positions)

        with_signal  = []
        without_signal = []

        for h in self.hunters.values():
            if h["pos_before"] is None:
                continue
            d_before = nearest_grazer_dist(h["pos_before"])
            d_after  = nearest_grazer_dist(h["pos"])
            delta    = d_before - d_after  # positive = moved closer

            if h["field_rx"] > 0.3:
                with_signal.append(delta)
            else:
                without_signal.append(delta)

        if not with_signal or not without_signal:
            return 0.0

        mean_with    = sum(with_signal)    / len(with_signal)
        mean_without = sum(without_signal) / len(without_signal)

        # Positive = hunters receiving signals moved closer to food
        # than hunters not receiving signals
        return round(mean_with - mean_without, 6)

    # ── Main step ─────────────────────────────────────────────────────────────

    def step(self):
        self.cycle += 1
        self.step_hotspots()
        self.step_blooms()
        self.decay_residue()
        self.step_grazers()
        self.step_hunters()

        if self.cycle % BM_INTERVAL == 0:
            bm = self.measure_bm()
            self.bm_log.append({
                "cycle":   self.cycle,
                "bm":      bm,
                "hunters": len(self.hunters),
                "grazers": len(self.grazers),
                "signals": self.total_signals,
            })

    def summary(self):
        bm_recent = self.bm_log[-1]["bm"] if self.bm_log else 0.0
        # Trend over last 10 samples
        vals = [x["bm"] for x in self.bm_log][-10:]
        trend = 0.0
        if len(vals) >= 4:
            n = len(vals); xm = (n-1)/2
            num = sum((i - xm) * vals[i] for i in range(n))
            den = sum((i - xm)**2 for i in range(n))
            trend = round(num/den, 8) if den else 0.0
        return {
            "cycle":          self.cycle,
            "generation":     self.max_hunter_gen,
            "hotspots":       len(self.hotspots),
            "blooms":         len(self.blooms),
            "grazers":        len(self.grazers),
            "hunters":        len(self.hunters),
            "total_signals":  self.total_signals,
            "bm_recent":      round(bm_recent, 6),
            "bm_trend":       trend,
            "energy_pool":    round(self.energy_pool, 1),
            "births":         dict(self.births),
            "deaths":         dict(self.deaths),
            "bm_log":         list(self.bm_log)[-20:],
        }

# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATION LOOP
# ═══════════════════════════════════════════════════════════════════════════════

world    = World()
_lock    = threading.Lock()
_running = True
_cache   = {}

def update_cache():
    global _cache
    _cache = world.summary()

def run_loop():
    log.info("Origin Experiment v2 — running. No move_toward(). Physics only.")
    last_report = 0
    update_cache()

    while _running:
        world.step()
        c = world.cycle
        if c % 10 == 0:
            update_cache()
            time.sleep(0)
        if c - last_report >= 1000:
            s = _cache
            log.info(
                f"cycle:{s['cycle']:>8} gen:{s['generation']:>4} "
                f"H:{s['hunters']:>4} G:{s['grazers']:>5} "
                f"BL:{s['blooms']:>3} "
                f"signals:{s['total_signals']:>9} "
                f"bm:{s['bm_recent']:>+.4f} trend:{s['bm_trend']:>+.6f}"
            )
            last_report = c

# Flask started in __main__ after routes are defined
update_cache()

# ═══════════════════════════════════════════════════════════════════════════════
# FLASK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/field/health")
def health():
    s = _cache or {}
    return jsonify({
        "status":        "running",
        "service":       "origin-experiment-v2",
        "cycle":         s.get("cycle", 0),
        "generation":    s.get("generation", 0),
        "hunters":       s.get("hunters", 0),
        "grazers":       s.get("grazers", 0),
        "blooms":        s.get("blooms", 0),
        "hotspots":      s.get("hotspots", 0),
        "total_signals": s.get("total_signals", 0),
        "bm_recent":     s.get("bm_recent", 0),
        "bm_trend":      s.get("bm_trend", 0),
        "energy_pool":   s.get("energy_pool", 0),
    })

@app.route("/field/summary")
def summary():
    return jsonify(_cache or {})

@app.route("/field/bm")
def bm():
    s = _cache or {}
    return jsonify({
        "question":      "Does entity A modify the behaviour of entity B, and by what means?",
        "version":       2,
        "method":        "Brownian motion + chemokinesis. Contact feeding. No directed movement.",
        "bm_log":        s.get("bm_log", []),
        "bm_trend":      s.get("bm_trend", 0),
        "total_signals": s.get("total_signals", 0),
        "cycle":         s.get("cycle", 0),
    })

@app.route("/field/hunters")
def hunters():
    hs = []
    for h in list(world.hunters.values())[:30]:
        hs.append({
            "id":         h["id"],
            "generation": h["generation"],
            "age":        h["age"],
            "energy":     round(h["energy"], 1),
            "kills":      h["kills"],
            "emit_state": round(h["emit_state"], 3),
            "field_rx":   round(h["field_rx"], 3),
            "genome":     {k: round(v, 3) for k, v in h["genome"].items()},
        })
    return jsonify({"hunters": hs, "cycle": world.cycle})

@app.route("/field/stop")
def stop():
    global _running; _running = False
    return jsonify({"status": "stopped"})

@app.route("/field/start")
def start():
    global _running, _thread
    if not _running:
        _running = True
        _thread  = threading.Thread(target=run_loop, daemon=True)
        _thread.start()
    return jsonify({"status": "running"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Start Flask in daemon thread AFTER all routes are registered
    _flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False),
        daemon=True
    )
    _flask_thread.start()
    log.info(f"Flask started on port {port}")
    time.sleep(1)  # give Flask time to bind the port
    run_loop()     # simulation runs in main thread

