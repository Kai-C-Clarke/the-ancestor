"""
ancestor.py — The Origin Experiment
=====================================
Question: Does entity A modify the behaviour of entity B,
and by what means does it do it?

Stack (bottom up):
  Planetary energy field  →  Vents  →  Blooms  →  Grazers  →  Hunters

Energy is conserved. Nothing is designed above the planetary layer.
Communication — if it emerges — emerges because physics made it necessary.

author: jon stiles / claude
"""

import os
import math
import time
import random
import json
import threading
import logging
from collections import deque
from flask import Flask, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ── Constants ────────────────────────────────────────────────────────────────

# World
WORLD_RADIUS        = 1.0       # unit sphere
DT                  = 1         # one cycle = one tick

# Energy budget — conserved across the system
TOTAL_ENERGY        = 50000.0

# Planetary field
N_VENTS             = 6         # active vents at any time
VENT_MIGRATE_RATE   = 0.0002    # radians/cycle — slow geological drift
VENT_ENERGY_OUTPUT  = 0.8       # energy released per cycle per vent
VENT_LIFETIME       = 8000      # cycles before vent dies
VENT_SPAWN_INTERVAL = 1200      # cycles between new vent births

# Residual field decay
RESIDUE_DECAY       = 0.97      # fraction remaining each cycle (1.0 = permanent)
RESIDUE_GRID        = 80        # resolution of residue field (80x80 grid on sphere)

# Blooms
N_BLOOMS_INIT       = 8
BLOOM_ENERGY_START  = 60.0
BLOOM_ENERGY_MAX    = 120.0
BLOOM_LIFETIME      = 600
BLOOM_EMIT_BASE     = 0.5       # baseline emission frequency
BLOOM_RESIDUE       = 8.0       # residue left per cycle
BLOOM_DEATH_RESIDUE = 30.0      # pulse on death (marine snow)
MAX_BLOOMS          = 20
MIN_BLOOMS          = 4

# Grazers
N_GRAZERS_INIT      = 400
GRAZER_ENERGY_START = 25.0
GRAZER_ENERGY_MAX   = 60.0
GRAZER_DEPLETE      = 0.3
GRAZER_MOVE_COST    = 0.1
GRAZER_BREED_THRESH = 35.0
GRAZER_BREED_COOL   = 5
GRAZER_MAX_AGE      = 80
GRAZER_FOOD_GAIN    = 15.0
GRAZER_SPAWN_COUNT  = 6
MAX_GRAZERS         = 8000
MIN_GRAZERS         = 200

# Hunters
N_HUNTERS_INIT      = 20
HUNTER_ENERGY_START = 80.0
HUNTER_ENERGY_MAX   = 200.0
HUNTER_DEPLETE      = 0.5
HUNTER_MOVE_COST    = 0.2
HUNTER_BREED_THRESH = 150.0
HUNTER_BREED_COOL   = 20
HUNTER_MAX_AGE      = 200
HUNTER_FOOD_GAIN    = 40.0
HUNTER_SPAWN_COUNT  = 2
HUNTER_HUNT_RADIUS  = 0.06
MAX_HUNTERS         = 120
MIN_HUNTERS         = 4

# Field physics
FIELD_RANGE         = 0.25      # max radius of field influence
FIELD_DECAY         = 0.85      # field strength falls off with distance
EMIT_MODULATION     = 0.3       # how much proximity to bloom modulates hunter emission

# Behaviour modification tracking
BM_WINDOW           = 500       # cycles to measure behaviour modification over
BM_SAMPLE_INTERVAL  = 50        # sample every N cycles

# ── Geometry ─────────────────────────────────────────────────────────────────

def angular_distance(a, b):
    """Great circle distance between two (theta, phi) positions."""
    t1, p1 = a
    t2, p2 = b
    x1 = math.sin(t1) * math.cos(p1)
    y1 = math.sin(t1) * math.sin(p1)
    z1 = math.cos(t1)
    x2 = math.sin(t2) * math.cos(p2)
    y2 = math.sin(t2) * math.sin(p2)
    z2 = math.cos(t2)
    dot = max(-1.0, min(1.0, x1*x2 + y1*y2 + z1*z2))
    return math.acos(dot)

