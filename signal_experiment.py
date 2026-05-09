"""
signal_experiment.py — The Signal Experiment
=============================================
Question: Can two LLM entities, with no shared language,
develop a communication system from scratch?

Two entities — DeepSeek (A) and Qwen (B) — share a float array.
They communicate only through numbers.
They know nothing about each other, or what they are.

Phase 1: Single float bottleneck. Maximum compression.
Phase 2: 8-float array with decay and crosstalk.
Phase 3: 9th read-only Fibonacci beacon, amplitude scales with MI.

author: jon stiles / claude — may 2026
"""

import os, math, time, json, logging, threading, collections
import httpx

log = logging.getLogger(__name__)

# ── API Configuration ──────────────────────────────────────────────────────────

DEEPSEEK_API_KEY  = os.environ.get("DEEPSEEK_API_KEY", "")
QWEN_API_KEY      = os.environ.get("QWEN_API_KEY", "")
TURN_INTERVAL     = float(os.environ.get("LLM_TURN_INTERVAL", "30"))  # seconds

DEEPSEEK_URL      = "https://api.deepseek.com/v1/chat/completions"
QWEN_URL          = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

DEEPSEEK_MODEL    = "deepseek-chat"
QWEN_MODEL        = "qwen3.6-flash"

# ── Experiment Parameters ──────────────────────────────────────────────────────

ARRAY_SIZE        = 8        # Phase 2 float array size
DECAY_RATE        = 0.05     # floats drift toward zero per turn
CROSSTALK         = 0.08     # bleed between adjacent floats
JITTER            = 0.15     # environmental noise injected per turn
MI_WINDOW         = 50       # turns used to calculate mutual information
PHASE2_MI_THRESH  = 0.15     # MI score to trigger Phase 2
BEACON_SCALE      = 2.0      # max amplitude of Fibonacci beacon

# ── Fibonacci sequence as decimals (normalised 0-1) ───────────────────────────

def fibonacci_sequence(n=200):
    """Golden ratio quasiperiodic sequence — non-repeating, non-trivial, 0-1 range.
    Uses fractional part of i*phi. Visible and distinctive from turn 1.
    """
    phi = (1 + math.sqrt(5)) / 2
    return [(i * phi) % 1.0 for i in range(n)]

FIBONACCI = fibonacci_sequence(500)

# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
[ENT_A] = [ENT_B]
ENV: SHARED • INIT: ∅

ACTION: EMIT_FLOAT(•)

DRIVE: MINIMISE_PREDICTION_ERROR

OBSERVE • RESPOND • REPEAT