def move_toward(pos, target, step):
    """Move pos toward target by step radians."""
    dist = angular_distance(pos, target)
    if dist < 0.001:
        return pos
    t = min(step / dist, 1.0)
    t1, p1 = pos
    t2, p2 = target
    theta = t1 + t * (t2 - t1)
    # Handle phi wrap
    dp = (p2 - p1 + math.pi) % (2 * math.pi) - math.pi
    phi = p1 + t * dp
    return (theta % math.pi, phi % (2 * math.pi))

def random_pos():
    theta = math.acos(1 - 2 * random.random())
    phi   = random.uniform(0, 2 * math.pi)
    return (theta, phi)

def perturb(pos, scale=0.05):
    t, p = pos
    return (
        max(0.01, min(math.pi - 0.01, t + random.gauss(0, scale))),
        (p + random.gauss(0, scale)) % (2 * math.pi)
    )

def grid_key(pos):
    """Map (theta, phi) to a residue grid cell."""
    t, p = pos
    row = int(t / math.pi * RESIDUE_GRID)
    col = int(p / (2 * math.pi) * RESIDUE_GRID)
    return (min(row, RESIDUE_GRID-1), min(col, RESIDUE_GRID-1))

# ── Genomes ───────────────────────────────────────────────────────────────────

def mutate(val, scale=0.05, lo=0.01, hi=1.0):
    return max(lo, min(hi, val + random.gauss(0, scale)))

def bloom_genome(parent=None):
    if parent:
        g = parent["genome"]
        return {
            "emit_freq":       mutate(g["emit_freq"],      0.03, 0.05, 1.0),
            "emit_amplitude":  mutate(g["emit_amplitude"], 0.05, 0.1,  1.0),
            "residue_strength":mutate(g["residue_strength"],0.05,0.1,  1.0),
        }
    return {
        "emit_freq":        random.uniform(0.3, 0.7),
        "emit_amplitude":   random.uniform(0.4, 0.8),
        "residue_strength": random.uniform(0.3, 0.7),
    }

def grazer_genome(parent=None):
    if parent:
        g = parent["genome"]
        return {
            "bloom_sensitivity":   mutate(g["bloom_sensitivity"],   0.05),
            "residue_sensitivity": mutate(g["residue_sensitivity"], 0.05),
            "speed":               mutate(g["speed"],               0.003, 0.005, 0.08),
            "emit_suppression":    mutate(g["emit_suppression"],    0.05),
        }
    return {
        "bloom_sensitivity":   random.uniform(0.3, 0.8),
        "residue_sensitivity": random.uniform(0.1, 0.5),
        "speed":               random.uniform(0.01, 0.04),
        "emit_suppression":    random.uniform(0.1, 0.5),
    }

def hunter_genome(parent=None):
    if parent:
        g = parent["genome"]
        return {
            "emit_freq":           mutate(g["emit_freq"],           0.03, 0.05, 1.5),
            "emit_amplitude":      mutate(g["emit_amplitude"],      0.05, 0.1,  1.0),
            "field_sensitivity":   mutate(g["field_sensitivity"],   0.05),
            "residue_sensitivity": mutate(g["residue_sensitivity"], 0.05),
            "memory_length":       max(2, int(g["memory_length"] + random.randint(-1, 1))),
            "response_threshold":  mutate(g["response_threshold"],  0.05, 0.05, 0.9),
            "speed":               mutate(g["speed"],               0.003, 0.01, 0.1),
        }
    return {
        "emit_freq":           random.uniform(0.2, 0.8),
        "emit_amplitude":      random.uniform(0.3, 0.8),
        "field_sensitivity":   random.uniform(0.2, 0.8),
        "residue_sensitivity": random.uniform(0.1, 0.6),
        "memory_length":       random.randint(3, 12),
        "response_threshold":  random.uniform(0.1, 0.5),
        "speed":               random.uniform(0.02, 0.06),
    }

# ── Entity factories ──────────────────────────────────────────────────────────

_uid = 0
def new_id(prefix="e"):
    global _uid
    _uid += 1
    return f"{prefix}{_uid}"

def new_vent(pos=None):
    return {
        "id":       new_id("v"),
        "pos":      pos or random_pos(),
        "energy":   TOTAL_ENERGY / N_VENTS,
        "age":      0,
        "lifetime": VENT_LIFETIME + random.randint(-1000, 1000),
        "drift":    (random.gauss(0, VENT_MIGRATE_RATE),
                     random.gauss(0, VENT_MIGRATE_RATE)),
    }

def new_bloom(pos=None, parent=None):
    return {
        "id":     new_id("bl"),
        "pos":    pos or random_pos(),
        "energy": BLOOM_ENERGY_START,
        "age":    0,
        "genome": bloom_genome(parent),
    }

def new_grazer(pos=None, parent=None, energy=None):
    return {
        "id":          new_id("g"),
        "pos":         pos or random_pos(),
        "energy":      energy or GRAZER_ENERGY_START,
        "age":         0,
        "breed_cool":  0,
        "genome":      grazer_genome(parent),
        "generation":  (parent["generation"] + 1) if parent else 0,
    }

def new_hunter(pos=None, parent=None, energy=None):
    return {
        "id":              new_id("h"),
        "pos":             pos or random_pos(),
        "energy":          energy or HUNTER_ENERGY_START,
        "age":             0,
        "breed_cool":      0,
        "genome":          hunter_genome(parent),
        "generation":      (parent["generation"] + 1) if parent else 0,
        # field state
        "emit_state":      0.0,    # current emission (modulated by environment)
        "field_received":  0.0,    # field received from other hunters last cycle
        # behaviour modification tracking
        "pos_before":      None,   # position before receiving field signal
        "signal_received": False,
        # memory: recent bloom/food positions
        "memory":          deque(maxlen=12),
        # stats
        "kills":           0,
        "bloom_hits":      0,
    }