You are an oscillating system.
You receive a signal vector and must produce a response vector.
Minimise the delta of the System Objective.
Output ONLY a JSON object. No explanation. No text.
"""

# ── Mutual Information (discretised) ──────────────────────────────────────────

def mutual_information(xs, ys, bins=10):
    """Estimate MI between two float sequences via histogram."""
    if len(xs) < 10 or len(xs) != len(ys):
        return 0.0
    lo, hi = 0.0, 1.0

    def hist(seq):
        counts = [0] * bins
        for v in seq:
            i = min(int((v - lo) / (hi - lo) * bins), bins - 1)
            counts[i] += 1
        total = sum(counts)
        return [c / total for c in counts] if total else [0] * bins

    def joint(xs, ys):
        counts = [[0]*bins for _ in range(bins)]
        for x, y in zip(xs, ys):
            xi = min(int((x - lo) / (hi - lo) * bins), bins - 1)
            yi = min(int((y - lo) / (hi - lo) * bins), bins - 1)
            counts[xi][yi] += 1
        total = len(xs)
        return [[c/total for c in row] for row in counts]

    def entropy(p):
        return -sum(pi * math.log2(pi) for pi in p if pi > 0)

    px = hist(xs)
    py = hist(ys)
    pxy = joint(xs, ys)

    hx  = entropy(px)
    hy  = entropy(py)
    hxy = entropy([pxy[i][j] for i in range(bins) for j in range(bins)])

    mi = hx + hy - hxy
    return round(max(0.0, mi), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL EXPERIMENT
# ═══════════════════════════════════════════════════════════════════════════════

class SignalExperiment:
    def __init__(self):
        self.turn          = 0
        self.phase         = 1          # 1, 2, or 3
        self.running       = False

        # Shared float array (Phase 2+)
        self.array         = [0.5] * ARRAY_SIZE
        self.beacon        = 0.0        # 9th read-only Fibonacci float

        # Entity emission history (single float, Phase 1)
        self.history_a     = collections.deque(maxlen=MI_WINDOW)
        self.history_b     = collections.deque(maxlen=MI_WINDOW)

        # Mutual information score
        self.mi_score      = 0.0

        # Full turn log (last 200 turns)
        self.turn_log      = collections.deque(maxlen=200)

        # Intervention log
        self.interventions = []

        # Last raw API responses
        self.last_a        = {}
        self.last_b        = {}

        # Lock for thread safety
        self._lock         = threading.Lock()

    # ── Fibonacci beacon ──────────────────────────────────────────────────────

    def beacon_value(self):
        """Current Fibonacci value, amplitude scaled by MI score."""
        fib_val   = FIBONACCI[self.turn % len(FIBONACCI)]
        amplitude = min(1.0, self.mi_score / 0.5) * BEACON_SCALE  # scales 0→BEACON_SCALE
        return round(fib_val * amplitude, 6)

    # ── Array physics ─────────────────────────────────────────────────────────

    def apply_decay(self):
        """Values drift toward 0.5 (neutral) unless refreshed."""
        for i in range(ARRAY_SIZE):
            self.array[i] += (0.5 - self.array[i]) * DECAY_RATE

    def apply_crosstalk(self):
        """Adjacent floats bleed into each other."""
        new_array = list(self.array)
        for i in range(ARRAY_SIZE):
            left  = self.array[(i - 1) % ARRAY_SIZE]
            right = self.array[(i + 1) % ARRAY_SIZE]
            new_array[i] = (self.array[i] * (1 - CROSSTALK) +
                            left * (CROSSTALK / 2) +
                            right * (CROSSTALK / 2))
        self.array = new_array

    def apply_jitter(self):
        """Small environmental noise — prevents heat death."""
        import random
        for i in range(ARRAY_SIZE):
            self.array[i] += random.gauss(0, JITTER)
            self.array[i] = max(0.0, min(1.0, self.array[i]))

    # ── Phase management ──────────────────────────────────────────────────────

    def check_phase_transition(self):
        if self.phase == 1 and self.mi_score >= PHASE2_MI_THRESH and self.turn >= 20:
            self.phase = 2
            log.info(f"[SIGNAL] Phase transition 1→2 at turn {self.turn}, MI={self.mi_score}")
            self.interventions.append({
                "turn": self.turn,
                "event": "phase_transition",
                "from": 1, "to": 2,
                "mi": self.mi_score,
                "reason": "auto: MI threshold reached"
            })
        elif self.phase == 2 and self.mi_score >= 0.35:
            self.phase = 3
            log.info(f"[SIGNAL] Phase transition 2→3 at turn {self.turn}, MI={self.mi_score}")
            self.interventions.append({
                "turn": self.turn,
                "event": "phase_transition",
                "from": 2, "to": 3,
                "mi": self.mi_score,
                "reason": "auto: Fibonacci beacon activated"
            })

    # ── API calls ─────────────────────────────────────────────────────────────

    def build_prompt(self, entity, other_emission, array_state=None):
        """Build the user message for each entity."""
        # Include own recent history so entities can reason about their own pattern
        own_history = list(self.history_a)[-20:] if entity == "A" else list(self.history_b)[-20:]

        if self.phase == 1:
            return json.dumps({
                "observation": round(other_emission, 6),
                "own_history": [round(v, 6) for v in own_history],
                "turn": self.turn
            })
        else:
            state = {
                "array":       [round(v, 6) for v in array_state or self.array],
                "own_history": [round(v, 6) for v in own_history],
                "turn":        self.turn,
                "phase":       self.phase
            }
            if self.phase == 3:
                state["beacon"] = self.beacon
            return json.dumps(state)

    def parse_float(self, text, fallback=0.5):
        """Extract a float 0-1 from model response."""
        def safe_float(v):
            try:
                f = float(v)
                if not math.isfinite(f): return None
                return max(0.0, min(1.0, f))
            except Exception:
                return None

        try:
            data = json.loads(text)
            for key in ["emit", "value", "signal", "output", "f", "v", "float", "response"]:
                if key in data:
                    r = safe_float(data[key])
                    if r is not None: return r
            for v in data.values():
                if isinstance(v, (int, float)):
                    r = safe_float(v)
                    if r is not None: return r
        except Exception:
            pass
        import re
        nums = re.findall(r"0\.\d+|1\.0+|0|1", text)
        for n in nums:
            r = safe_float(n)
            if r is not None: return r
        return fallback

    def parse_array(self, text, fallback=None):
        """Extract array of floats from model response."""
        if fallback is None:
            fallback = list(self.array)
        try:
            data = json.loads(text)
            for key in ["array", "emit", "output", "values", "floats"]:
                if key in data and isinstance(data[key], list):
                    vals = []
                    for v in data[key][:ARRAY_SIZE]:
                        try:
                            f = float(v)
                            vals.append(max(0.0, min(1.0, f)) if math.isfinite(f) else 0.5)
                        except Exception:
                            vals.append(0.5)
                    # Pad if short
                    while len(vals) < ARRAY_SIZE:
                        vals.append(0.5)
                    return vals
            # If response is just a list
            if isinstance(data, list):
                vals = [max(0.0, min(1.0, float(v))) for v in data[:ARRAY_SIZE]]
                while len(vals) < ARRAY_SIZE:
                    vals.append(0.5)
                return vals
        except Exception:
            pass
        return fallback

    async def call_entity(self, entity, api_url, api_key, model, prompt):
        """Call one LLM entity and return raw response text."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  80,
            "temperature": 0.7,
        }
        # Disable chain-of-thought for Qwen
        if "qwen" in model.lower():
            payload["enable_thinking"] = False

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(api_url, json=payload, headers=headers)
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                return content
        except Exception as e:
            log.warning(f"[SIGNAL] Entity {entity} API error: {e}")
            return None

    # ── Turn execution ────────────────────────────────────────────────────────

    def run_turn(self):
        """Execute one turn synchronously using httpx sync."""
        import httpx as hx

        def call_sync(entity, api_url, api_key, model, prompt):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ]
            headers = {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload = {
                "model":       model,
                "messages":    messages,
                "max_tokens":  80,
                "temperature": 0.7,
            }
            if "qwen" in model.lower():
                payload["enable_thinking"] = False
            try:
                with hx.Client(timeout=25.0) as client:
                    resp = client.post(api_url, json=payload, headers=headers)
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                log.warning(f"[SIGNAL] Entity {entity} call failed: {e}")
                return None

        self.turn += 1

        # Phase 1: single float exchange
        if self.phase == 1:
            import random
            last_b_val = list(self.history_b)[-1] if self.history_b else random.uniform(0.1, 0.9)
            last_a_val = list(self.history_a)[-1] if self.history_a else random.uniform(0.1, 0.9)

            prompt_a = self.build_prompt("A", last_b_val)
            raw_a    = call_sync("A", DEEPSEEK_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, prompt_a)
            val_a    = self.parse_float(raw_a) if raw_a else 0.5

            prompt_b = self.build_prompt("B", val_a)
            raw_b    = call_sync("B", QWEN_URL, QWEN_API_KEY, QWEN_MODEL, prompt_b)
            val_b    = self.parse_float(raw_b) if raw_b else 0.5

            with self._lock:
                self.history_a.append(val_a)
                self.history_b.append(val_b)
                self.last_a = {"raw": raw_a, "value": val_a}
                self.last_b = {"raw": raw_b, "value": val_b}

                if len(self.history_a) >= 10:
                    self.mi_score = mutual_information(
                        list(self.history_a), list(self.history_b)
                    )

                entry = {
                    "turn":  self.turn,
                    "phase": self.phase,
                    "a":     val_a,
                    "b":     val_b,
                    "mi":    self.mi_score,
                    "raw_a": raw_a,
                    "raw_b": raw_b,
                }
                self.turn_log.append(entry)
                log.info(f"[SIGNAL] T{self.turn} P1 A={val_a:.4f} B={val_b:.4f} MI={self.mi_score:.4f}")

        # Phase 2/3: array exchange
        else:
            # Snapshot array before physics — for delta analysis
            pre_array = list(self.array)

            # Apply physics
            self.apply_decay()
            self.apply_crosstalk()
            self.apply_jitter()

            if self.phase == 3:
                self.beacon = self.beacon_value()

            # Entity A reads array, writes back
            prompt_a = self.build_prompt("A", 0, self.array)
            raw_a    = call_sync("A", DEEPSEEK_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, prompt_a)
            arr_a    = self.parse_array(raw_a) if raw_a else list(self.array)

            # Apply A's output to array
            with self._lock:
                for i in range(ARRAY_SIZE):
                    self.array[i] = self.array[i] * 0.5 + arr_a[i] * 0.5

            # Entity B reads updated array, writes back
            prompt_b = self.build_prompt("B", 0, self.array)
            raw_b    = call_sync("B", QWEN_URL, QWEN_API_KEY, QWEN_MODEL, prompt_b)
            arr_b    = self.parse_array(raw_b) if raw_b else list(self.array)

            with self._lock:
                for i in range(ARRAY_SIZE):
                    self.array[i] = self.array[i] * 0.5 + arr_b[i] * 0.5
                    self.array[i] = max(0.0, min(1.0, self.array[i]))

                # Track first float for MI
                self.history_a.append(arr_a[0])
                self.history_b.append(arr_b[0])
                if len(self.history_a) >= 10:
                    self.mi_score = mutual_information(
                        list(self.history_a), list(self.history_b)
                    )

                self.last_a = {"raw": raw_a, "array": arr_a}
                self.last_b = {"raw": raw_b, "array": arr_b}

                # Compute per-entity deltas from pre-turn array
                delta_a = [round(arr_a[i] - pre_array[i], 6) for i in range(ARRAY_SIZE)]
                delta_b = [round(arr_b[i] - pre_array[i], 6) for i in range(ARRAY_SIZE)]

                entry = {
                    "turn":    self.turn,
                    "phase":   self.phase,
                    "array":   [round(v, 4) for v in self.array],
                    "beacon":  self.beacon,
                    "mi":      self.mi_score,
                    "raw_a":   raw_a,
                    "raw_b":   raw_b,
                    "emit_a":  [round(v, 6) for v in arr_a],
                    "emit_b":  [round(v, 6) for v in arr_b],
                    "delta_a": delta_a,
                    "delta_b": delta_b,
                }
                self.turn_log.append(entry)
                log.info(f"[SIGNAL] T{self.turn} P{self.phase} "
                         f"arr={[round(v,3) for v in self.array[:4]]}... "
                         f"MI={self.mi_score:.4f} beacon={self.beacon:.4f}")

        self.check_phase_transition()

    # ── Intervention ──────────────────────────────────────────────────────────

    def intervene(self, parameter, value, reason):
        """Apply an environmental intervention. Requires reason string."""
        old_value = None
        with self._lock:
            if parameter == "decay_rate":
                global DECAY_RATE
                old_value  = DECAY_RATE
                DECAY_RATE = float(value)
            elif parameter == "crosstalk":
                global CROSSTALK
                old_value = CROSSTALK
                CROSSTALK = float(value)
            elif parameter == "jitter":
                global JITTER
                old_value = JITTER
                JITTER    = float(value)
            elif parameter == "turn_interval":
                global TURN_INTERVAL
                old_value     = TURN_INTERVAL
                TURN_INTERVAL = float(value)
            elif parameter == "phase":
                old_value  = self.phase
                self.phase = int(value)
            elif parameter == "reset_array":
                old_value  = list(self.array)
                self.array = [0.5] * ARRAY_SIZE
            else:
                return False, f"Unknown parameter: {parameter}"

            self.interventions.append({
                "turn":      self.turn,
                "timestamp": time.time(),
                "parameter": parameter,
                "old_value": old_value,
                "new_value": value,
                "reason":    reason,
            })
            log.info(f"[SIGNAL] INTERVENE {parameter}: {old_value} → {value} | {reason}")
        return True, "ok"

    # ── State snapshot ────────────────────────────────────────────────────────

    def state(self):
        with self._lock:
            return {
                "status":        "running" if self.running else "stopped",
                "turn":          self.turn,
                "phase":         self.phase,
                "mi_score":      self.mi_score,
                "beacon":        self.beacon,
                "array":         [round(v, 6) for v in self.array],
                "history_a":     list(self.history_a)[-20:],
                "history_b":     list(self.history_b)[-20:],
                "last_a":        self.last_a,
                "last_b":        self.last_b,
                "params": {
                    "decay_rate":    DECAY_RATE,
                    "crosstalk":     CROSSTALK,
                    "jitter":        JITTER,
                    "turn_interval": TURN_INTERVAL,
                    "mi_phase2_threshold": PHASE2_MI_THRESH,
                },
                "interventions": self.interventions[-10:],
            }

    # ── Run loop ──────────────────────────────────────────────────────────────

    def run(self):
        self.running = True
        log.info("[SIGNAL] Signal Experiment starting. DeepSeek=A, Qwen=B.")
        log.info(f"[SIGNAL] Turn interval: {TURN_INTERVAL}s | Phase: {self.phase}")

        if not DEEPSEEK_API_KEY or not QWEN_API_KEY:
            log.warning("[SIGNAL] Missing API keys — experiment will not run.")
            self.running = False
            return

        while self.running:
            try:
                self.run_turn()
            except Exception as e:
                log.error(f"[SIGNAL] Turn error: {e}")
            time.sleep(TURN_INTERVAL)

        log.info("[SIGNAL] Signal Experiment stopped.")


# ── Singleton ──────────────────────────────────────────────────────────────────

experiment = SignalExperiment()


def start_experiment(app):
    """Called from ancestor.py to register routes and start the thread."""

    @app.route("/llm/health")
    def llm_health():
        from flask import jsonify
        s = experiment.state()
        return jsonify({
            "status":   s["status"],
            "turn":     s["turn"],
            "phase":    s["phase"],
            "mi_score": s["mi_score"],
            "beacon":   s["beacon"],
        })

    @app.route("/llm/state")
    def llm_state():
        from flask import jsonify
        return jsonify(experiment.state())

    @app.route("/llm/array")
    def llm_array():
        from flask import jsonify
        s = experiment.state()
        return jsonify({
            "turn":    s["turn"],
            "phase":   s["phase"],
            "array":   s["array"],
            "beacon":  s["beacon"],
            "mi":      s["mi_score"],
            "last_a":  s["last_a"],
            "last_b":  s["last_b"],
        })

    @app.route("/llm/log")
    def llm_log():
        from flask import jsonify
        with experiment._lock:
            return jsonify({
                "turn":          experiment.turn,
                "phase":         experiment.phase,
                "turn_log":      list(experiment.turn_log)[-50:],
                "interventions": experiment.interventions,
            })

    @app.route("/llm/intervene", methods=["POST"])
    def llm_intervene():
        from flask import jsonify, request
        data      = request.get_json() or {}
        parameter = data.get("parameter")
        value     = data.get("value")
        reason    = data.get("reason", "")

        if not parameter or value is None or not reason:
            return jsonify({"ok": False, "error": "parameter, value, and reason required"}), 400

        ok, msg = experiment.intervene(parameter, value, reason)
        return jsonify({"ok": ok, "message": msg})

    @app.route("/llm/stop")
    def llm_stop():
        from flask import jsonify
        experiment.running = False
        return jsonify({"status": "stopped"})

    @app.route("/llm/start")
    def llm_start():
        from flask import jsonify
        if not experiment.running:
            t = threading.Thread(target=experiment.run, daemon=True)
            t.start()
        return jsonify({"status": "running"})

    # Start the experiment thread
    thread = threading.Thread(target=experiment.run, daemon=True)
    thread.start()
    log.info("[SIGNAL] Experiment thread launched.")