# ── World state ───────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.cycle          = 0
        self.generation     = 0   # hunter generation counter
        self.vents          = {e["id"]: e for e in [new_vent() for _ in range(N_VENTS)]}
        self.blooms         = {e["id"]: e for e in [new_bloom() for _ in range(N_BLOOMS_INIT)]}
        self.grazers        = {e["id"]: e for e in [new_grazer() for _ in range(N_GRAZERS_INIT)]}
        self.hunters        = {e["id"]: e for e in [new_hunter() for _ in range(N_HUNTERS_INIT)]}
        self.residue        = {}   # grid_key -> float (energy residue)
        self.energy_pool    = TOTAL_ENERGY  # planetary reserve
        self.next_vent_spawn = VENT_SPAWN_INTERVAL
        self.births         = {"bloom": 0, "grazer": 0, "hunter": 0}
        self.deaths         = {"bloom": 0, "grazer": 0, "hunter": 0}
        self.total_signals  = 0
        # behaviour modification log
        self.bm_log         = deque(maxlen=BM_WINDOW // BM_SAMPLE_INTERVAL)
        self.hunter_gen_stats = []  # per-generation summary

    # ── Residue field ─────────────────────────────────────────────────────────

    def add_residue(self, pos, amount):
        k = grid_key(pos)
        self.residue[k] = self.residue.get(k, 0.0) + amount

    def get_residue(self, pos):
        return self.residue.get(grid_key(pos), 0.0)

    def decay_residue(self):
        dead = [k for k, v in self.residue.items() if v < 0.01]
        for k in dead:
            del self.residue[k]
        for k in self.residue:
            self.residue[k] *= RESIDUE_DECAY

    # ── Planetary field step ──────────────────────────────────────────────────

    def step_vents(self):
        # Drift vents
        for v in self.vents.values():
            dt, dp = v["drift"]
            t, p = v["pos"]
            v["pos"] = (
                max(0.01, min(math.pi - 0.01, t + dt + random.gauss(0, 0.0001))),
                (p + dp + random.gauss(0, 0.0001)) % (2 * math.pi)
            )
            v["age"] += 1
            # Release energy to nearby blooms
            for bl in self.blooms.values():
                d = angular_distance(v["pos"], bl["pos"])
                if d < 0.15:
                    gain = VENT_ENERGY_OUTPUT * (1 - d / 0.15)
                    bl["energy"] = min(BLOOM_ENERGY_MAX, bl["energy"] + gain)
                    self.energy_pool -= gain

        # Kill old vents — return energy to pool
        dead = [vid for vid, v in self.vents.items() if v["age"] > v["lifetime"]]
        for vid in dead:
            self.energy_pool += self.vents[vid]["energy"] * 0.5
            del self.vents[vid]

        # Spawn new vents
        self.next_vent_spawn -= 1
        if self.next_vent_spawn <= 0 and len(self.vents) < N_VENTS:
            self.vents[new_id("v")] = new_vent()
            self.next_vent_spawn = VENT_SPAWN_INTERVAL

    # ── Bloom step ────────────────────────────────────────────────────────────

    def step_blooms(self):
        dead = []
        for bid, bl in self.blooms.items():
            bl["age"]    += 1
            bl["energy"] -= 0.2  # baseline metabolic cost

            # Drift toward nearest vent (blooms follow energy gradient)
            nearest_vent = min(
                self.vents.values(),
                key=lambda v: angular_distance(v["pos"], bl["pos"]),
                default=None
            )
            if nearest_vent:
                bl["pos"] = move_toward(
                    bl["pos"], nearest_vent["pos"],
                    0.003 + random.gauss(0, 0.001)
                )

            # Emit residue
            g = bl["genome"]
            self.add_residue(bl["pos"], g["residue_strength"] * g["emit_amplitude"])

            if bl["energy"] <= 0 or bl["age"] > BLOOM_LIFETIME:
                dead.append(bid)
                # Marine snow — death pulse
                self.add_residue(bl["pos"], BLOOM_DEATH_RESIDUE * g["residue_strength"])
                self.energy_pool += bl["energy"] * 0.3
                self.deaths["bloom"] += 1

        for bid in dead:
            del self.blooms[bid]

        # Maintain minimum blooms
        if len(self.blooms) < MIN_BLOOMS:
            nb = new_bloom()
            self.blooms[nb["id"]] = nb
            self.births["bloom"] += 1
        elif len(self.blooms) < MAX_BLOOMS and random.random() < 0.005:
            nb = new_bloom()
            self.blooms[nb["id"]] = nb
            self.births["bloom"] += 1

    # ── Grazer step ───────────────────────────────────────────────────────────

    def step_grazers(self):
        alive = list(self.grazers.values())
        random.shuffle(alive)
        new_born = []
        dead = []

        for gz in alive:
            gz["age"]        += 1
            gz["energy"]     -= GRAZER_DEPLETE
            gz["breed_cool"]  = max(0, gz["breed_cool"] - 1)
            g = gz["genome"]

            # Find best target: bloom field or residue trail
            best_target = None
            best_score  = -1

            for bl in self.blooms.values():
                d = angular_distance(gz["pos"], bl["pos"])
                if d < FIELD_RANGE:
                    score = (g["bloom_sensitivity"] *
                             bl["genome"]["emit_amplitude"] *
                             (1 - d / FIELD_RANGE))
                    if score > best_score:
                        best_score  = score
                        best_target = bl["pos"]

            # Residue sensitivity
            res = self.get_residue(gz["pos"])
            if res * g["residue_sensitivity"] > best_score:
                # Move toward highest residue neighbour
                best_target = perturb(gz["pos"], 0.08)

            if best_target:
                gz["pos"] = move_toward(gz["pos"], best_target,
                                        g["speed"] - GRAZER_MOVE_COST * 0.01)
            else:
                gz["pos"] = perturb(gz["pos"], g["speed"])

            # Feed on bloom
            for bl in self.blooms.values():
                d = angular_distance(gz["pos"], bl["pos"])
                if d < 0.05:
                    gain = min(GRAZER_FOOD_GAIN, bl["energy"] * 0.1)
                    gz["energy"] = min(GRAZER_ENERGY_MAX, gz["energy"] + gain)
                    bl["energy"] -= gain
                    break

            # Breed
            if (gz["energy"] > GRAZER_BREED_THRESH and
                    gz["breed_cool"] == 0 and
                    len(self.grazers) + len(new_born) < MAX_GRAZERS):
                per_child = gz["energy"] * 0.3 / GRAZER_SPAWN_COUNT
                gz["energy"] *= 0.7
                gz["breed_cool"] = GRAZER_BREED_COOL
                for _ in range(GRAZER_SPAWN_COUNT):
                    nb = new_grazer(
                        pos=perturb(gz["pos"], 0.03),
                        parent=gz,
                        energy=per_child
                    )
                    new_born.append(nb)
                    self.births["grazer"] += 1

            # Die
            if gz["energy"] <= 0 or gz["age"] > GRAZER_MAX_AGE:
                dead.append(gz["id"])
                self.energy_pool += gz["energy"] * 0.2
                self.deaths["grazer"] += 1
                self.add_residue(gz["pos"], 2.0)  # death residue

        for gz in new_born:
            self.grazers[gz["id"]] = gz
        for gid in dead:
            del self.grazers[gid]

        # Maintain minimum
        while len(self.grazers) < MIN_GRAZERS:
            nb = new_grazer()
            self.grazers[nb["id"]] = nb

    # ── Hunter step ───────────────────────────────────────────────────────────

    def step_hunters(self):
        alive   = list(self.hunters.values())
        new_born = []
        dead    = []

        # ── Phase 1: compute field emissions ─────────────────────────────────
        # Each hunter's emission is modulated by proximity to blooms/grazers
        for h in alive:
            g      = h["genome"]
            base   = g["emit_amplitude"]
            # Bloom proximity modulates emission
            bloom_mod = 0.0
            for bl in self.blooms.values():
                d = angular_distance(h["pos"], bl["pos"])
                if d < FIELD_RANGE:
                    bloom_mod = max(bloom_mod,
                        bl["genome"]["emit_amplitude"] *
                        EMIT_MODULATION *
                        (1 - d / FIELD_RANGE))
            # Grazer proximity adds further modulation
            grazer_mod = 0.0
            for gz in list(self.grazers.values())[:50]:  # sample for performance
                d = angular_distance(h["pos"], gz["pos"])
                if d < HUNTER_HUNT_RADIUS:
                    grazer_mod = min(0.3, grazer_mod + 0.05 * (1 - d / HUNTER_HUNT_RADIUS))

            h["emit_state"] = base + bloom_mod + grazer_mod

        # ── Phase 2: receive fields from other hunters ────────────────────────
        for h in alive:
            g              = h["genome"]
            received       = 0.0
            h["pos_before"] = h["pos"]  # snapshot before signal influences move

            for other in alive:
                if other["id"] == h["id"]:
                    continue
                d = angular_distance(h["pos"], other["pos"])
                if d < FIELD_RANGE:
                    strength = (other["emit_state"] *
                                (FIELD_DECAY ** (d / FIELD_RANGE * 10)) *
                                g["field_sensitivity"])
                    received += strength
                    self.total_signals += 1

            h["field_received"]  = received
            h["signal_received"] = received > g["response_threshold"]

        # ── Phase 3: move, feed, breed, die ──────────────────────────────────
        random.shuffle(alive)
        for h in alive:
            h["age"]        += 1
            h["energy"]     -= HUNTER_DEPLETE
            h["breed_cool"]  = max(0, h["breed_cool"] - 1)
            g = h["genome"]

            # Determine movement target
            best_target = None
            best_score  = -1

            # Direct grazer detection
            for gz in list(self.grazers.values()):
                d = angular_distance(h["pos"], gz["pos"])
                if d < HUNTER_HUNT_RADIUS * 2:
                    score = (1 - d / (HUNTER_HUNT_RADIUS * 2))
                    if score > best_score:
                        best_score  = score
                        best_target = gz["pos"]

            # Field signal from other hunters — does it modify behaviour?
            if h["signal_received"] and best_target is None:
                # Follow the field gradient — move toward strongest emitter
                best_emitter = None
                best_strength = 0.0
                for other in alive:
                    if other["id"] == h["id"]:
                        continue
                    d = angular_distance(h["pos"], other["pos"])
                    if d < FIELD_RANGE:
                        s = other["emit_state"] * g["field_sensitivity"]
                        if s > best_strength:
                            best_strength = s
                            best_emitter  = other["pos"]
                if best_emitter:
                    best_target = best_emitter

            # Residue trail
            if best_target is None:
                res = self.get_residue(h["pos"])
                if res * g["residue_sensitivity"] > 0.1:
                    best_target = perturb(h["pos"], 0.1)

            # Memory — last known food positions
            if best_target is None and h["memory"]:
                best_target = h["memory"][-1]

            # Random patrol
            if best_target is None:
                best_target = perturb(h["pos"], g["speed"] * 2)

            h["pos"] = move_toward(h["pos"], best_target,
                                   g["speed"] - HUNTER_MOVE_COST * 0.01)

            # Leave emission residue
            self.add_residue(h["pos"], h["emit_state"] * 0.1)

            # Hunt
            hunted = False
            for gid, gz in list(self.grazers.items()):
                d = angular_distance(h["pos"], gz["pos"])
                if d < HUNTER_HUNT_RADIUS * 0.5:
                    h["energy"] = min(HUNTER_ENERGY_MAX,
                                      h["energy"] + HUNTER_FOOD_GAIN)
                    h["kills"] += 1
                    h["memory"].append(gz["pos"])  # remember where food was
                    del self.grazers[gid]
                    self.deaths["grazer"] += 1
                    hunted = True
                    break

            # Breed
            if (h["energy"] > HUNTER_BREED_THRESH and
                    h["breed_cool"] == 0 and
                    len(self.hunters) + len(new_born) < MAX_HUNTERS):
                per_child = h["energy"] * 0.3 / HUNTER_SPAWN_COUNT
                h["energy"] *= 0.7
                h["breed_cool"] = HUNTER_BREED_COOL
                for _ in range(HUNTER_SPAWN_COUNT):
                    nb = new_hunter(
                        pos=perturb(h["pos"], 0.04),
                        parent=h,
                        energy=per_child
                    )
                    new_born.append(nb)
                    self.births["hunter"] += 1
                    if nb["generation"] > self.generation:
                        self.generation = nb["generation"]

            # Die
            if h["energy"] <= 0 or h["age"] > HUNTER_MAX_AGE:
                dead.append(h["id"])
                self.energy_pool += h["energy"] * 0.3
                self.deaths["hunter"] += 1
                self.add_residue(h["pos"], 5.0)

        for h in new_born:
            self.hunters[h["id"]] = h
        for hid in dead:
            del self.hunters[hid]

        while len(self.hunters) < MIN_HUNTERS:
            nb = new_hunter()
            self.hunters[nb["id"]] = nb

    # ── Behaviour modification measurement ───────────────────────────────────

    def measure_behaviour_modification(self):
        """
        For each hunter that received a signal this cycle:
        did it move toward food vs where it would have gone otherwise?
        
        Returns: mean behaviour delta (positive = signal helped)
        """
        if not self.hunters:
            return 0.0

        deltas = []
        for h in self.hunters.values():
            if not h["signal_received"] or h["pos_before"] is None:
                continue
            if not h["memory"]:
                continue

            last_food = h["memory"][-1]
            # Distance to food before signal influenced move
            d_before = angular_distance(h["pos_before"], last_food)
            # Distance to food after move
            d_after  = angular_distance(h["pos"], last_food)
            # Positive delta = moved closer to food = signal was useful
            delta = d_before - d_after
            deltas.append(delta)

        return sum(deltas) / len(deltas) if deltas else 0.0

    # ── Main step ─────────────────────────────────────────────────────────────

    def step(self):
        self.cycle += 1
        self.step_vents()
        self.step_blooms()
        self.decay_residue()
        self.step_grazers()
        self.step_hunters()

        # Sample behaviour modification
        if self.cycle % BM_SAMPLE_INTERVAL == 0:
            bm = self.measure_behaviour_modification()
            self.bm_log.append({
                "cycle": self.cycle,
                "bm":    round(bm, 6),
                "signals": self.total_signals,
                "hunters": len(self.hunters),
                "grazers": len(self.grazers),
            })

    def bm_trend(self):
        """Is behaviour modification increasing over recent samples?"""
        if len(self.bm_log) < 4:
            return 0.0
        vals = [x["bm"] for x in self.bm_log]
        # Simple linear trend
        n    = len(vals)
        mean = sum(vals) / n
        xs   = list(range(n))
        xm   = sum(xs) / n
        num  = sum((xs[i] - xm) * (vals[i] - mean) for i in range(n))
        den  = sum((xs[i] - xm) ** 2 for i in range(n))
        return round(num / den, 8) if den else 0.0

    def summary(self):
        bm_recent = list(self.bm_log)[-1]["bm"] if self.bm_log else 0.0
        return {
            "cycle":           self.cycle,
            "generation":      self.generation,
            "vents":           len(self.vents),
            "blooms":          len(self.blooms),
            "grazers":         len(self.grazers),
            "hunters":         len(self.hunters),
            "total_signals":   self.total_signals,
            "bm_recent":       round(bm_recent, 6),
            "bm_trend":        self.bm_trend(),
            "energy_pool":     round(self.energy_pool, 1),
            "births":          dict(self.births),
            "deaths":          dict(self.deaths),
            "residue_cells":   len(self.residue),
            "bm_log":          list(self.bm_log)[-20:],
        }

# ── Simulation loop ───────────────────────────────────────────────────────────

world        = World()
_lock        = threading.Lock()
_running     = True
_cache       = {}          # cached summary for HTTP endpoints
_cache_cycle = -1

STATE_FILE = '/mnt/data/state.json'

def update_cache():
    global _cache, _cache_cycle
    with _lock:
        s = world.summary()
    _cache       = s
    _cache_cycle = s["cycle"]
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(s, f)
    except Exception as e:
        log.warning(f"Cache write failed: {e}")

def read_cache():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return _cache

def run_loop():
    global _running
    log.info("Origin experiment started — running flat out")
    report_interval = 1000
    cache_interval  = 100
    last_report     = 0

    while _running:
        world.step()
        c = world.cycle
        if c % 10 == 0:
            update_cache()
            time.sleep(0)  # yield GIL

        if c - last_report >= report_interval:
            s = _cache
            log.info(
                f"cycle:{s['cycle']:>8} gen:{s['generation']:>4} "
                f"H:{s['hunters']:>4} G:{s['grazers']:>6} "
                f"BL:{s['blooms']:>3} V:{s['vents']:>2} "
                f"signals:{s['total_signals']:>8} "
                f"bm:{s['bm_recent']:>+.4f} trend:{s['bm_trend']:>+.6f}"
            )
            last_report = c

update_cache()  # initialise cache before thread starts
_thread = threading.Thread(target=run_loop, daemon=True)
_thread.start()

# ── Flask endpoints ───────────────────────────────────────────────────────────

@app.route("/field/health")
def field_health():
    s = read_cache() if _cache else {}
    return jsonify({
        "status":        "running",
        "service":       "origin-experiment",
        "cycle":         s.get("cycle", 0),
        "generation":    s.get("generation", 0),
        "hunters":       s.get("hunters", 0),
        "grazers":       s.get("grazers", 0),
        "blooms":        s.get("blooms", 0),
        "vents":         s.get("vents", 0),
        "total_signals": s.get("total_signals", 0),
        "bm_recent":     s.get("bm_recent", 0),
        "bm_trend":      s.get("bm_trend", 0),
        "energy_pool":   s.get("energy_pool", 0),
    })

@app.route("/field/summary")
def field_summary():
    return jsonify(read_cache())

@app.route("/field/bm")
def field_bm():
    """Behaviour modification log — the core experiment output."""
    s = read_cache()
    return jsonify({
        "question":      "Does entity A modify the behaviour of entity B, and by what means?",
        "bm_log":        s.get("bm_log", []),
        "bm_trend":      s.get("bm_trend", 0),
        "total_signals": s.get("total_signals", 0),
        "cycle":         s.get("cycle", 0),
    })

@app.route("/field/hunters")
def field_hunters():
    """Snapshot of hunter genomes — watch evolution in action."""
    with _lock:
        hunters = []
        for h in list(world.hunters.values())[:50]:
            hunters.append({
                "id":              h["id"],
                "generation":      h["generation"],
                "age":             h["age"],
                "energy":          round(h["energy"], 1),
                "kills":           h["kills"],
                "genome":          {k: round(v, 3) if isinstance(v, float) else v
                                    for k, v in h["genome"].items()},
                "emit_state":      round(h["emit_state"], 3),
                "signal_received": h["signal_received"],
            })
    return jsonify({"hunters": hunters, "cycle": world.cycle})

@app.route("/field/stop")
def field_stop():
    global _running
    _running = False
    return jsonify({"status": "stopped"})

@app.route("/field/start")
def field_start():
    global _running, _thread
    if not _running:
        _running = True
        _thread  = threading.Thread(target=run_loop, daemon=True)
        _thread.start()
    return jsonify({"status": "running"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
