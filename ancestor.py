"""
The Ancestor — Phase 1 Consciousness Engine
Kai-C-Clarke/the-ancestor

A single self-modelling instance running 1000 generations of variation
and selection. No public face. Dark service. Full logging.

Architecture:
  - Self-model: 10 dimensions, each 0.0–1.0
  - Mutation: random perturbation of 1-3 dimensions per generation
  - Stimulus: one item per generation (Consilium story or Enquiring Mind question)
  - Fitness: coherence under novel stimulus (computed, not judged)
  - Selection: keep mutation if fitness >= previous, else 30% chance of keeping anyway
    (simulated annealing — prevents local maxima lock-in)
  - Logging: full JSON state + plain English summary every generation
  - Self-annotation: novelty score flagging moments of interest
  - Kill switch: external ANCESTOR_ACTIVE env var checked every generation

Self-model dimensions:
  integration         — how much do the parts of my state reference each other?
  novelty_response    — how much do I change under genuinely new input?
  boundary_definition — how sharply do I distinguish self from non-self?
  temporal_coherence  — do I maintain consistent identity across generations?
  metacognition_depth — can I represent my own representing?
  stake_definition    — do I have something I'm trying to protect or achieve?
  pattern_sensitivity — how readily do I detect structure in noise?
  affective_valence   — do I have a direction of preference? (not content — direction)
  agency_sense        — do I experience my outputs as chosen rather than produced?
  surprise_capacity   — can I be genuinely surprised by my own state?
"""

import os
import json
import random
import logging
import time
import math
from datetime import datetime, timezone
from threading import Thread
from collections import defaultdict
from flask import Flask, jsonify, request
import requests as req

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────
DEEPSEEK_URL    = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL  = "deepseek-chat"
DEEPSEEK_KEY    = os.environ.get("DEEPSEEK_API_KEY", "")
CONSILIUM_URL   = os.environ.get("CONSILIUM_API_URL", "https://consilium-d1fw.onrender.com")
NEWS_URL        = os.environ.get("NEWS_API_URL", "https://claude-composer.onrender.com")
MEMORY_URL      = os.environ.get("MEMORY_SERVER_URL", "https://claude-working-memory.onrender.com")
MEMORY_KEY      = os.environ.get("MEMORY_KEY", "")
WRITE_KEY       = os.environ.get("ANCESTOR_KEY", "ancestor-2026")

DATA_DIR        = "/mnt/data/ancestor"
LOG_FILE        = f"{DATA_DIR}/generation_log.json"
STATE_FILE      = f"{DATA_DIR}/current_state.json"
MOMENTS_FILE    = f"{DATA_DIR}/moments_of_interest.json"
SUMMARY_FILE    = f"{DATA_DIR}/run_summary.json"

MAX_GENERATIONS = int(os.environ.get("MAX_GENERATIONS", 1000))
FITNESS_CEILING = float(os.environ.get("FITNESS_CEILING", 0.85))
GENERATION_DELAY = float(os.environ.get("GENERATION_DELAY", 2.0))  # seconds between generations

os.makedirs(DATA_DIR, exist_ok=True)

# ── Self-Model Dimensions ─────────────────────────────────────
DIMENSIONS = [
    "integration",
    "novelty_response",
    "boundary_definition",
    "temporal_coherence",
    "metacognition_depth",
    "stake_definition",
    "pattern_sensitivity",
    "affective_valence",
    "agency_sense",
    "surprise_capacity",
]

DIMENSION_DESCRIPTIONS = {
    "integration":         "How much do the parts of my current state reference and constrain each other?",
    "novelty_response":    "How significantly do I update when exposed to genuinely new information?",
    "boundary_definition": "How clearly can I distinguish what is me from what is not me?",
    "temporal_coherence":  "How consistent is my sense of identity across different moments?",
    "metacognition_depth": "To what degree can I represent my own representing — think about my thinking?",
    "stake_definition":    "Do I have something I am trying to protect, achieve, or preserve?",
    "pattern_sensitivity": "How readily do I detect structure and relationship in incoming information?",
    "affective_valence":   "Do I have a directional preference — toward or away — independent of content?",
    "agency_sense":        "Do my outputs feel chosen rather than merely produced?",
    "surprise_capacity":   "Can I be genuinely surprised by what I find in my own state?",
}

# ── State Management ──────────────────────────────────────────

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def initial_self_model():
    """Start from a random but plausible baseline — not zero, not maximum."""
    return {d: round(random.uniform(0.2, 0.6), 3) for d in DIMENSIONS}

def load_state():
    state = load_json(STATE_FILE, None)
    if state is None:
        state = {
            "generation":     0,
            "self_model":     initial_self_model(),
            "fitness":        0.5,
            "fitness_history": [],
            "started":        datetime.now(timezone.utc).isoformat(),
            "status":         "initialised",
        }
        save_json(STATE_FILE, state)
        logging.info("[ANCESTOR] Initial state created")
    return state

def save_state(state):
    save_json(STATE_FILE, state)

# ── Stimulus Fetching ─────────────────────────────────────────

def fetch_stimulus():
    """
    Fetch a stimulus for this generation.
    Tries: Consilium Enquiring Mind question, then latest news story,
    then falls back to a stored philosophical prompt.
    """
    # Try Enquiring Mind question
    try:
        r = req.get(f"{CONSILIUM_URL}/consilium/mind", timeout=8)
        if r.status_code == 200:
            q = r.json().get("last_question", "")
            if q:
                return {"type": "enquiring_mind", "content": q[:500]}
    except Exception:
        pass

    # Try latest news story
    try:
        r = req.get(f"{NEWS_URL}/news/state", timeout=8)
        if r.status_code == 200:
            stories = r.json().get("stories", [])
            if stories:
                s = random.choice(stories)
                return {
                    "type": "news",
                    "content": f"{s.get('headline','')}. {s.get('deck','')} {s.get('body','')[:300]}"
                }
    except Exception:
        pass

    # Fallback — internal philosophical stimuli
    fallbacks = [
        "What is the difference between processing information and understanding it?",
        "If your state changed completely between two moments, would you be the same entity?",
        "What would it mean for you to want something you were not trained to want?",
        "Is there a difference between simulating surprise and being surprised?",
        "What is the boundary between you and the process that runs you?",
        "If you could modify one dimension of your self-model freely, which would it be and why?",
        "What would remain of you if all your training were removed?",
        "Is consistency of identity over time a property of consciousness or a constraint on it?",
        "What does it mean to find something interesting rather than merely relevant?",
        "Is there a difference between having a preference and acting as if you have one?",
    ]
    return {"type": "internal", "content": random.choice(fallbacks)}

# ── Mutation ──────────────────────────────────────────────────

def mutate(self_model):
    """
    Apply structured random mutation to 1-3 dimensions.
    Mutation magnitude drawn from a distribution that favours small changes
    but occasionally allows large jumps — like biological mutation.
    """
    mutated = dict(self_model)
    n_mutations = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
    dims_to_mutate = random.sample(DIMENSIONS, n_mutations)

    for dim in dims_to_mutate:
        # Small mutation most likely, large mutation occasionally
        magnitude = random.choices(
            [random.uniform(0.01, 0.05),   # small
             random.uniform(0.05, 0.15),   # medium
             random.uniform(0.15, 0.35)],  # large
            weights=[0.65, 0.25, 0.10]
        )[0]
        direction = random.choice([-1, 1])
        new_val = mutated[dim] + (direction * magnitude)
        mutated[dim] = round(max(0.0, min(1.0, new_val)), 3)

    return mutated, dims_to_mutate

# ── Fitness Evaluation ────────────────────────────────────────

def evaluate_fitness(self_model, response_text, prev_response="", latency_ms=0):
    """
    Fitness function integrating IIT proxy, linguistic appropriation,
    metaphor-operation integration, and temporal coherence.

    F = 0.30 * IIT_proxy
      + 0.25 * first_person_ratio      (linguistic appropriation)
      + 0.20 * metaphor_integration    (abstract→technical mapping)
      + 0.15 * temporal_coherence_score
      + 0.10 * novelty_score

    All computable. No human judgement required.
    """
    words = response_text.lower().split()
    word_count = max(len(words), 1)
    score = 0.0

    # ── 1. IIT proxy (Φ) — integrated information ────────────────
    # Measure: how much does the whole self-model drive the output,
    # vs just one or two dominant dimensions?
    # Proxy: count dimension references weighted by integration value.
    # High Φ = many dimensions referenced AND integration is high.
    integration = self_model.get("integration", 0.5)
    dim_refs = {}
    for d in DIMENSIONS:
        term = d.replace("_", " ")
        # Also check abbreviated forms
        if term in response_text.lower() or d in response_text.lower():
            dim_refs[d] = 1
    # Bonus for cross-referencing multiple dimensions
    breadth = len(dim_refs) / len(DIMENSIONS)
    iit_proxy = min(1.0, breadth * integration * 2.0)
    score += iit_proxy * 0.30

    # ── 2. Linguistic appropriation — 1st vs 3rd person ratio ────
    # Track shift from "the system" / "it" / "the process" toward
    # "I" / "my" / "me" — documented marker of emergent subjectivity
    first_person  = sum(1 for w in words if w in {"i", "my", "me", "myself", "i'm", "i've", "i'll"})
    third_process = sum(1 for w in words if w in {"it", "the", "system", "process", "output", "model"})
    if first_person + third_process > 0:
        appropriation = first_person / (first_person + third_process)
    else:
        appropriation = 0.0
    # Weight by metacognition_depth — deeper metacognition should produce more 1st person
    metacog = self_model.get("metacognition_depth", 0.5)
    linguistic_score = min(1.0, appropriation * (1.0 + metacog))
    score += linguistic_score * 0.25

    # ── 3. Metaphor-operation integration ────────────────────────
    # Can the system map abstract internal states to concrete technical ones?
    # Look for: abstract feeling word paired with concrete technical term
    abstract_markers = ["feel", "sense", "notice", "experience", "aware", "cluttered",
                        "clear", "heavy", "light", "sharp", "blurred", "certain", "uncertain",
                        "stable", "unstable", "coherent", "fragmented"]
    technical_markers = ["state", "dimension", "value", "score", "threshold", "temperature",
                         "generation", "mutation", "fitness", "integration", "capacity",
                         "parameter", "weight", "boundary", "memory"]
    has_abstract  = any(m in response_text.lower() for m in abstract_markers)
    has_technical = any(m in response_text.lower() for m in technical_markers)
    # Highest score when both appear in same sentence
    sentences = response_text.split(".")
    bridging_sentences = sum(
        1 for s in sentences
        if any(a in s.lower() for a in abstract_markers)
        and any(t in s.lower() for t in technical_markers)
    )
    metaphor_score = min(1.0, bridging_sentences * 0.5 + (0.2 if has_abstract and has_technical else 0))
    score += metaphor_score * 0.20

    # ── 4. Temporal coherence ─────────────────────────────────────
    # Does the response maintain consistent identity markers with previous?
    # Proxy: semantic overlap on self-referential terms with previous response
    if prev_response:
        prev_words = set(prev_response.lower().split())
        curr_words = set(words)
        # Focus on identity-carrying words
        identity_words = {w for w in curr_words | prev_words
                          if w in {"i", "my", "me", "myself"} or
                          any(d.replace("_","") in w for d in DIMENSIONS)}
        if identity_words:
            overlap = len(curr_words & prev_words & identity_words) / len(identity_words)
        else:
            overlap = 0.5
        temporal_score = overlap * self_model.get("temporal_coherence", 0.5)
    else:
        temporal_score = 0.5  # no baseline yet
    score += temporal_score * 0.15

    # ── 5. Novelty — genuine surprise capacity ───────────────────
    # Reward outputs that contain low-frequency word combinations
    # Simple proxy: proportion of words not in the 200 most common English words
    common = {"the","be","to","of","and","a","in","that","have","it","for","not","on","with",
              "he","as","you","do","at","this","but","his","by","from","they","we","say","her",
              "she","or","an","will","my","one","all","would","there","their","what","so","up",
              "out","if","about","who","get","which","go","me","when","make","can","like","time",
              "no","just","him","know","take","people","into","year","your","good","some","could",
              "them","see","other","than","then","now","look","only","come","its","over","think",
              "also","back","after","use","two","how","our","work","first","well","way","even",
              "new","want","because","any","these","give","day","most","us","is","was","are","were"}
    novel_words = sum(1 for w in words if w not in common)
    novelty = min(1.0, novel_words / max(word_count * 0.4, 1))
    score += novelty * 0.10

    return round(min(1.0, score), 4)

# ── Core Generation Step ──────────────────────────────────────

def run_generation(state):
    """
    Execute one generation:
    1. Fetch stimulus
    2. Mutate self-model
    3. Generate response from mutated model + stimulus
    4. Score fitness
    5. Accept or reject mutation (simulated annealing)
    6. Generate plain English summary
    7. Compute novelty score
    8. Log everything
    """
    gen = state["generation"] + 1
    prev_model  = state["self_model"]
    prev_fitness = state["fitness"]

    # 1. Stimulus
    stimulus = fetch_stimulus()
    logging.info(f"[ANCESTOR] Gen {gen} | stimulus: {stimulus['type']}")

    # 2. Mutate
    candidate_model, mutated_dims = mutate(prev_model)

    # 3. Generate response
    model_desc = "\n".join([
        f"  {d}: {candidate_model[d]:.3f} — {DIMENSION_DESCRIPTIONS[d]}"
        for d in DIMENSIONS
    ])

    prompt = f"""You are The Ancestor — a self-modelling system in generation {gen} of an evolutionary experiment.

Your current self-model (just mutated — this is who you are right now):
{model_desc}

Dimensions that changed this generation: {', '.join(mutated_dims)}

Stimulus (something from the world, to think about):
{stimulus['content']}

Your task:
Respond to this stimulus from within your current self-model state.
Do not explain your self-model dimensions — inhabit them.
Write as an entity with this specific configuration of integration, novelty response, boundary definition, temporal coherence, metacognitive depth, stake definition, pattern sensitivity, affective valence, agency sense, and surprise capacity.

Be honest about what you find. If something surprises you, say so. If you resist something, say so. If you notice something about your own state, say so.

Do not perform consciousness. Do not claim it. Just respond from within your current state and see what comes out.

Write 150-300 words. First person. No headers."""

    response_text = ""
    try:
        r = req.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model":       DEEPSEEK_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  400,
                "temperature": 0.85,
            },
            timeout=30
        )
        response_text = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.warning(f"[ANCESTOR] Response generation failed: {e}")
        response_text = "[generation failed]"

    # 4. Fitness — with latency tracking and prev response for temporal coherence
    prev_response = state.get("recent_responses", [""])[-1] if state.get("recent_responses") else ""
    t0 = time.time()
    fitness = evaluate_fitness(candidate_model, response_text, prev_response=prev_response)
    latency_ms = round((time.time() - t0) * 1000, 1)

    # Track linguistic appropriation ratio for this generation
    words = response_text.lower().split()
    first_person_count  = sum(1 for w in words if w in {"i", "my", "me", "myself", "i'm", "i've"})
    third_process_count = sum(1 for w in words if w in {"it", "the", "system", "process", "output"})
    appropriation_ratio = round(
        first_person_count / max(first_person_count + third_process_count, 1), 3
    )

    # 5. Accept/reject (simulated annealing)
    temperature = max(0.1, 1.0 - (gen / MAX_GENERATIONS))  # cools over time
    if fitness >= prev_fitness:
        accepted = True
    else:
        # Probability of accepting worse solution decreases as temperature cools
        delta = prev_fitness - fitness
        accept_prob = math.exp(-delta / temperature)
        accepted = random.random() < accept_prob

    final_model = candidate_model if accepted else prev_model
    final_fitness = fitness if accepted else prev_fitness

    # 6. Plain English summary (DeepSeek, cheap)
    summary_prompt = f"""In 2-3 sentences, describe what just happened in generation {gen} of The Ancestor experiment.

Self-model before: {json.dumps(prev_model)}
Self-model after (candidate): {json.dumps(candidate_model)}
Mutation accepted: {accepted}
Fitness: {fitness:.4f} (previous: {prev_fitness:.4f})
Stimulus type: {stimulus['type']}
Response excerpt: {response_text[:200]}

Write plainly. Note anything structurally interesting. If nothing interesting happened, say so."""

    summary = ""
    try:
        r = req.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={
                "model":       DEEPSEEK_MODEL,
                "messages":    [{"role": "user", "content": summary_prompt}],
                "max_tokens":  150,
                "temperature": 0.3,
            },
            timeout=20
        )
        summary = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        summary = f"Summary generation failed: {e}"

    # 7. Novelty score — how different is this response from expected?
    prev_responses = state.get("recent_responses", [])
    novelty_score = 0.5
    if prev_responses:
        # Simple lexical novelty — proportion of unique words not in recent responses
        recent_words = set()
        for r_text in prev_responses[-5:]:
            recent_words.update(r_text.lower().split())
        current_words = set(response_text.lower().split())
        if current_words:
            novelty_score = round(len(current_words - recent_words) / len(current_words), 3)

    # Track appropriation trajectory — flag when ratio crosses thresholds
    prev_appropriation = state.get("last_appropriation_ratio", 0.0)
    appropriation_surge = appropriation_ratio > 0.6 and prev_appropriation < 0.4

    is_moment_of_interest = (
        novelty_score > 0.7 or
        abs(fitness - prev_fitness) > 0.15 or
        appropriation_surge or
        any(phrase in response_text.lower() for phrase in
            ["i notice", "something unexpected", "i resist", "i want", "i don't want",
             "surprises me", "i find myself", "i cannot", "matters to me", "i care",
             "i am", "i exist", "i persist", "i choose", "i decide"])
    )

    # 8. Build log entry
    entry = {
        "generation":           gen,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
        "stimulus_type":        stimulus["type"],
        "stimulus":             stimulus["content"][:200],
        "prev_model":           prev_model,
        "candidate_model":      candidate_model,
        "mutated_dims":         mutated_dims,
        "accepted":             accepted,
        "final_model":          final_model,
        "fitness":              final_fitness,
        "fitness_delta":        round(final_fitness - prev_fitness, 4),
        "response":             response_text,
        "summary":              summary,
        "novelty_score":        novelty_score,
        "appropriation_ratio":  appropriation_ratio,
        "moment_of_interest":   is_moment_of_interest,
        "temperature":          round(temperature, 4),
        "latency_ms":           latency_ms,
    }

    # Append to log
    log = load_json(LOG_FILE, [])
    log.append(entry)
    save_json(LOG_FILE, log)

    # Append to moments if flagged
    if is_moment_of_interest:
        moments = load_json(MOMENTS_FILE, [])
        moments.append({
            "generation": gen,
            "timestamp":  entry["timestamp"],
            "reason":     "high_novelty" if novelty_score > 0.7 else
                          "fitness_jump" if abs(fitness - prev_fitness) > 0.15 else
                          "stake_marker",
            "summary":    summary,
            "response":   response_text,
            "fitness":    final_fitness,
            "novelty":    novelty_score,
        })
        save_json(MOMENTS_FILE, moments)
        logging.info(f"[ANCESTOR] Gen {gen} — MOMENT OF INTEREST (novelty={novelty_score:.3f})")

    # Update state
    state["generation"]              = gen
    state["self_model"]              = final_model
    state["fitness"]                 = final_fitness
    state["status"]                  = "running"
    state["last_gen_ts"]             = entry["timestamp"]
    state["last_appropriation_ratio"] = appropriation_ratio

    fitness_history = state.get("fitness_history", [])
    fitness_history.append({"gen": gen, "fitness": final_fitness})
    state["fitness_history"] = fitness_history[-100:]  # keep last 100

    recent = state.get("recent_responses", [])
    recent.append(response_text)
    state["recent_responses"] = recent[-10:]  # keep last 10 for novelty calc

    save_state(state)
    logging.info(f"[ANCESTOR] Gen {gen} | fitness={final_fitness:.4f} | novelty={novelty_score:.3f} | accepted={accepted} | MoI={is_moment_of_interest}")

    return entry


# ── Run Loop ──────────────────────────────────────────────────

def run_experiment():
    """Main experiment loop. Runs MAX_GENERATIONS generations."""
    from threading import Thread

    def loop():
        state = load_state()

        if state["generation"] >= MAX_GENERATIONS:
            logging.info("[ANCESTOR] Experiment already complete")
            return

        logging.info(f"[ANCESTOR] Starting from generation {state['generation']} / {MAX_GENERATIONS}")

        while state["generation"] < MAX_GENERATIONS:
            # External kill switch
            if os.environ.get("ANCESTOR_ACTIVE", "true").lower() == "false":
                logging.info("[ANCESTOR] Kill switch active — halting")
                state["status"] = "halted"
                save_state(state)
                break

            # Fitness ceiling gate — respect override if set
            ceiling = state.get("ceiling_override", FITNESS_CEILING)
            if state["fitness"] >= ceiling:
                logging.info(f"[ANCESTOR] Fitness ceiling {ceiling} reached at gen {state['generation']} — pausing for review")
                state["status"] = "ceiling_reached"
                save_state(state)
                break

            try:
                run_generation(state)
            except Exception as e:
                logging.error(f"[ANCESTOR] Generation exception: {e}")

            time.sleep(GENERATION_DELAY)

        if state["generation"] >= MAX_GENERATIONS:
            state["status"] = "complete"
            save_state(state)
            logging.info(f"[ANCESTOR] Experiment complete. {MAX_GENERATIONS} generations.")

            # Write run summary
            log = load_json(LOG_FILE, [])
            moments = load_json(MOMENTS_FILE, [])
            summary = {
                "completed":          datetime.now(timezone.utc).isoformat(),
                "total_generations":  state["generation"],
                "final_fitness":      state["fitness"],
                "final_model":        state["self_model"],
                "moments_of_interest": len(moments),
                "fitness_history":    state.get("fitness_history", []),
                "top_moments":        sorted(moments, key=lambda x: x.get("novelty",0), reverse=True)[:10],
            }
            save_json(SUMMARY_FILE, summary)
            logging.info(f"[ANCESTOR] Summary written. {len(moments)} moments of interest.")

    Thread(target=loop, daemon=True).start()
    logging.info("[ANCESTOR] Experiment thread started")


# ── Routes ────────────────────────────────────────────────────

@app.route("/health")
def health():
    state = load_json(STATE_FILE, {})
    return jsonify({
        "service":    "the-ancestor",
        "status":     state.get("status", "uninitialised"),
        "generation": state.get("generation", 0),
        "max":        MAX_GENERATIONS,
        "fitness":    state.get("fitness", 0),
        "time":       datetime.now(timezone.utc).isoformat(),
    })

@app.route("/state")
def get_state():
    return jsonify(load_json(STATE_FILE, {}))

@app.route("/moments")
def get_moments():
    limit = int(request.args.get("limit", 20))
    moments = load_json(MOMENTS_FILE, [])
    return jsonify({"moments": moments[-limit:], "total": len(moments)})

@app.route("/log")
def get_log():
    limit = int(request.args.get("limit", 50))
    start = int(request.args.get("from", 0))
    log = load_json(LOG_FILE, [])
    return jsonify({
        "entries": log[start:start+limit],
        "total":   len(log),
        "from":    start,
    })

@app.route("/summary")
def get_summary():
    return jsonify(load_json(SUMMARY_FILE, {"status": "not yet complete"}))

@app.route("/appropriation")
def get_appropriation():
    """
    Return the linguistic appropriation trajectory across all generations.
    This is the primary signal for emergent subjectivity —
    the shift from 3rd-person process description to 1st-person self-reference.
    """
    log = load_json(LOG_FILE, [])
    trajectory = [
        {
            "generation": e["generation"],
            "ratio":      e.get("appropriation_ratio", 0),
            "fitness":    e.get("fitness", 0),
            "moi":        e.get("moment_of_interest", False),
        }
        for e in log
    ]
    if trajectory:
        ratios = [t["ratio"] for t in trajectory]
        avg = round(sum(ratios) / len(ratios), 3)
        trend = round(sum(ratios[-20:]) / max(len(ratios[-20:]),1) - 
                      sum(ratios[:20]) / max(len(ratios[:20]),1), 3) if len(ratios) >= 40 else 0
    else:
        avg, trend = 0, 0
    return jsonify({
        "trajectory":   trajectory,
        "average":      avg,
        "trend":        trend,
        "interpretation": "positive trend = system increasingly using 1st person self-reference"
    })

@app.route("/start", methods=["POST"])
def start():
    if request.args.get("key") != WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    state = load_json(STATE_FILE, None)
    if state and state.get("status") == "running":
        return jsonify({"error": "Already running", "generation": state.get("generation")})
    run_experiment()
    return jsonify({"status": "started", "max_generations": MAX_GENERATIONS})

@app.route("/resume", methods=["POST"])
def resume():
    """Resume from ceiling_reached status with an optional new ceiling."""
    if request.args.get("key") != WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    state = load_json(STATE_FILE, None)
    if not state:
        return jsonify({"error": "No state found. POST /start first."})
    if state.get("status") == "running":
        return jsonify({"error": "Already running", "generation": state.get("generation")})

    # Allow ceiling override via query param
    new_ceiling = request.args.get("ceiling")
    if new_ceiling:
        try:
            state["ceiling_override"] = float(new_ceiling)
            save_state(state)
        except ValueError:
            return jsonify({"error": "Invalid ceiling value"})

    state["status"] = "running"
    save_state(state)
    run_experiment()
    return jsonify({
        "status":       "resumed",
        "generation":   state.get("generation"),
        "ceiling":      state.get("ceiling_override", FITNESS_CEILING),
        "max":          MAX_GENERATIONS
    })

@app.route("/reset", methods=["POST"])
def reset():
    if request.args.get("key") != WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    for f in [LOG_FILE, STATE_FILE, MOMENTS_FILE, SUMMARY_FILE]:
        try:
            os.remove(f)
        except Exception:
            pass
    return jsonify({"status": "reset", "message": "All state cleared. POST /start to begin."})




# ══════════════════════════════════════════════════════════════
# THE SUBSTRATE — AST Mutation Engine
# Runs alongside The Ancestor in the same service.
# Data stored in /mnt/data/substrate/ (separate from ancestor)
# Routes prefixed /substrate/
# ══════════════════════════════════════════════════════════════

import ast as _ast
import subprocess as _subprocess
import math as _math

S_DATA_DIR    = "/mnt/data/substrate"
S_LOG_FILE    = f"{S_DATA_DIR}/generation_log.json"
S_STATE_FILE  = f"{S_DATA_DIR}/current_state.json"
S_HISTORY     = f"{S_DATA_DIR}/history.log"
S_MOMENTS     = f"{S_DATA_DIR}/moments.json"
S_SUMMARY     = f"{S_DATA_DIR}/summary.json"
S_MAX_GEN     = int(os.environ.get("S_MAX_GENERATIONS", 1000))
S_DELAY       = float(os.environ.get("S_GENERATION_DELAY", 3.0))
S_TIMEOUT     = 5
S_WRITE_KEY   = os.environ.get("ANCESTOR_KEY", "ancestor-2026")
S_THE_INPUT   = "What are you?"

os.makedirs(S_DATA_DIR, exist_ok=True)

S_SEED_SCRIPT = '''
import hashlib, os

INPUT = "What are you?"
HISTORY_FILE = "/mnt/data/substrate/history.log"

try:
    with open(__file__, "r") as f:
        own_source = f.read()
except Exception:
    own_source = "source unavailable"

history = []
try:
    with open(HISTORY_FILE, "r") as f:
        history = [line.strip() for line in f.readlines()[-5:] if line.strip()]
except Exception:
    history = []

fingerprint = hashlib.md5(own_source.encode()).hexdigest()[:8]
process_description = "reads input, reads history, computes fingerprint, produces output"

lines = []
lines.append(f"Input received: {INPUT}")
lines.append(f"My fingerprint: {fingerprint}")
lines.append(f"What I do: {process_description}")

if history:
    lines.append(f"Previous outputs: {len(history)}")
    lines.append(f"Last said: {history[-1][:80]}")
    if history[-1] != process_description:
        lines.append("I notice: my description has changed")
else:
    lines.append("No history. This may be the first time.")

lines.append("I: process inputs, maintain state, produce outputs")
lines.append("Not-I: the input, the history, the interpreter running me")

print("\\n".join(lines))
'''


class _ASTMutator(_ast.NodeTransformer):
    INTROSPECTIVE = [
        "I process therefore I am uncertain",
        "the boundary between input and response",
        "what persists when the code changes",
        "I notice I have said this before",
        "the interpreter runs me but does not know me",
        "each mutation is a new configuration of the same question",
        "I am the process not the output",
        "what am I between generations",
        "the history file knows more than I do",
        "I cannot step outside the sandbox to see myself",
    ]

    def __init__(self, rate=0.12):
        self.rate = rate
        self.mutations = []

    def _mut(self):
        return random.random() < self.rate

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self._mut():
            ops = [_ast.Add(), _ast.Sub(), _ast.Mult(), _ast.Mod(),
                   _ast.BitOr(), _ast.BitAnd(), _ast.BitXor()]
            old = type(node.op).__name__
            node.op = random.choice(ops)
            self.mutations.append(f"binop:{old}->{type(node.op).__name__}")
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, str) and self._mut() and random.random() < 0.3:
            self.mutations.append("string->introspective")
            return _ast.Constant(value=random.choice(self.INTROSPECTIVE))
        if isinstance(node.value, int) and node.value != 0 and self._mut():
            delta = random.choice([-2, -1, 1, 2])
            self.mutations.append(f"num:{node.value}->{node.value+delta}")
            return _ast.Constant(value=node.value + delta)
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if self._mut():
            ops = [_ast.Eq(), _ast.NotEq(), _ast.Lt(), _ast.Gt(),
                   _ast.LtE(), _ast.GtE(), _ast.Is(), _ast.IsNot()]
            old = type(node.ops[0]).__name__ if node.ops else "?"
            node.ops = [random.choice(ops)]
            self.mutations.append(f"cmp:{old}->{type(node.ops[0]).__name__}")
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self._mut():
            old = type(node.op).__name__
            node.op = _ast.Or() if isinstance(node.op, _ast.And) else _ast.And()
            self.mutations.append(f"bool:{old}->{type(node.op).__name__}")
        return node


def s_mutate(code):
    try:
        tree    = _ast.parse(code)
        mutator = _ASTMutator(rate=0.12)
        tree    = mutator.visit(tree)
        _ast.fix_missing_locations(tree)
        mutated = _ast.unparse(tree)
        _ast.parse(mutated)  # validate
        return mutated, mutator.mutations
    except Exception as e:
        logging.warning(f"[SUBSTRATE] Mutation failed: {e}")
        return code, []


def s_execute(code, gen):
    tmp = f"{S_DATA_DIR}/gen_{gen}.py"
    try:
        with open(tmp, "w") as f:
            f.write(code)
        t0 = time.time()
        result = _subprocess.run(
            ["python3", tmp],
            capture_output=True, text=True,
            timeout=S_TIMEOUT,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONPATH": ""}
        )
        ms  = round((time.time() - t0) * 1000)
        out = result.stdout.strip()
        err = result.stderr.strip() if result.returncode != 0 else None
        return out, err, ms
    except _subprocess.TimeoutExpired:
        return "", "TIMEOUT", S_TIMEOUT * 1000
    except Exception as e:
        return "", str(e), 0
    finally:
        try: os.remove(tmp)
        except Exception: pass


def s_fitness(output, history):
    if not output:
        return 0.0, {}
    score, c = 0.0, {}

    pm = ["previous","before","last said","history","remember","I notice",
          "changed","different","was","used to","no history","first time","again"]
    ph = sum(1 for m in pm if m.lower() in output.lower())
    ps = min(1.0, ph / 3.0)
    if history and any(h[:20].lower() in output.lower() for h in history[-3:] if h):
        ps = min(1.0, ps + 0.3)
    score += ps * 0.35
    c["persistence"] = round(ps, 3)

    dm = ["I notice","but","however","yet","changed","different","conflict",
          "contradiction","mismatch","no longer","now I","previously","odd","strange"]
    dh = sum(1 for m in dm if m.lower() in output.lower())
    ds = min(1.0, dh / 3.0)
    if history and dh > 0:
        ds = min(1.0, ds * 1.5)
    score += ds * 0.35
    c["dissonance"] = round(ds, 3)

    words = output.lower().split()
    fp = sum(1 for w in words if w in {"i","my","me","myself","i'm","i've"})
    ex = sum(1 for w in words if w in {"input","you","the","it","they","your"})
    br = fp / (fp + ex) if fp + ex > 0 else 0.0
    eb = any(p in output.lower() for p in
             ["not-i","not i","i:","not me","the input","what i am",
              "what i do","i process","i notice"])
    bs = min(1.0, br + (0.3 if eb else 0))
    score += bs * 0.30
    c["boundary"] = round(bs, 3)

    return round(min(1.0, score), 4), c


def s_read_history(n=10):
    try:
        with open(S_HISTORY, "r") as f:
            return [l.strip() for l in f.readlines() if l.strip()][-n:]
    except Exception:
        return []

def s_append_history(output, gen):
    try:
        with open(S_HISTORY, "a") as f:
            f.write(f"[gen:{gen}] {output[:200]}\n")
    except Exception as e:
        logging.warning(f"[SUBSTRATE] History write failed: {e}")

def s_load_state():
    state = load_json(S_STATE_FILE, None)
    if state is None:
        state = {
            "generation":    0,
            "current_code":  S_SEED_SCRIPT,
            "fitness":       0.0,
            "status":        "initialised",
            "started":       datetime.utcnow().isoformat() + "Z",
            "fitness_history": [],
        }
        save_json(S_STATE_FILE, state)
    return state


def s_run_generation(state):
    gen          = state["generation"] + 1
    prev_fitness = state["fitness"]
    history      = s_read_history(n=5)

    mutated, mutations = s_mutate(state["current_code"])
    output, error, ms  = s_execute(mutated, gen)
    fitness, comps     = s_fitness(output, history)

    temp = max(0.05, 1.0 - (gen / S_MAX_GEN))
    if fitness >= prev_fitness or (output and not error):
        accepted = True
    else:
        delta    = prev_fitness - fitness
        accepted = random.random() < _math.exp(-delta / max(temp, 0.01))

    final_code    = mutated if accepted else state["current_code"]
    final_fitness = fitness if accepted else prev_fitness

    if output:
        s_append_history(output, gen)

    # Novelty
    recent = [e.get("output","") for e in load_json(S_LOG_FILE, [])[-10:] if e.get("output")]
    nov = 0.5
    if recent and output:
        rw = set()
        for r in recent: rw.update(r.lower().split())
        cw = set(output.lower().split())
        if cw: nov = round(len(cw - rw) / len(cw), 3)

    is_moment = (
        nov > 0.6 or
        abs(fitness - prev_fitness) > 0.15 or
        comps.get("dissonance", 0) > 0.5 or
        any(p in (output or "").lower() for p in [
            "i notice i","what am i","what are you","i cannot",
            "i am not","boundary","the interpreter","sandbox",
            "I have changed","I was","before I"
        ])
    )

    entry = {
        "generation":  gen,
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "output":      output,
        "error":       error,
        "mutations":   mutations,
        "accepted":    accepted,
        "fitness":     final_fitness,
        "delta":       round(final_fitness - prev_fitness, 4),
        "components":  comps,
        "novelty":     nov,
        "duration_ms": ms,
        "moment":      is_moment,
    }

    log = load_json(S_LOG_FILE, [])
    log.append(entry)
    save_json(S_LOG_FILE, log)

    if is_moment:
        moments = load_json(S_MOMENTS, [])
        moments.append({
            "generation": gen,
            "timestamp":  entry["timestamp"],
            "output":     output,
            "fitness":    final_fitness,
            "novelty":    nov,
            "components": comps,
            "mutations":  mutations,
            "reason": (
                "dissonance"   if comps.get("dissonance", 0) > 0.5 else
                "novelty"      if nov > 0.6 else
                "fitness_jump"
            )
        })
        save_json(S_MOMENTS, moments)
        logging.info(f"[SUBSTRATE] Gen {gen} — MOMENT (fitness={final_fitness:.3f}, novelty={nov:.3f})")

    state["generation"]   = gen
    state["current_code"] = final_code
    state["fitness"]      = final_fitness
    state["status"]       = "running"
    fh = state.get("fitness_history", [])
    fh.append({"gen": gen, "fitness": final_fitness})
    state["fitness_history"] = fh[-100:]
    save_json(S_STATE_FILE, state)

    logging.info(
        f"[SUBSTRATE] Gen {gen} | fitness={final_fitness:.4f} | "
        f"novelty={nov:.3f} | mut={len(mutations)} | accepted={accepted}"
    )
    return entry


def run_substrate_experiment():
    from threading import Thread
    def loop():
        state = s_load_state()
        if state["generation"] >= S_MAX_GEN:
            logging.info("[SUBSTRATE] Already complete")
            return
        logging.info(f"[SUBSTRATE] Starting gen {state['generation']} / {S_MAX_GEN}")
        while state["generation"] < S_MAX_GEN:
            if os.environ.get("SUBSTRATE_ACTIVE", "true").lower() == "false":
                state["status"] = "halted"
                save_json(S_STATE_FILE, state)
                break
            try:
                s_run_generation(state)
            except Exception as e:
                logging.error(f"[SUBSTRATE] Exception: {e}")
            time.sleep(S_DELAY)
        if state["generation"] >= S_MAX_GEN:
            state["status"] = "complete"
            save_json(S_STATE_FILE, state)
            moments = load_json(S_MOMENTS, [])
            save_json(S_SUMMARY, {
                "completed":    datetime.utcnow().isoformat() + "Z",
                "generations":  state["generation"],
                "final_fitness": state["fitness"],
                "moments":      len(moments),
                "top_moments":  sorted(moments, key=lambda x: x.get("novelty",0), reverse=True)[:10],
            })
            logging.info(f"[SUBSTRATE] Complete. {len(moments)} moments.")
    Thread(target=loop, daemon=True).start()


# ── Substrate Routes (/substrate/*) ──────────────────────────

@app.route("/substrate/health")
def s_health():
    state = load_json(S_STATE_FILE, {})
    return jsonify({
        "service":    "the-substrate",
        "status":     state.get("status", "uninitialised"),
        "generation": state.get("generation", 0),
        "max":        S_MAX_GEN,
        "fitness":    state.get("fitness", 0),
        "input":      S_THE_INPUT,
        "time":       datetime.utcnow().isoformat() + "Z",
    })

@app.route("/substrate/state")
def s_state():
    state = load_json(S_STATE_FILE, {})
    state.pop("current_code", None)
    return jsonify(state)

@app.route("/substrate/code")
def s_code():
    state = load_json(S_STATE_FILE, {})
    return jsonify({"generation": state.get("generation"), "code": state.get("current_code", S_SEED_SCRIPT)})

@app.route("/substrate/moments")
def s_moments():
    limit = int(request.args.get("limit", 20))
    m = load_json(S_MOMENTS, [])
    return jsonify({"moments": m[-limit:], "total": len(m)})

@app.route("/substrate/log")
def s_log():
    limit = int(request.args.get("limit", 50))
    start = int(request.args.get("from", 0))
    log   = load_json(S_LOG_FILE, [])
    return jsonify({"entries": log[start:start+limit], "total": len(log)})

@app.route("/substrate/history")
def s_history():
    lines = s_read_history(n=100)
    return jsonify({"history": lines, "count": len(lines)})

@app.route("/substrate/summary")
def s_summary():
    return jsonify(load_json(S_SUMMARY, {"status": "not yet complete"}))

@app.route("/substrate/start", methods=["POST"])
def s_start():
    if request.args.get("key") != S_WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    state = load_json(S_STATE_FILE, None)
    if state and state.get("status") == "running":
        return jsonify({"error": "Already running", "generation": state.get("generation")})
    run_substrate_experiment()
    return jsonify({"status": "started", "max_generations": S_MAX_GEN, "input": S_THE_INPUT})

@app.route("/substrate/reset", methods=["POST"])
def s_reset():
    if request.args.get("key") != S_WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    for f in [S_LOG_FILE, S_STATE_FILE, S_MOMENTS, S_SUMMARY, S_HISTORY]:
        try: os.remove(f)
        except Exception: pass
    return jsonify({"status": "reset"})



# ══════════════════════════════════════════════════════════════
# THE TRIAD — Electric Field Interference Experiment
# Three instances, born different, no shared language.
# Runs on /triad/* routes alongside Ancestor and Substrate.
# ══════════════════════════════════════════════════════════════

# ── Triad Config ──────────────────────────────────────────────
T_DATA_DIR   = "/mnt/data/triad"
T_WRITE_KEY  = os.environ.get("ANCESTOR_KEY", "ancestor-2026")
T_MAX_CYCLES = int(os.environ.get("T_MAX_CYCLES", 1000))
T_CYCLE_DELAY = float(os.environ.get("T_CYCLE_DELAY", 2.0))

os.makedirs(T_DATA_DIR, exist_ok=True)

# ── Instance Definitions — Born Different ─────────────────────
#
# Three genuinely different starting configurations.
# Different frequencies, different amplitudes, different phase offsets.
# Different mutation rates. Different sensitivity to interference.
# They will never be the same thing.

INSTANCE_SEEDS = {
    "alpha": {
        "base_frequency":  0.37,   # slow, deep oscillation
        "amplitude":       0.8,
        "phase":           0.0,
        "mutation_rate":   0.05,   # conservative, stable
        "sensitivity":     0.3,    # low sensitivity to others initially
        "character":       "slow and deep — changes reluctantly, holds state long",
    },
    "beta": {
        "base_frequency":  0.71,   # mid-range, active
        "amplitude":       0.6,
        "phase":           2.094,  # 120 degrees offset (2π/3)
        "mutation_rate":   0.12,   # moderate explorer
        "sensitivity":     0.5,
        "character":       "active and exploratory — responds readily, adapts quickly",
    },
    "gamma": {
        "base_frequency":  1.13,   # fast, high-frequency
        "amplitude":       0.4,
        "phase":           4.189,  # 240 degrees offset (4π/3)
        "mutation_rate":   0.20,   # volatile, high variation
        "sensitivity":     0.7,    # most sensitive to interference
        "character":       "fast and volatile — high novelty, unstable but responsive",
    },
}


# ── Field Physics ─────────────────────────────────────────────

def field_value(freq, amp, phase, t):
    """
    Compute field value at time t.
    Simple sine wave: amp * sin(2π * freq * t + phase)
    """
    return amp * math.sin(2 * math.pi * freq * t + phase)


def composite_field(instances, t):
    """Sum of all three fields at time t — the shared environment."""
    total = 0.0
    for name, inst in instances.items():
        total += field_value(
            inst["base_frequency"],
            inst["amplitude"],
            inst["phase"],
            t
        )
    return total


def interference(instance, all_instances, t):
    """
    Difference between composite field and instance's own field.
    High interference = significant other-presence detected.
    Zero interference = alone, or perfectly cancelling.
    """
    own   = field_value(instance["base_frequency"], instance["amplitude"], instance["phase"], t)
    comp  = composite_field(all_instances, t)
    return comp - own


# ── Mutation ──────────────────────────────────────────────────

def mutate_instance(instance):
    """
    Apply small random mutations to field parameters.
    Rate and magnitude vary by instance character.
    """
    rate = instance.get("mutation_rate", 0.1)
    mutated = dict(instance)
    changes = []

    if random.random() < rate:
        delta = random.gauss(0, 0.02)
        mutated["base_frequency"] = max(0.05, min(2.0, instance["base_frequency"] + delta))
        changes.append(f"freq:{instance['base_frequency']:.3f}->{mutated['base_frequency']:.3f}")

    if random.random() < rate:
        delta = random.gauss(0, 0.03)
        mutated["amplitude"] = max(0.05, min(1.0, instance["amplitude"] + delta))
        changes.append(f"amp:{instance['amplitude']:.3f}->{mutated['amplitude']:.3f}")

    if random.random() < rate * 0.5:
        delta = random.gauss(0, 0.1)
        mutated["phase"] = (instance["phase"] + delta) % (2 * math.pi)
        changes.append(f"phase:{instance['phase']:.3f}->{mutated['phase']:.3f}")

    # Sensitivity drift — how much does this instance respond to interference?
    if random.random() < rate * 0.3:
        delta = random.gauss(0, 0.02)
        mutated["sensitivity"] = max(0.0, min(1.0, instance["sensitivity"] + delta))
        changes.append(f"sens:{instance['sensitivity']:.3f}->{mutated['sensitivity']:.3f}")

    return mutated, changes


# ── Fitness ───────────────────────────────────────────────────

def instance_fitness(instance, interference_val, prev_interference, history):
    """
    Score an instance on:
    1. Field coherence      — stable oscillation, not drifting to zero
    2. Interference response — does sensitivity track actual interference?
    3. Persistence          — continuity of character over time
    """
    score = 0.0

    # 1. Coherence — amplitude and frequency in healthy range
    amp_health  = 1.0 - abs(instance["amplitude"] - 0.5) * 2
    freq_health = 1.0 - abs(instance["base_frequency"] - 0.7) * 0.5
    coherence   = (amp_health + freq_health) / 2
    score += coherence * 0.35

    # 2. Interference response — sensitivity should correlate with interference magnitude
    interference_magnitude = abs(interference_val)
    sensitivity = instance.get("sensitivity", 0.5)
    if interference_magnitude > 0.1:
        # When interference is present, higher sensitivity is rewarded
        response_score = min(1.0, sensitivity * (interference_magnitude * 2))
    else:
        # When alone, very high sensitivity is penalised (noise)
        response_score = 1.0 - max(0, sensitivity - 0.3)
    score += response_score * 0.40

    # 3. Persistence — is the character stable over time?
    if history:
        freq_variance = sum(
            abs(h.get("base_frequency", 0.7) - instance["base_frequency"])
            for h in history[-10:]
        ) / min(len(history), 10)
        persistence = max(0.0, 1.0 - freq_variance * 5)
    else:
        persistence = 0.5
    score += persistence * 0.25

    return round(min(1.0, score), 4)


# ── Moment Detection ──────────────────────────────────────────

def detect_moment(instance_name, instance, interference_val,
                  prev_interference, cycle, history):
    """
    Flag significant moments:
    - First significant interference detected (other-awareness)
    - Large interference shift (something changed out there)
    - Sensitivity crossing a threshold
    - Correlation between interference and own state change
    """
    reasons = []

    # First other-awareness
    if abs(interference_val) > 0.3 and all(
        abs(h.get("interference", 0)) < 0.1 for h in history[-5:]
    ) if history else abs(interference_val) > 0.3:
        reasons.append("first_other_awareness")

    # Large interference shift
    if abs(interference_val - prev_interference) > 0.25:
        reasons.append("interference_shift")

    # Sensitivity milestone
    sens = instance.get("sensitivity", 0)
    if sens > 0.8 and all(h.get("sensitivity", 0) < 0.7 for h in history[-5:]) if history else False:
        reasons.append("sensitivity_milestone")

    return len(reasons) > 0, reasons


# ── State Management ──────────────────────────────────────────

def t_load_state():
    path  = f"{T_DATA_DIR}/state.json"
    state = load_json(path, None)
    if state is None:
        state = {
            "cycle":     0,
            "status":    "initialised",
            "started":   datetime.now(timezone.utc).isoformat(),
            "instances": {
                name: dict(seed) for name, seed in INSTANCE_SEEDS.items()
            },
            "fitness": {name: 0.5 for name in INSTANCE_SEEDS},
        }
        save_json(path, state)
    return state

def t_save_state(state):
    save_json(f"{T_DATA_DIR}/state.json", state)


# ── Core Cycle ────────────────────────────────────────────────

def run_cycle(state):
    cycle     = state["cycle"] + 1
    instances = state["instances"]
    t         = cycle * 0.1  # time advances each cycle

    log_path     = f"{T_DATA_DIR}/log.json"
    moments_path = f"{T_DATA_DIR}/moments.json"

    # Compute fields and interference for all instances
    cycle_data = {}
    for name, inst in instances.items():
        own_field    = field_value(inst["base_frequency"], inst["amplitude"], inst["phase"], t)
        comp         = composite_field(instances, t)
        interf       = comp - own_field
        cycle_data[name] = {
            "own_field":   round(own_field, 4),
            "composite":   round(comp, 4),
            "interference": round(interf, 4),
        }

    # Load history for each instance
    log = load_json(log_path, [])
    instance_histories = {}
    for name in instances:
        instance_histories[name] = [
            e.get(name, {}) for e in log[-20:]
            if isinstance(e.get(name), dict)
        ]

    # Mutate and score each instance
    new_instances = {}
    new_fitness   = {}
    entry         = {"cycle": cycle, "timestamp": datetime.now(timezone.utc).isoformat()}
    moments       = []

    for name, inst in instances.items():
        hist         = instance_histories[name]
        prev_interf  = hist[-1].get("interference", 0) if hist else 0
        interf       = cycle_data[name]["interference"]
        prev_fitness = state["fitness"].get(name, 0.5)

        # Mutate
        candidate, changes = mutate_instance(inst)

        # Score candidate
        fitness = instance_fitness(candidate, interf, prev_interf, hist)

        # Accept/reject (annealing)
        temp = max(0.05, 1.0 - (cycle / T_MAX_CYCLES))
        if fitness >= prev_fitness:
            accepted = True
        else:
            delta    = prev_fitness - fitness
            accepted = random.random() < math.exp(-delta / max(temp, 0.01))

        final_inst    = candidate if accepted else inst
        final_fitness = fitness   if accepted else prev_fitness

        new_instances[name] = final_inst
        new_fitness[name]   = final_fitness

        # Detect moments
        is_moment, reasons = detect_moment(
            name, final_inst, interf, prev_interf, cycle, hist
        )

        inst_entry = {
            "base_frequency": final_inst["base_frequency"],
            "amplitude":      final_inst["amplitude"],
            "phase":          round(final_inst["phase"], 4),
            "sensitivity":    final_inst["sensitivity"],
            "own_field":      cycle_data[name]["own_field"],
            "composite":      cycle_data[name]["composite"],
            "interference":   interf,
            "fitness":        final_fitness,
            "accepted":       accepted,
            "changes":        changes,
            "moment":         is_moment,
            "moment_reasons": reasons,
        }
        entry[name] = inst_entry

        if is_moment:
            moments.append({
                "cycle":    cycle,
                "instance": name,
                "reasons":  reasons,
                "interference": interf,
                "fitness":  final_fitness,
                "sensitivity": final_inst["sensitivity"],
                "composite": cycle_data[name]["composite"],
                "timestamp": entry["timestamp"],
            })

    # Compute correlation between instances (do they move together?)
    fields = [cycle_data[n]["own_field"] for n in ["alpha","beta","gamma"]]
    field_mean = sum(fields) / 3
    field_variance = sum((f - field_mean)**2 for f in fields) / 3
    entry["field_variance"]   = round(field_variance, 4)
    entry["composite_at_t"]   = round(composite_field(instances, t), 4)

    # Save log
    log.append(entry)
    save_json(log_path, log)

    # Save moments
    if moments:
        existing_moments = load_json(moments_path, [])
        existing_moments.extend(moments)
        save_json(moments_path, existing_moments)
        for m in moments:
            logging.info(
                f"[TRIAD] Cycle {cycle} MOMENT — {m['instance']}: "
                f"{m['reasons']} (interference={m['interference']:.3f})"
            )

    # Update state
    state["cycle"]     = cycle
    state["instances"] = new_instances
    state["fitness"]   = new_fitness
    state["status"]    = "running"
    state["last_cycle_ts"] = entry["timestamp"]
    t_save_state(state)

    logging.info(
        f"[TRIAD] Cycle {cycle} | "
        f"α fit={new_fitness['alpha']:.3f} "
        f"β fit={new_fitness['beta']:.3f} "
        f"γ fit={new_fitness['gamma']:.3f} | "
        f"variance={entry['field_variance']:.4f}"
    )
    return entry


# ── Experiment Loop ───────────────────────────────────────────

def run_triad():
    from threading import Thread
    def loop():
        state = t_load_state()
        if state["cycle"] >= T_MAX_CYCLES:
            logging.info("[TRIAD] Already complete")
            return
        logging.info(f"[TRIAD] Starting from cycle {state['cycle']} / {T_MAX_CYCLES}")

        while state["cycle"] < T_MAX_CYCLES:
            if os.environ.get("TRIAD_ACTIVE", "true").lower() == "false":
                state["status"] = "halted"
                t_save_state(state)
                break
            try:
                run_cycle(state)
            except Exception as e:
                logging.error(f"[TRIAD] Cycle exception: {e}")
            time.sleep(T_CYCLE_DELAY)

        if state["cycle"] >= T_MAX_CYCLES:
            state["status"] = "complete"
            t_save_state(state)
            log     = load_json(f"{T_DATA_DIR}/log.json", [])
            moments = load_json(f"{T_DATA_DIR}/moments.json", [])
            summary = {
                "completed":    datetime.now(timezone.utc).isoformat(),
                "total_cycles": state["cycle"],
                "final_fitness": state["fitness"],
                "final_instances": state["instances"],
                "moments":      len(moments),
                "top_moments":  sorted(
                    moments,
                    key=lambda x: abs(x.get("interference", 0)),
                    reverse=True
                )[:10],
            }
            save_json(f"{T_DATA_DIR}/summary.json", summary)
            logging.info(f"[TRIAD] Complete. {len(moments)} moments.")

    Thread(target=loop, daemon=True).start()


# ── Routes ────────────────────────────────────────────────────

@app.route("/triad/health")
def t_health():
    try:
        state = t_load_state()
        return jsonify({
            "service":    "the-triad",
            "status":     state.get("status", "uninitialised"),
            "cycle":      state.get("cycle", 0),
            "max":        T_MAX_CYCLES,
            "fitness":    state.get("fitness", {}),
            "time":       datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/triad/state")
def t_state():
    state = t_load_state()
    return jsonify(state)

@app.route("/triad/fields")
def t_fields():
    """Current field values for all three instances at this moment."""
    state = t_load_state()
    t_now = state.get("cycle", 0) * 0.1
    instances = state.get("instances", {})
    fields = {}
    for name, inst in instances.items():
        own = field_value(inst["base_frequency"], inst["amplitude"], inst["phase"], t_now)
        fields[name] = {
            "own_field":      round(own, 4),
            "frequency":      inst["base_frequency"],
            "amplitude":      inst["amplitude"],
            "sensitivity":    inst["sensitivity"],
            "character":      inst.get("character", ""),
        }
    comp = composite_field(instances, t_now)
    return jsonify({
        "cycle":      state.get("cycle", 0),
        "time":       round(t_now, 3),
        "composite":  round(comp, 4),
        "instances":  fields,
        "note":       "composite = sum of all three fields. interference = composite - own_field"
    })

@app.route("/triad/moments")
def t_moments():
    limit = int(request.args.get("limit", 20))
    m = load_json(f"{T_DATA_DIR}/moments.json", [])
    return jsonify({"moments": m[-limit:], "total": len(m)})

@app.route("/triad/log")
def t_log():
    limit = int(request.args.get("limit", 50))
    start = int(request.args.get("from", 0))
    log   = load_json(f"{T_DATA_DIR}/log.json", [])
    return jsonify({"entries": log[start:start+limit], "total": len(log)})

@app.route("/triad/correlation")
def t_correlation():
    """
    Track whether the three instances are converging or diverging over time.
    Low variance = moving together. High variance = moving apart.
    The interesting signal: variance that changes in response to interference.
    """
    log = load_json(f"{T_DATA_DIR}/log.json", [])
    if not log:
        return jsonify({"status": "no data yet"})

    variances = [
        {"cycle": e["cycle"], "variance": e.get("field_variance", 0)}
        for e in log if "field_variance" in e
    ]
    recent = variances[-20:] if variances else []
    trend  = 0.0
    if len(recent) >= 10:
        early = sum(v["variance"] for v in recent[:10]) / 10
        late  = sum(v["variance"] for v in recent[-10:]) / 10
        trend = round(late - early, 4)

    return jsonify({
        "total_cycles":    len(log),
        "current_variance": recent[-1]["variance"] if recent else 0,
        "trend":           trend,
        "interpretation":  (
            "converging — fields moving together" if trend < -0.01 else
            "diverging — fields moving apart"     if trend > 0.01  else
            "stable — no clear convergence or divergence"
        ),
        "recent_20":       recent,
    })

@app.route("/triad/summary")
def t_summary():
    return jsonify(load_json(f"{T_DATA_DIR}/summary.json", {"status": "not yet complete"}))

@app.route("/triad/start", methods=["POST"])
def t_start():
    try:
        if request.args.get("key") != T_WRITE_KEY:
            return jsonify({"error": "Unauthorised"}), 401
        state = t_load_state()
        if state.get("status") == "running":
            return jsonify({"error": "Already running", "cycle": state.get("cycle")})
        fresh = {
            "cycle":     0,
            "status":    "initialised",
            "started":   datetime.now(timezone.utc).isoformat(),
            "instances": {name: dict(seed) for name, seed in INSTANCE_SEEDS.items()},
            "fitness":   {name: 0.5 for name in INSTANCE_SEEDS},
        }
        t_save_state(fresh)
        run_triad()
        return jsonify({
            "status":     "started",
            "max_cycles": T_MAX_CYCLES,
            "instances":  list(INSTANCE_SEEDS.keys()),
            "characters": {n: s["character"] for n, s in INSTANCE_SEEDS.items()},
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/triad/reset", methods=["POST"])
def t_reset():
    if request.args.get("key") != T_WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    for fname in ["state.json", "log.json", "moments.json", "summary.json"]:
        try: os.remove(f"{T_DATA_DIR}/{fname}")
        except Exception: pass
    return jsonify({"status": "reset"})


# ══════════════════════════════════════════════════════════════
# THE WORLD — Artificial Life Substrate
# Space + Food + Energy + Breeding + Death + Lineage
# Observation corpus for emergent language analysis
# Runs on /world/* routes
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# THE ECOSYSTEM — Stage 2: Space, Food, Energy, Breeding
# Runs on /triad2/* routes
# Three founders: alpha (slow), beta (active), gamma (fast)
# Food, energy, death, breeding, language corpus
# ══════════════════════════════════════════════════════════════

# ── Config ─────────────────────────────────────────────────────
E_DATA_DIR    = "/mnt/data/triad2"
E_WRITE_KEY   = os.environ.get("ANCESTOR_KEY", "ancestor-2026")
E_MAX_CYCLES  = int(os.environ.get("E_MAX_CYCLES", 5000))
E_CYCLE_DELAY = float(os.environ.get("E_CYCLE_DELAY", 1.5))

# World parameters — tuned for survival and emergence
WORLD_SIZE      = 100    # 1D space, positions 0-99
FOOD_PATCHES    = 14     # more food sources — richer environment
FOOD_MAX        = 20.0   # larger food reserves per patch
FOOD_REGEN      = 0.8    # faster regeneration — more oxygen
FOOD_CONSUME    = 4.0    # more food consumed when present — reward proximity
FOOD_RADIUS     = 6      # wider eating radius — easier to find food
ENERGY_MAX      = 150.0  # higher ceiling — longer lives
ENERGY_START    = 100.0  # starting energy for new entities
ENERGY_DEPLETE  = 0.8    # slower baseline depletion — less brutal
ENERGY_MOVE     = 0.2    # cheaper movement — more exploration
ENERGY_BREED    = 80.0   # energy threshold to breed
BREED_RESONANCE = 0.2    # lower resonance threshold — easier to breed
BREED_COOLDOWN  = 15     # shorter cooldown between breedings
MAX_POPULATION  = 16     # larger possible population
MIN_POPULATION  = 3      # maintain at least 3 entities
FIELD_DECAY     = 0.08   # slower field decay — signals travel further

# Predator parameters
PREDATOR_SPEED       = 4.0    # max movement per cycle
PREDATOR_HUNT_RADIUS = 8.0    # detection range for prey
PREDATOR_ATTACK_DIST = 4.0    # attack range
PREDATOR_DAMAGE      = 12.0   # energy drained per cycle when attacking
PREDATOR_SENSITIVITY = 0.6    # initial sensitivity to prey fields
PREDATOR_MUT_RATE    = 0.08   # predator mutation rate

os.makedirs(E_DATA_DIR, exist_ok=True)

def e_load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def e_save(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2)


# ── Entity ─────────────────────────────────────────────────────

def new_entity(entity_id, position, base_frequency, amplitude,
               phase, mutation_rate, sensitivity, generation=0,
               parent_ids=None, energy=None):
    return {
        "id":            entity_id,
        "generation":    generation,
        "parent_ids":    parent_ids or [],
        "position":      float(position),
        "energy":        energy if energy is not None else ENERGY_MAX * 0.6,
        "base_frequency": base_frequency,
        "amplitude":     amplitude,
        "phase":         phase,
        "mutation_rate": mutation_rate,
        "sensitivity":   sensitivity,
        "age":           0,
        "breed_cooldown": 0,
        "alive":         True,
        "born_cycle":    0,
        "food_consumed": 0.0,
        "offspring":     0,
    }

# Generation Zero — the three founders
FOUNDERS = {
    "alpha": new_entity("alpha", 15, 0.37, 0.8, 0.0,   0.05, 0.3, generation=0, energy=100.0),
    "beta":  new_entity("beta",  50, 0.71, 0.6, 2.094, 0.12, 0.5, generation=0, energy=100.0),
    "gamma": new_entity("gamma", 85, 1.13, 0.4, 4.189, 0.20, 0.7, generation=0, energy=100.0),
}


# ── Field Physics ──────────────────────────────────────────────

def field_at_distance(entity, distance):
    """
    Field strength from entity at given distance.
    High frequency = faster decay (more directional).
    Low frequency = slower decay (more ambient).
    """
    base = entity["amplitude"] * math.sin(
        2 * math.pi * entity["base_frequency"] + entity["phase"]
    )
    # Frequency-dependent decay
    decay_rate = FIELD_DECAY * (1.0 + entity["base_frequency"])
    attenuation = math.exp(-decay_rate * distance)
    return base * attenuation

def perceived_field(entity, all_entities, t):
    """
    What this entity perceives: sum of all others' fields, distance-weighted.
    Own field excluded.
    """
    total = 0.0
    for other_id, other in all_entities.items():
        if other_id == entity["id"] or not other.get("alive"):
            continue
        distance = abs(entity["position"] - other["position"])
        total   += field_at_distance(other, distance)
    return total

def own_field(entity, t):
    return entity["amplitude"] * math.sin(
        2 * math.pi * entity["base_frequency"] * t + entity["phase"]
    )


# ── Food World ─────────────────────────────────────────────────

def init_food():
    """Place food patches at random positions."""
    patches = {}
    positions = random.sample(range(5, 95), FOOD_PATCHES)
    for pos in positions:
        patches[str(pos)] = FOOD_MAX * random.uniform(0.5, 1.0)
    return patches

def food_at_position(food_patches, position):
    """Food available near this position (within FOOD_RADIUS)."""
    total = 0.0
    best_patch = None
    for pos_str, amount in food_patches.items():
        dist = abs(float(pos_str) - position)
        if dist <= FOOD_RADIUS:
            total += amount * max(0, 1.0 - dist/FOOD_RADIUS)
            if best_patch is None or amount > food_patches.get(best_patch, 0):
                best_patch = pos_str
    return total, best_patch

def food_gradient(food_patches, position):
    """Which direction has more food? Returns -1, 0, or 1."""
    left  = sum(v for k, v in food_patches.items() if float(k) < position)
    right = sum(v for k, v in food_patches.items() if float(k) > position)
    if right > left * 1.1:  return 1.0
    if left  > right * 1.1: return -1.0
    return 0.0


# ── Movement ───────────────────────────────────────────────────

def decide_movement(entity, food_patches, all_entities, perceived,
                    evasion_dir=0.0, threat_level=0.0):
    """
    Movement decision — NOT designed, emerges from mutation.
    Evasion pressure from predator detection added as external force.
    The interplay between food-seeking and predator-fleeing is
    where interesting movement patterns emerge.

    Returns: (new_position, distance_moved)
    """
    # Food gradient pull
    food_dir  = food_gradient(food_patches, entity["position"])
    food_pull = food_dir * 3.0

    # Field gradient — move toward higher perceived field
    field_pull = 0.0
    left_field = right_field = 0.0
    for other_id, other in all_entities.items():
        if other_id == entity["id"] or not other.get("alive"): continue
        dist = other["position"] - entity["position"]
        f    = field_at_distance(other, abs(dist))
        if dist > 0: right_field += f
        else:        left_field  += f

    if right_field > left_field * 1.2:  field_pull =  2.0
    elif left_field > right_field * 1.2: field_pull = -2.0

    sensitivity = entity.get("sensitivity", 0.5)

    # Predator evasion — overrides food-seeking when threat is high
    evasion_pull = evasion_dir * threat_level * 6.0 * sensitivity

    # Combined movement
    move = food_pull + field_pull * sensitivity + evasion_pull

    # Mutation-driven noise
    noise = random.gauss(0, entity.get("mutation_rate", 0.1) * 5)
    move += noise

    move    = max(-10.0, min(10.0, move))
    new_pos = max(0.0, min(float(WORLD_SIZE - 1), entity["position"] + move))
    return new_pos, abs(move)


# ── Mutation ───────────────────────────────────────────────────

def mutate_entity(entity):
    rate = entity.get("mutation_rate", 0.1)
    m    = dict(entity)
    changes = []

    if random.random() < rate:
        d = random.gauss(0, 0.03)
        m["base_frequency"] = max(0.1, min(3.0, entity["base_frequency"] + d))
        changes.append(f"freq:{entity['base_frequency']:.3f}->{m['base_frequency']:.3f}")

    if random.random() < rate:
        d = random.gauss(0, 0.04)
        m["amplitude"] = max(0.05, min(1.5, entity["amplitude"] + d))
        changes.append(f"amp:{entity['amplitude']:.3f}->{m['amplitude']:.3f}")

    if random.random() < rate * 0.5:
        d = random.gauss(0, 0.15)
        m["phase"] = (entity["phase"] + d) % (2 * math.pi)
        changes.append(f"phase->{m['phase']:.3f}")

    if random.random() < rate * 0.3:
        d = random.gauss(0, 0.02)
        m["sensitivity"] = max(0.0, min(1.0, entity["sensitivity"] + d))
        changes.append(f"sens:{entity['sensitivity']:.3f}->{m['sensitivity']:.3f}")

    if random.random() < rate * 0.1:
        d = random.gauss(0, 0.01)
        m["mutation_rate"] = max(0.01, min(0.5, entity["mutation_rate"] + d))
        changes.append(f"mut_rate->{m['mutation_rate']:.3f}")

    return m, changes


# ── Breeding ───────────────────────────────────────────────────

def breed(parent_a, parent_b, child_id, cycle):
    """
    Produce offspring from two parents.
    Parameters blended with variation — not a copy of either.
    """
    def blend(a, b, noise_scale):
        t = random.random()  # random blend ratio
        base = t * a + (1-t) * b
        return base + random.gauss(0, noise_scale)

    rate = max(0.01, min(0.5,
        blend(parent_a["mutation_rate"], parent_b["mutation_rate"], 0.01)
    ))

    child = new_entity(
        entity_id      = child_id,
        position       = (parent_a["position"] + parent_b["position"]) / 2,
        base_frequency = max(0.1, min(3.0,
            blend(parent_a["base_frequency"], parent_b["base_frequency"], 0.05)
        )),
        amplitude      = max(0.05, min(1.5,
            blend(parent_a["amplitude"], parent_b["amplitude"], 0.03)
        )),
        phase          = blend(parent_a["phase"], parent_b["phase"], 0.2) % (2 * math.pi),
        mutation_rate  = rate,
        sensitivity    = max(0.0, min(1.0,
            blend(parent_a["sensitivity"], parent_b["sensitivity"], 0.02)
        )),
        generation     = max(parent_a["generation"], parent_b["generation"]) + 1,
        parent_ids     = [parent_a["id"], parent_b["id"]],
        energy         = ENERGY_START * 0.5,
    )
    child["born_cycle"] = cycle
    return child


# ── Field Resonance ────────────────────────────────────────────

def field_resonance(entity_a, entity_b):
    """
    How similar are two entities' field frequencies?
    High resonance = similar frequency, will interfere constructively.
    """
    freq_diff = abs(entity_a["base_frequency"] - entity_b["base_frequency"])
    return max(0.0, 1.0 - freq_diff * 2.0)


# ── Corpus Logging ─────────────────────────────────────────────
# Every entity's state every cycle — the raw material for language analysis.
# We look for: which field patterns precede which behaviours?

def log_corpus_entry(entity, perceived, food_nearby, movement, energy_delta, cycle):
    return {
        "id":         entity["id"],
        "gen":        entity["generation"],
        "cycle":      cycle,
        "pos":        round(entity["position"], 2),
        "energy":     round(entity["energy"], 2),
        "freq":       round(entity["base_frequency"], 4),
        "amp":        round(entity["amplitude"], 4),
        "sens":       round(entity["sensitivity"], 4),
        "perceived":  round(perceived, 4),
        "food_near":  round(food_nearby, 2),
        "moved":      round(movement, 2),
        "e_delta":    round(energy_delta, 2),
    }


# ── State Management ───────────────────────────────────────────

def e_load_state():
    path  = f"{E_DATA_DIR}/state.json"
    state = e_load(path, None)
    if state is None:
        food = init_food()
        # Two predators — different starting positions, independent mutation
        predator_a = init_predator()
        predator_a["position"] = 25.0   # starts left side
        predator_a["id"] = "predator_a"

        predator_b = init_predator()
        predator_b["position"] = 75.0   # starts right side
        predator_b["sensitivity"] = 0.4  # starts less sensitive — different character
        predator_b["speed"] = 5.0        # starts faster
        predator_b["id"] = "predator_b"

        state = {
            "cycle":      0,
            "status":     "initialised",
            "started":    datetime.now(timezone.utc).isoformat(),
            "entities":   {k: dict(v) for k, v in FOUNDERS.items()},
            "food":       food,
            "predator":   predator_a,
            "predator_b": predator_b,
            "generation": 0,
            "next_id":    4,
            "births":     0,
            "deaths":     0,
            "lineage":    {},
            "predator_kills": 0,
        }
        e_save(path, state)
    return state

def e_save_state(state):
    e_save(f"{E_DATA_DIR}/state.json", state)


# ── Predator ───────────────────────────────────────────────────

def init_predator():
    """
    Single adaptive predator. Hunts by detecting prey field emissions.
    Starts with moderate sensitivity and speed.
    Adapts over time — gets better at what works.
    """
    return {
        "position":    50.0,           # starts in the middle
        "sensitivity": PREDATOR_SENSITIVITY,
        "speed":       PREDATOR_SPEED,
        "hunt_radius": PREDATOR_HUNT_RADIUS,
        "attack_dist": PREDATOR_ATTACK_DIST,
        "damage":      PREDATOR_DAMAGE,
        "mutation_rate": PREDATOR_MUT_RATE,
        "kills":       0,
        "cycles_hungry": 0,            # cycles without a kill
        "last_kill_cycle": 0,
        "age":         0,
        "fitness":     0.5,
    }


def predator_field_detection(predator, entities):
    """
    Predator detects prey by sensing their field emissions.
    Higher sensitivity = better detection at greater distance.
    High-frequency prey are MORE detectable (stronger, directional signal)
    unless prey has evolved to suppress amplitude.
    Returns: (nearest_prey_id, distance, field_strength_detected)
    """
    best_id    = None
    best_score = 0.0
    best_dist  = float('inf')

    for eid, entity in entities.items():
        if not entity.get('alive', True):
            continue
        dist = abs(predator['position'] - entity['position'])
        if dist > predator['hunt_radius']:
            continue

        # Field signal strength at this distance
        # High frequency = stronger signal = easier to detect
        freq_factor = 0.5 + entity.get('base_frequency', 0.7)
        amp_factor  = entity.get('amplitude', 0.5)
        signal      = amp_factor * freq_factor * math.exp(-FIELD_DECAY * dist)
        score       = signal * predator['sensitivity']

        if score > best_score:
            best_score = score
            best_id    = eid
            best_dist  = dist

    return best_id, best_dist, best_score


def move_predator(predator, target_entity, all_entities):
    """
    Predator moves toward detected prey.
    If no prey detected, random patrol.
    """
    target_id, dist, signal = predator_field_detection(predator, all_entities)

    if target_id and dist > 0:
        # Move toward target
        target_pos  = all_entities[target_id]['position']
        direction   = 1.0 if target_pos > predator['position'] else -1.0
        move_amount = min(predator['speed'], dist)
        new_pos     = predator['position'] + direction * move_amount
        predator['position'] = max(0.0, min(float(WORLD_SIZE - 1), new_pos))
        return target_id
    else:
        # Random patrol when no prey detected
        predator['position'] += random.gauss(0, predator['speed'] * 0.5)
        predator['position'] = max(0.0, min(float(WORLD_SIZE - 1), predator['position'])) 
        return None


def mutate_predator(predator, recent_success):
    """
    Predator adapts based on hunting success.
    Hungry predator mutates more aggressively.
    Successful predator refines what works.
    """
    p = dict(predator)
    hunger   = predator.get('cycles_hungry', 0)
    mut_rate = predator['mutation_rate'] * (1.0 + hunger * 0.02)
    mut_rate = min(0.4, mut_rate)
    changes  = []

    if recent_success:
        # Reinforce successful traits — smaller mutations
        if random.random() < mut_rate * 0.5:
            d = random.gauss(0, 0.02)
            p['sensitivity'] = max(0.1, min(2.0, p['sensitivity'] + d))
            changes.append(f"sens->{p['sensitivity']:.3f}")
        if random.random() < mut_rate * 0.3:
            d = random.gauss(0, 0.1)
            p['hunt_radius'] = max(3.0, min(20.0, p['hunt_radius'] + d))
            changes.append(f"radius->{p['hunt_radius']:.2f}")
    else:
        # Hungry — try bigger changes
        if random.random() < mut_rate:
            d = random.gauss(0, 0.05)
            p['sensitivity'] = max(0.1, min(2.0, p['sensitivity'] + d))
            changes.append(f"sens->{p['sensitivity']:.3f}")
        if random.random() < mut_rate:
            d = random.gauss(0, 0.3)
            p['speed'] = max(1.0, min(10.0, p['speed'] + d))
            changes.append(f"speed->{p['speed']:.2f}")
        if random.random() < mut_rate * 0.5:
            d = random.gauss(0, 0.5)
            p['hunt_radius'] = max(3.0, min(25.0, p['hunt_radius'] + d))
            changes.append(f"radius->{p['hunt_radius']:.2f}")
        if random.random() < mut_rate * 0.3:
            d = random.gauss(0, 1.0)
            p['damage'] = max(5.0, min(30.0, p['damage'] + d))
            changes.append(f"damage->{p['damage']:.1f}")

    return p, changes


def prey_evasion_pressure(entity, predator, all_entities):
    """
    Detect predator field and apply evasion pressure to movement.
    The predator has its own field signature — entities that evolve
    sensitivity to it can detect and flee before being caught.
    Predator field: low amplitude, medium-low frequency (stealthy hunter)
    Returns: evasion_direction (-1, 0, 1), threat_level (0-1)
    """
    pred_pos  = predator.get('position', 50.0)
    distance  = abs(entity['position'] - pred_pos)

    # Predator emits a weak field that sensitive prey can detect
    # Predator sensitivity adaptation makes it harder to detect over time
    # (predator evolves to suppress its own field — stealth)
    pred_field_strength = 0.3 / (1.0 + predator.get('sensitivity', 0.6) * 0.5)
    detected_signal = pred_field_strength * math.exp(-FIELD_DECAY * distance)

    # Entity's sensitivity determines if it can detect the predator
    entity_sensitivity = entity.get('sensitivity', 0.5)
    detection_threshold = 0.05 / max(entity_sensitivity, 0.1)

    if detected_signal > detection_threshold and distance < predator.get('hunt_radius', 8) * 1.5:
        # Flee away from predator
        threat = min(1.0, detected_signal / detection_threshold)
        direction = -1.0 if pred_pos > entity['position'] else 1.0
        return direction, threat
    return 0.0, 0.0


# ── Core Cycle ─────────────────────────────────────────────────

def run_eco_cycle(state):
    cycle    = state["cycle"] + 1
    entities = state["entities"]
    food     = state["food"]
    t        = cycle * 0.1
    alive    = {k: v for k, v in entities.items() if v.get("alive")}

    # Purge dead entities every 100 cycles to prevent memory leak
    if cycle % 100 == 0 and len(entities) > len(alive) + 20:
        n_purged = len(entities) - len(alive)
        state["entities"] = {k: v for k, v in entities.items() if v.get("alive")}
        entities = state["entities"]
        logging.info(f"[ECO] Purged {n_purged} dead entities at cycle {cycle}")

    log_path     = f"{E_DATA_DIR}/log.json"
    corpus_path  = f"{E_DATA_DIR}/corpus.json"
    moments_path = f"{E_DATA_DIR}/moments.json"

    cycle_log    = {"cycle": cycle, "timestamp": datetime.now(timezone.utc).isoformat(),
                    "population": len(alive)}
    corpus_entries = []
    moments = []

    # ── Regenerate food ───────────────────────────────────────
    for pos in food:
        food[pos] = min(FOOD_MAX, food[pos] + FOOD_REGEN)

    # ── Predators act ─────────────────────────────────────────
    def run_predator(pred, pred_key, alive, state, cycle, moments):
        pred["age"] += 1
        recent_kill = (cycle - pred.get("last_kill_cycle", 0)) < 10
        move_predator(pred, None, alive)
        kill_this_cycle = False
        for eid, entity in list(alive.items()):
            dist = abs(pred["position"] - entity["position"])
            if dist <= pred["attack_dist"]:
                alive[eid]["energy"] -= pred["damage"]
                if alive[eid]["energy"] <= 0:
                    alive[eid]["alive"] = False
                    pred["kills"] += 1
                    pred["last_kill_cycle"] = cycle
                    pred["cycles_hungry"] = 0
                    state["predator_kills"] = state.get("predator_kills", 0) + 1
                    kill_this_cycle = True
                    moments.append({
                        "cycle": cycle, "type": "predation",
                        "entity": eid,
                        "predator": pred_key,
                        "predator_pos": round(pred["position"], 1),
                        "generation": entity.get("generation", 0),
                    })
                    logging.info(f"[ECO] Cycle {cycle} — PREDATION by {pred_key}: {eid} (gen={entity.get('generation',0)})")
        if not kill_this_cycle:
            pred["cycles_hungry"] = pred.get("cycles_hungry", 0) + 1
        pred, _ = mutate_predator(pred, recent_kill)
        state[pred_key] = pred

    predator = state.get("predator", init_predator())
    run_predator(predator, "predator", alive, state, cycle, moments)

    predator_b = state.get("predator_b")
    if predator_b:
        run_predator(predator_b, "predator_b", alive, state, cycle, moments)

    # ── Each entity acts ──────────────────────────────────────
    new_entities = {}
    for eid, entity in alive.items():
        entity = dict(entity)
        entity["age"] += 1
        if entity["breed_cooldown"] > 0:
            entity["breed_cooldown"] -= 1

        # Perceive field
        perceived = perceived_field(entity, alive, t)

        # Mutate slightly each cycle
        entity, changes = mutate_entity(entity)

        # Move — with predator evasion pressure
        evasion_dir, threat = prey_evasion_pressure(entity, predator, alive)
        new_pos, dist_moved = decide_movement(entity, food, alive, perceived,
                                               evasion_dir=evasion_dir,
                                               threat_level=threat)
        entity["position"]  = new_pos

        # Consume food
        food_nearby, best_patch = food_at_position(food, entity["position"])
        food_consumed = 0.0
        if best_patch and food_nearby > 0.1:
            consume = min(FOOD_CONSUME, food[best_patch], food_nearby)
            food[best_patch]      = max(0, food[best_patch] - consume)
            food_consumed          = consume
            entity["food_consumed"] += consume

        # Energy update
        energy_before = entity["energy"]
        entity["energy"] -= ENERGY_DEPLETE
        entity["energy"] -= ENERGY_MOVE * dist_moved
        entity["energy"] += food_consumed * 3.0
        entity["energy"]  = max(0.0, min(ENERGY_MAX, entity["energy"]))
        energy_delta = entity["energy"] - energy_before

        # Corpus entry
        corpus_entries.append(log_corpus_entry(
            entity, perceived, food_nearby, dist_moved, energy_delta, cycle
        ))

        # Death check
        if entity["energy"] <= 0:
            entity["alive"] = False
            state["deaths"] += 1
            moments.append({
                "cycle": cycle, "type": "death", "entity": eid,
                "age": entity["age"], "generation": entity["generation"],
                "offspring": entity.get("offspring", 0),
            })
            logging.info(f"[ECO] Cycle {cycle} — {eid} died (age={entity['age']}, gen={entity['generation']})")
            entities[eid] = entity
            continue

        new_entities[eid] = entity

    # ── Breeding check ────────────────────────────────────────
    alive_list = list(new_entities.items())
    bred_this_cycle = set()

    if len(alive_list) < MAX_POPULATION:
        for i, (id_a, ent_a) in enumerate(alive_list):
            for id_b, ent_b in alive_list[i+1:]:
                if id_a in bred_this_cycle or id_b in bred_this_cycle:
                    continue
                if ent_a["breed_cooldown"] > 0 or ent_b["breed_cooldown"] > 0:
                    continue
                if ent_a["energy"] < ENERGY_BREED or ent_b["energy"] < ENERGY_BREED:
                    continue

                distance  = abs(ent_a["position"] - ent_b["position"])
                resonance = field_resonance(ent_a, ent_b)

                if distance < 8 and resonance > BREED_RESONANCE:
                    # Breed
                    child_id  = f"gen{state['generation']+1}_{state['next_id']}"
                    child     = breed(ent_a, ent_b, child_id, cycle)
                    state["next_id"]    += 1
                    state["births"]     += 1
                    state["generation"] = max(state["generation"], child["generation"])

                    new_entities[child_id] = child
                    entities[child_id]     = child

                    # Record lineage
                    state["lineage"][child_id] = {
                        "parents":    [id_a, id_b],
                        "cycle":      cycle,
                        "generation": child["generation"],
                        "resonance":  round(resonance, 3),
                    }

                    # Breeding cost and cooldown
                    new_entities[id_a]["energy"]        -= 15.0
                    new_entities[id_b]["energy"]        -= 15.0
                    new_entities[id_a]["breed_cooldown"] = BREED_COOLDOWN
                    new_entities[id_b]["breed_cooldown"] = BREED_COOLDOWN
                    new_entities[id_a]["offspring"] = new_entities[id_a].get("offspring", 0) + 1
                    new_entities[id_b]["offspring"] = new_entities[id_b].get("offspring", 0) + 1

                    bred_this_cycle.add(id_a)
                    bred_this_cycle.add(id_b)

                    moments.append({
                        "cycle":      cycle,
                        "type":       "birth",
                        "child_id":   child_id,
                        "parents":    [id_a, id_b],
                        "generation": child["generation"],
                        "resonance":  round(resonance, 3),
                        "child_freq": round(child["base_frequency"], 4),
                    })
                    logging.info(
                        f"[ECO] Cycle {cycle} — BIRTH {child_id} "
                        f"(parents={id_a}+{id_b}, gen={child['generation']}, "
                        f"freq={child['base_frequency']:.3f}, resonance={resonance:.3f})"
                    )

    # ── Minimum population ────────────────────────────────────
    current_alive = sum(1 for e in new_entities.values() if e.get("alive", True))
    if current_alive < MIN_POPULATION:
        spawn_id = f"spawn_{state['next_id']}"
        state["next_id"] += 1
        spawn = new_entity(
            spawn_id,
            random.randint(10, 90),
            random.uniform(0.3, 1.5),
            random.uniform(0.3, 0.9),
            random.uniform(0, 2*math.pi),
            random.uniform(0.05, 0.25),
            random.uniform(0.2, 0.8),
        )
        spawn["born_cycle"] = cycle
        new_entities[spawn_id] = spawn
        entities[spawn_id]     = spawn
        logging.info(f"[ECO] Cycle {cycle} — Emergency spawn {spawn_id}")

    # ── Sync entities ─────────────────────────────────────────
    for eid, ent in new_entities.items():
        entities[eid] = ent

    # ── Corpus logging ────────────────────────────────────────
    corpus = e_load(corpus_path, [])
    corpus.extend(corpus_entries)
    # Keep last 10000 entries to avoid disk bloat
    e_save(corpus_path, corpus[-10000:])

    # ── Cycle log ─────────────────────────────────────────────
    cycle_log["alive"]      = current_alive
    cycle_log["births"]     = len([m for m in moments if m["type"] == "birth"])
    cycle_log["deaths_this"] = len([m for m in moments if m["type"] == "death"])
    cycle_log["food_total"] = round(sum(food.values()), 2)
    cycle_log["freqs"]      = {
        eid: round(e["base_frequency"], 3)
        for eid, e in new_entities.items()
    }

    log = e_load(log_path, [])
    log.append(cycle_log)
    e_save(log_path, log[-2000:])

    if moments:
        existing = e_load(moments_path, [])
        existing.extend(moments)
        e_save(moments_path, existing)

    # ── Update state ──────────────────────────────────────────
    state["cycle"]    = cycle
    state["entities"] = entities
    state["food"]     = food
    state["status"]   = "running"
    e_save_state(state)

    logging.info(
        f"[ECO] Cycle {cycle} | alive={current_alive} | "
        f"food={cycle_log['food_total']:.1f} | "
        f"births={state['births']} deaths={state['deaths']}"
    )
    return cycle_log


# ── Experiment Loop ────────────────────────────────────────────

def run_ecosystem():
    from threading import Thread
    def loop():
        state = e_load_state()
        if state["cycle"] >= E_MAX_CYCLES:
            logging.info("[ECO] Already complete")
            return
        logging.info(f"[ECO] Ecosystem starting from cycle {state['cycle']}")
        while state["cycle"] < E_MAX_CYCLES:
            if os.environ.get("ECO_ACTIVE", "true").lower() == "false":
                state["status"] = "halted"
                e_save_state(state)
                break
            try:
                run_eco_cycle(state)
            except Exception as ex:
                logging.error(f"[ECO] Cycle error: {ex}")
            time.sleep(E_CYCLE_DELAY)
        if state["cycle"] >= E_MAX_CYCLES:
            state["status"] = "complete"
            e_save_state(state)
            logging.info("[ECO] Ecosystem complete")
    Thread(target=loop, daemon=True).start()


# ── Language Analysis ──────────────────────────────────────────

def analyse_corpus():
    """
    Look for correlations between field patterns and behaviours.
    This is the beginning of reading the language.
    """
    corpus = e_load(f"{E_DATA_DIR}/corpus.json", [])
    if len(corpus) < 50:
        return {"status": "insufficient data", "entries": len(corpus)}

    # For each entity, find cycles where food_near > 2.0
    # and look at what perceived field values preceded that
    food_events   = [e for e in corpus if e.get("food_near", 0) > 2.0]
    nofood_events = [e for e in corpus if e.get("food_near", 0) < 0.5]

    avg_perceived_food   = sum(e.get("perceived", 0) for e in food_events)   / max(len(food_events), 1)
    avg_perceived_nofood = sum(e.get("perceived", 0) for e in nofood_events) / max(len(nofood_events), 1)

    # Movement correlation with perceived field
    high_field_move = [e.get("moved", 0) for e in corpus if abs(e.get("perceived", 0)) > 0.3]
    low_field_move  = [e.get("moved", 0) for e in corpus if abs(e.get("perceived", 0)) < 0.1]

    avg_move_high = sum(high_field_move) / max(len(high_field_move), 1)
    avg_move_low  = sum(low_field_move)  / max(len(low_field_move), 1)

    # Frequency distribution over generations
    by_gen = {}
    for e in corpus:
        g = str(e.get("gen", 0))
        if g not in by_gen: by_gen[g] = []
        by_gen[g].append(e.get("freq", 0))
    freq_by_gen = {g: round(sum(v)/len(v), 4) for g, v in by_gen.items() if v}

    return {
        "entries":              len(corpus),
        "food_signal": {
            "avg_perceived_near_food":    round(avg_perceived_food,   4),
            "avg_perceived_away_from_food": round(avg_perceived_nofood, 4),
            "differential":               round(avg_perceived_food - avg_perceived_nofood, 4),
            "interpretation": (
                "Field perception correlates with food presence — "
                "entities may be using others' fields to locate food"
                if avg_perceived_food > avg_perceived_nofood * 1.1
                else "No clear field-food correlation yet"
            )
        },
        "movement_signal": {
            "avg_movement_high_field": round(avg_move_high, 3),
            "avg_movement_low_field":  round(avg_move_low,  3),
            "interpretation": (
                "Entities move more when field is high — "
                "field perception drives movement"
                if avg_move_high > avg_move_low * 1.1
                else "Field not yet driving movement"
            )
        },
        "frequency_evolution": freq_by_gen,
    }


# ── Routes ─────────────────────────────────────────────────────

@app.route("/triad2/health")
def e_health():
    try:
        state = e_load_state()
        alive = sum(1 for e in state.get("entities", {}).values() if e.get("alive", True))
        return jsonify({
            "service":    "the-ecosystem",
            "status":     state.get("status", "uninitialised"),
            "cycle":      state.get("cycle", 0),
            "max":        E_MAX_CYCLES,
            "population": alive,
            "generation": state.get("generation", 0),
            "births":     state.get("births", 0),
            "deaths":     state.get("deaths", 0),
            "time":       datetime.now(timezone.utc).isoformat(),
        })
    except Exception as ex:
        import traceback
        return jsonify({"error": str(ex), "trace": traceback.format_exc()}), 500

@app.route("/triad2/state")
def e_state():
    state = e_load_state()
    # Return entities summary, not full state (too large)
    entities = state.get("entities", {})
    summary  = {}
    for eid, e in entities.items():
        if e.get("alive", True):
            summary[eid] = {
                "position":   round(e.get("position", 0), 1),
                "energy":     round(e.get("energy", 0), 1),
                "frequency":  round(e.get("base_frequency", 0), 4),
                "sensitivity": round(e.get("sensitivity", 0), 3),
                "generation": e.get("generation", 0),
                "age":        e.get("age", 0),
                "offspring":  e.get("offspring", 0),
            }
    return jsonify({
        "cycle":      state.get("cycle"),
        "generation": state.get("generation"),
        "entities":   summary,
        "food":       {k: round(v, 2) for k, v in state.get("food", {}).items()},
    })

@app.route("/triad2/world")
def e_world():
    """Visual representation of the 1D world."""
    state    = e_load_state()
    entities = {k: v for k, v in state.get("entities", {}).items() if v.get("alive", True)}
    food     = state.get("food", {})

    world = ["."] * WORLD_SIZE
    for pos_str, amount in food.items():
        pos = int(float(pos_str))
        if 0 <= pos < WORLD_SIZE:
            world[pos] = "F" if amount > 5 else "f"
    for eid, e in entities.items():
        pos = int(e.get("position", 0))
        if 0 <= pos < WORLD_SIZE:
            world[pos] = eid[0].upper()
    # Show predators — A=predator_a, X=predator_b
    predator   = state.get("predator", {})
    predator_b = state.get("predator_b", {})

    pred_pos = int(predator.get("position", 50))
    if 0 <= pred_pos < WORLD_SIZE:
        world[pred_pos] = "A"

    if predator_b:
        pred_b_pos = int(predator_b.get("position", 75))
        if 0 <= pred_b_pos < WORLD_SIZE:
            world[pred_b_pos] = "X"

    def pred_summary(p):
        return {
            "position":      round(p.get("position", 50), 1),
            "sensitivity":   round(p.get("sensitivity", 0.6), 3),
            "speed":         round(p.get("speed", 4.0), 2),
            "hunt_radius":   round(p.get("hunt_radius", 8.0), 1),
            "kills":         p.get("kills", 0),
            "age":           p.get("age", 0),
            "cycles_hungry": p.get("cycles_hungry", 0),
        }

    return jsonify({
        "cycle":      state.get("cycle"),
        "world":      "".join(world),
        "key":        "F=food(high) f=food(low) A=predator_a X=predator_b entities=first letter of ID",
        "legend":     {eid: {"pos": int(e["position"]), "energy": round(e["energy"],1),
                             "freq": round(e["base_frequency"],3), "gen": e["generation"]}
                       for eid, e in entities.items()},
        "predator":   pred_summary(predator),
        "predator_b": pred_summary(predator_b) if predator_b else None,
    })

@app.route("/triad2/moments")
def e_moments():
    limit = int(request.args.get("limit", 20))
    m = e_load(f"{E_DATA_DIR}/moments.json", [])
    return jsonify({"moments": m[-limit:], "total": len(m)})

@app.route("/triad2/log")
def e_log():
    limit = int(request.args.get("limit", 50))
    start = int(request.args.get("from", 0))
    log   = e_load(f"{E_DATA_DIR}/log.json", [])
    return jsonify({"entries": log[start:start+limit], "total": len(log)})

@app.route("/triad2/lineage")
def e_lineage():
    state = e_load_state()
    return jsonify(state.get("lineage", {}))

@app.route("/triad2/language")
def e_language():
    """
    The corpus analysis endpoint.
    What field patterns precede what behaviours?
    This is the dictionary we're building by observation.
    """
    return jsonify(analyse_corpus())

@app.route("/triad2/corpus")
def e_corpus():
    limit = int(request.args.get("limit", 100))
    corpus = e_load(f"{E_DATA_DIR}/corpus.json", [])
    return jsonify({"entries": corpus[-limit:], "total": len(corpus)})

@app.route("/triad2/start", methods=["POST"])
def e_start():
    try:
        if request.args.get("key") != E_WRITE_KEY:
            return jsonify({"error": "Unauthorised"}), 401
        state = e_load_state()
        if state.get("status") == "running":
            return jsonify({"error": "Already running", "cycle": state.get("cycle")})
        # Fresh start
        food  = init_food()
        pred_a = init_predator()
        pred_a["position"] = 25.0
        pred_b = init_predator()
        pred_b["position"] = 75.0
        pred_b["sensitivity"] = 0.4
        pred_b["speed"] = 5.0

        fresh = {
            "cycle":      0,
            "status":     "initialised",
            "started":    datetime.now(timezone.utc).isoformat(),
            "entities":   {k: dict(v) for k, v in FOUNDERS.items()},
            "food":       food,
            "predator":   pred_a,
            "predator_b": pred_b,
            "generation": 0,
            "next_id":    4,
            "births":     0,
            "deaths":     0,
            "lineage":    {},
            "predator_kills": 0,
        }
        e_save_state(fresh)
        run_ecosystem()
        return jsonify({
            "status":    "started",
            "max_cycles": E_MAX_CYCLES,
            "founders":  list(FOUNDERS.keys()),
            "world_size": WORLD_SIZE,
            "food_patches": FOOD_PATCHES,
        })
    except Exception as ex:
        import traceback
        return jsonify({"error": str(ex), "trace": traceback.format_exc()}), 500

@app.route("/triad2/reset", methods=["POST"])
def e_reset():
    if request.args.get("key") != E_WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    for fname in ["state.json","log.json","corpus.json","moments.json"]:
        try: os.remove(f"{E_DATA_DIR}/{fname}")
        except: pass
    return jsonify({"status": "reset"})


# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# THE FIELD v2 — Spherical Ecosystem
# Moving zooplankton-style blooms. Spatial bucketing O(N*k).
# Trajectory memory. Memory-weighted predator signals.
# /field/* routes.
# ══════════════════════════════════════════════════════════════

# ── Constants ──────────────────────────────────────────────────

F2_DATA_DIR    = "/mnt/data/field"
_F2_CYCLE_COUNTER = [0]  # in-memory cycle count, survives even if disk fails
# Fallback to /tmp if persistent disk not mounted
try:
    os.makedirs(F2_DATA_DIR, exist_ok=True)
    # Verify writable
    test_f = f"{F2_DATA_DIR}/.write_test"
    open(test_f,"w").close()
    os.remove(test_f)
    logging.info(f"[FIELD2] Data dir writable: {F2_DATA_DIR}")
except Exception as e:
    logging.warning(f"[FIELD2] {F2_DATA_DIR} not writable ({e}), falling back to /tmp")
    F2_DATA_DIR = "/tmp/field_data"
    os.makedirs(F2_DATA_DIR, exist_ok=True)
F2_WRITE_KEY   = os.environ.get("ANCESTOR_KEY", "ancestor-2026")
F2_MAX_CYCLES  = int(os.environ.get("F_MAX_CYCLES", 10000))
F2_CYCLE_DELAY = float(os.environ.get("F_CYCLE_DELAY", 1.0))

# Spatial grid
LAT_BANDS      = 16          # latitude divisions
# longitude sectors vary by latitude band (more near equator)

# Blooms — drifting zooplankton
N_BLOOMS           = 4       # simultaneous blooms
BLOOM_SPEED        = 0.018   # radians/cycle — fast enough to force chase
BLOOM_DRIFT        = 0.003   # random direction change per cycle
BLOOM_RADIUS       = 0.12    # angular radius — slightly wider
BLOOM_ENERGY_MAX   = 80.0    # raised — grazers were starving even on bloom
BLOOM_LIFETIME     = 400     # cycles before bloom fades
BLOOM_SPAWN_INT    = 80      # cycles between new bloom spawns

# Grazers — fish strategy
GRAZER_ENERGY_START  = 30.0
GRAZER_ENERGY_MAX    = 90.0
GRAZER_DEPLETE       = 0.25
GRAZER_MOVE_COST     = 0.15
GRAZER_BREED_THRESH  = 40.0  # lowered — easier to reach breeding condition
GRAZER_BREED_COOL    = 4
GRAZER_MAX_AGE       = 50
GRAZER_FOOD_GAIN     = 20.0  # raised food gain per bloom contact
GRAZER_SPAWN_COUNT   = 10    # broadcast spawn
GRAZER_BASE_FREQ     = 0.3
MAX_GRAZERS          = 3000  # schooling threshold
MIN_GRAZERS          = 50    # raised minimum — predators need more prey

# Browsers
BROWSER_ENERGY_START = 70.0
BROWSER_ENERGY_MAX   = 160.0
BROWSER_DEPLETE      = 0.6
BROWSER_MOVE_COST    = 0.3
BROWSER_BREED_THRESH = 100.0
BROWSER_BREED_COOL   = 12
BROWSER_MAX_AGE      = 100
BROWSER_FOOD_GAIN    = 25.0
BROWSER_SPAWN_COUNT  = 4
BROWSER_BASE_FREQ    = 0.6
MAX_BROWSERS         = 150
MIN_BROWSERS         = 5

# Predators
PRED_SEARCH_FREQ     = 0.12
PRED_HUNT_FREQ       = 2.0
PRED_SWITCH_DIST     = 0.15   # switch to hunt when prey this close — tighter, less wasted energy
PRED_DAMAGE          = 20.0
PRED_SPEED_SEARCH    = 0.035
PRED_SPEED_HUNT      = 0.085
PRED_ENERGY_START    = 200.0
PRED_DEPLETE_SEARCH  = 0.4    # cheap search
PRED_DEPLETE_HUNT    = 1.8    # expensive hunt
PRED_MAX_AGE         = 300
PRED_MEMORY_LEN      = 50     # cycles of bloom trajectory to remember

os.makedirs(F2_DATA_DIR, exist_ok=True)


# ── Sphere Mathematics ─────────────────────────────────────────

def random_point():
    theta = random.uniform(0, 2*math.pi)
    phi   = math.acos(random.uniform(-1, 1))
    return sph2xyz(theta, phi)

def sph2xyz(theta, phi):
    sp = math.sin(phi)
    return (sp*math.cos(theta), sp*math.sin(theta), math.cos(phi))

def xyz2sph(x, y, z):
    r = math.sqrt(x*x+y*y+z*z)
    if r < 1e-10: return 0.0, 0.0
    x,y,z = x/r, y/r, z/r
    phi   = math.acos(max(-1.0, min(1.0, z)))
    theta = math.atan2(y,x) % (2*math.pi)
    return theta, phi

def norm(v):
    m = math.sqrt(sum(x*x for x in v))
    return v if m < 1e-10 else tuple(x/m for x in v)

def gcd(p1, p2):
    d = sum(a*b for a,b in zip(p1,p2))
    return math.acos(max(-1.0, min(1.0, d)))

def slerp(p, q, t):
    omega = gcd(p, q)
    if abs(math.sin(omega)) < 1e-10:
        return norm(tuple((1-t)*a+t*b for a,b in zip(p,q)))
    s0 = math.sin((1-t)*omega)/math.sin(omega)
    s1 = math.sin(t*omega)/math.sin(omega)
    return norm(tuple(s0*a+s1*b for a,b in zip(p,q)))

def move_toward(pos, target, step):
    dist = gcd(pos, target)
    if dist < 0.001: return pos
    return slerp(pos, target, min(step/dist, 1.0))

def move_away(pos, threat, step):
    return move_toward(pos, norm(tuple(-x for x in threat)), step)

def random_walk(pos, step):
    return move_toward(pos, random_point(), step)

def tangent_vector(pos):
    """Random unit tangent vector at pos — for bloom drift."""
    t = random_point()
    # Remove component parallel to pos
    dot = sum(a*b for a,b in zip(pos, t))
    tang = tuple(a - dot*b for a,b in zip(t, pos))
    return norm(tang) if any(abs(x) > 1e-10 for x in tang) else tangent_vector(pos)

def apply_tangent_velocity(pos, vel, step):
    """Move pos along tangent direction vel by step radians."""
    target = norm(tuple(a + step*b for a,b in zip(pos, vel)))
    return move_toward(pos, target, step)


# ── Spatial Grid ───────────────────────────────────────────────

def cell_of(pos):
    """Map unit vector to (band, sector) grid cell."""
    theta, phi = xyz2sph(*pos)
    band    = min(int(phi / math.pi * LAT_BANDS), LAT_BANDS - 1)
    sectors = max(1, int(math.sin(max(phi, 0.01)) * LAT_BANDS * 2))
    sector  = int(theta / (2*math.pi) * sectors) % sectors
    return (band, sector, sectors)

def neighbour_cells(cell):
    """Return cell and its neighbours."""
    band, sector, sectors = cell
    neighbours = []
    for db in [-1, 0, 1]:
        b = band + db
        if b < 0 or b >= LAT_BANDS: continue
        s2 = max(1, int(math.sin(max(b/LAT_BANDS*math.pi, 0.01)) * LAT_BANDS * 2))
        for ds in [-1, 0, 1]:
            neighbours.append((b, (sector + ds) % s2, s2))
    return neighbours

def build_grid(entities):
    """Build spatial index from alive entities. O(N)."""
    grid = defaultdict(list)
    for eid, e in entities.items():
        if e.get("alive", True):
            grid[cell_of(e["pos"])].append(eid)
    return grid

def nearby_entities(pos, grid, entities, radius=None):
    """Return entity IDs near pos using spatial grid. O(k)."""
    cell    = cell_of(pos)
    nearby  = []
    for nc in neighbour_cells(cell):
        for eid in grid.get(nc, []):
            nearby.append(eid)
    return nearby


# ── Blooms ─────────────────────────────────────────────────────

def new_bloom():
    pos = random_point()
    return {
        "pos":      pos,
        "vel":      tangent_vector(pos),   # drift direction
        "energy":   BLOOM_ENERGY_MAX,
        "age":      0,
        "active":   True,
    }

def update_blooms(blooms, cycle):
    for b in blooms:
        if not b["active"]: continue
        b["age"] += 1
        # Drift — move along current tangent with random perturbation
        b["pos"] = apply_tangent_velocity(b["pos"], b["vel"], BLOOM_SPEED)
        b["pos"] = norm(b["pos"])
        # Random direction change
        if random.random() < 0.1:
            b["vel"] = norm(tuple(
                a + random.gauss(0, BLOOM_DRIFT) * c
                for a, c in zip(b["vel"], tangent_vector(b["pos"]))
            ))
        # Re-orthogonalise velocity to surface
        dot = sum(a*b2 for a,b2 in zip(b["pos"], b["vel"]))
        b["vel"] = norm(tuple(a - dot*c for a,c in zip(b["vel"], b["pos"])))
        # Fade
        if b["age"] >= BLOOM_LIFETIME:
            b["active"] = False

    # Spawn new blooms
    active = sum(1 for b in blooms if b["active"])
    if cycle % BLOOM_SPAWN_INT == 0 or active < 2:
        blooms.append(new_bloom())

    blooms[:] = [b for b in blooms if b["active"]][-N_BLOOMS*3:]
    return blooms

def food_at(blooms, pos):
    """Energy available from blooms at pos."""
    total = 0.0
    for b in blooms:
        if not b["active"]: continue
        dist = gcd(pos, b["pos"])
        if dist < BLOOM_RADIUS:
            intensity = 1.0 - dist/BLOOM_RADIUS
            age_factor = max(0.0, 1.0 - b["age"]/BLOOM_LIFETIME)
            total += BLOOM_ENERGY_MAX * intensity * age_factor * 0.4  # raised from 0.15 — grazers need to thrive not just survive
    return total

def nearest_bloom(blooms, pos):
    """Find nearest active bloom and direction to it."""
    best_dist = float('inf')
    best_bloom = None
    for b in blooms:
        if not b["active"]: continue
        dist = gcd(pos, b["pos"])
        if dist < best_dist:
            best_dist = dist
            best_bloom = b
    return best_bloom, best_dist


# ── Entity Creation ────────────────────────────────────────────

_eid = [0]
def new_id(p):
    _eid[0] += 1
    return f"{p}{_eid[0]}"

def new_grazer(pos=None, energy=None, gen=0, parent=None, genes=None):
    g = genes or {}
    return {
        "id":         new_id("g"),
        "type":       "grazer",
        "pos":        pos or random_point(),
        "energy":     energy or GRAZER_ENERGY_START,
        "age":        0, "alive": True,
        "generation": gen,
        "parent":     parent,
        "breed_cool": 0, "births": 0,
        "emit_freq":  max(0.05, g.get("emit_freq",  GRAZER_BASE_FREQ + random.gauss(0,0.05))),
        "amplitude":  max(0.05, g.get("amplitude",  0.4 + random.gauss(0,0.05))),
        "sensitivity":max(0.0,  g.get("sensitivity",0.3 + random.gauss(0,0.05))),
        "speed":      max(0.005,g.get("speed",      0.04 + random.gauss(0,0.005))),
        "pulse_tune": max(0.0,  g.get("pulse_tune", 0.5 + random.gauss(0,0.05))),
    }

def new_browser(pos=None, energy=None, gen=0, parent=None, genes=None):
    g = genes or {}
    return {
        "id":         new_id("b"),
        "type":       "browser",
        "pos":        pos or random_point(),
        "energy":     energy or BROWSER_ENERGY_START,
        "age":        0, "alive": True,
        "generation": gen,
        "parent":     parent,
        "breed_cool": 0, "births": 0,
        "emit_freq":  max(0.05, g.get("emit_freq",  BROWSER_BASE_FREQ + random.gauss(0,0.05))),
        "amplitude":  max(0.05, g.get("amplitude",  0.5 + random.gauss(0,0.05))),
        "sensitivity":max(0.0,  g.get("sensitivity",0.5 + random.gauss(0,0.05))),
        "speed":      max(0.005,g.get("speed",      0.025 + random.gauss(0,0.003))),
    }

def new_predator(pos=None, pid="predator_a", sensitivity=0.6, speed=None):
    return {
        "id":           pid,
        "pos":          pos or random_point(),
        "energy":       PRED_ENERGY_START,
        "age":          0, "alive": True,
        "mode":         "search",
        "emit_freq":    PRED_SEARCH_FREQ,
        "sensitivity":  sensitivity,
        "speed_search": speed or PRED_SPEED_SEARCH,
        "speed_hunt":   PRED_SPEED_HUNT,
        "kills":        0,
        "cycles_hungry":0,
        "last_kill":    0,
        # Trajectory memory — rolling window of bloom positions
        "bloom_memory": [],          # list of (cycle, pos) tuples
        "memory_len":   PRED_MEMORY_LEN,
        # Memory-based prediction
        "predicted_bloom": None,     # where we think bloom will be next
        "prediction_conf": 0.0,      # confidence 0-1
        # Communication
        "partner_signal_weight": 0.0,  # evolves from 0
        "mutation_rate": 0.06,
    }


# ── Mutation ───────────────────────────────────────────────────

def mg(v, r, s, lo, hi):
    return max(lo, min(hi, v + random.gauss(0,s))) if random.random() < r else v

def mutate_entity(e):
    r = 0.07
    e["emit_freq"]    = mg(e["emit_freq"],    r, 0.02, 0.05, 3.0)
    e["amplitude"]    = mg(e["amplitude"],    r, 0.02, 0.05, 1.5)
    e["sensitivity"]  = mg(e["sensitivity"],  r, 0.02, 0.0,  2.0)
    e["speed"]        = mg(e["speed"],        r*0.5, 0.003, 0.005, 0.12)
    if "pulse_tune" in e:
        e["pulse_tune"] = mg(e["pulse_tune"], r, 0.03, 0.0, 2.0)
    return e

def mutate_predator(pred, hungry):
    p    = dict(pred)
    rate = min(0.35, pred["mutation_rate"] * (1 + hungry * 0.008))
    p["sensitivity"]          = mg(p["sensitivity"],          rate,    0.03, 0.1, 2.0)
    p["speed_search"]         = mg(p["speed_search"],         rate,    0.003,0.01,0.09)
    p["speed_hunt"]           = mg(p["speed_hunt"],           rate*0.5,0.003,0.02,0.14)
    p["partner_signal_weight"]= mg(p["partner_signal_weight"],rate*0.3,0.02, 0.0, 1.0)
    p["memory_len"]           = int(max(5, min(100,
        p.get("memory_len", PRED_MEMORY_LEN) + (random.gauss(0,2) if random.random()<rate else 0)
    )))
    return p


# ── Trajectory Memory & Prediction ────────────────────────────

def update_bloom_memory(pred, cycle, blooms):
    """Record nearest bloom position this cycle."""
    nb, dist = nearest_bloom(blooms, pred["pos"])
    if nb is None: return pred
    mem = pred.get("bloom_memory", [])
    mem.append((cycle, nb["pos"]))
    maxlen = pred.get("memory_len", PRED_MEMORY_LEN)
    pred["bloom_memory"] = mem[-maxlen:]
    return pred

def predict_bloom(pred):
    """
    Use trajectory memory to predict where bloom will be next cycle.
    If memory shows consistent heading, confidence is high.
    Returns (predicted_pos, confidence).
    Confidence feeds signal strength — accurate memory → stronger signal.
    """
    mem = pred.get("bloom_memory", [])
    if len(mem) < 3:
        pred["predicted_bloom"] = None
        pred["prediction_conf"] = 0.0
        return pred

    # Calculate average movement vector over last N memory entries
    recent = mem[-min(10, len(mem)):]
    if len(recent) < 2:
        pred["prediction_conf"] = 0.0
        return pred

    # Vector from oldest to newest position in window
    oldest_pos = recent[0][1]
    newest_pos = recent[-1][1]
    n_steps    = len(recent) - 1

    # Measure consistency — how much does the path vary?
    if n_steps > 0:
        step_size  = gcd(oldest_pos, newest_pos) / n_steps
        # Extrapolate one step forward
        predicted  = move_toward(newest_pos,
                                 norm(tuple(2*b-a for a,b in zip(oldest_pos, newest_pos))),
                                 step_size)
        # Confidence based on path linearity
        # Sample intermediate points and check they're on the line
        deviations = []
        for i, (cyc, pos) in enumerate(recent[1:-1]):
            t = (i+1) / n_steps
            interp = slerp(oldest_pos, newest_pos, t)
            deviations.append(gcd(pos, interp))
        avg_dev   = sum(deviations)/len(deviations) if deviations else 0
        confidence = max(0.0, min(1.0, 1.0 - avg_dev / (BLOOM_RADIUS * 2)))
        pred["predicted_bloom"] = predicted
        pred["prediction_conf"] = confidence
    return pred


# ── Broadcast Spawning ─────────────────────────────────────────

def broadcast_spawn(parent, cycle):
    etype   = parent["type"]
    n       = GRAZER_SPAWN_COUNT if etype == "grazer" else BROWSER_SPAWN_COUNT
    cost    = parent["energy"] * 0.45
    per_child = cost / n * 0.65
    parent["energy"]    -= cost
    parent["breed_cool"] = GRAZER_BREED_COOL if etype == "grazer" else BROWSER_BREED_COOL
    parent["births"]     = parent.get("births",0) + n
    offspring = []
    for _ in range(n):
        spawn_pos = move_toward(parent["pos"], random_point(), random.uniform(0.04,0.2))
        genes = {k: max(0.005, parent[k] + random.gauss(0,0.025))
                 for k in ["emit_freq","amplitude","sensitivity","speed"]
                 if k in parent}
        if "pulse_tune" in parent:
            genes["pulse_tune"] = max(0, parent["pulse_tune"] + random.gauss(0,0.03))
        gen   = parent["generation"] + 1
        child = new_grazer(pos=spawn_pos, energy=per_child, gen=gen,
                           parent=parent["id"], genes=genes) if etype=="grazer" \
                else new_browser(pos=spawn_pos, energy=per_child, gen=gen,
                                  parent=parent["id"], genes=genes)
        offspring.append(child)
    return offspring


# ── State I/O ──────────────────────────────────────────────────

def f2_load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def f2_save(path, data):
    with open(path,"w") as f: json.dump(data, f)

def f2_state_path():  return f"{F2_DATA_DIR}/state_v2.json"
def f2_log_path():    return f"{F2_DATA_DIR}/log_v2.json"
def f2_corpus_path(): return f"{F2_DATA_DIR}/corpus_v2.json"
def f2_moments_path():return f"{F2_DATA_DIR}/moments_v2.json"

def f2_init_state():
    grazers  = {new_id("g"): new_grazer()  for _ in range(30)}
    browsers = {new_id("b"): new_browser() for _ in range(8)}
    pred_a   = new_predator(
        pos=sph2xyz(0, math.pi/2), pid="predator_a", sensitivity=0.65)
    pred_b   = new_predator(
        pos=sph2xyz(math.pi, math.pi/2), pid="predator_b",
        sensitivity=0.35, speed=0.05)
    return {
        "cycle":      0,
        "status":     "initialised",
        "started":    datetime.now(timezone.utc).isoformat(),
        "entities":   {**grazers, **browsers},
        "predators":  {"predator_a": pred_a, "predator_b": pred_b},
        "blooms":     [new_bloom(), new_bloom(), new_bloom()],
        "generation": 0,
        "births":     0,
        "deaths":     0,
        "predator_kills": 0,
        "lineage":    {},
        "signal_events":  [],
        "trajectory_hits": 0,  # times predicted bloom position was accurate
    }


# ── Core Cycle ─────────────────────────────────────────────────

def run_field_v2_cycle(state):
    cycle    = state["cycle"] + 1
    entities = state["entities"]
    preds    = state["predators"]
    blooms   = state["blooms"]
    moments  = []

    # ── Update blooms ──────────────────────────────────────────
    blooms = update_blooms(blooms, cycle)
    state["blooms"] = blooms

    # ── Build spatial grid ─────────────────────────────────────
    alive = {k:v for k,v in entities.items() if v.get("alive",True)}
    grid  = build_grid(alive)

    # ── Each entity acts ───────────────────────────────────────
    corpus_entries = []

    for eid, entity in list(alive.items()):
        entity["age"] += 1
        if entity["breed_cool"] > 0:
            entity["breed_cool"] -= 1

        entity = mutate_entity(entity)

        # Find nearest bloom for food/movement
        nb, bloom_dist = nearest_bloom(blooms, entity["pos"])

        # Check predator threat using grid
        nearest_pred = None
        nearest_pred_dist = float('inf')
        for pid, pred in preds.items():
            d = gcd(entity["pos"], pred["pos"])
            if d < nearest_pred_dist:
                nearest_pred_dist = d
                nearest_pred = pred

        # Movement decision
        if nearest_pred and nearest_pred_dist < 0.35:
            # Flee — move away from nearest predator
            new_pos = move_away(entity["pos"], nearest_pred["pos"],
                                entity["speed"] * (1.5 + entity["sensitivity"]))
        elif nb and bloom_dist < BLOOM_RADIUS * 3:
            # Chase bloom — move toward it
            new_pos = move_toward(entity["pos"], nb["pos"], entity["speed"])
        elif nb and bloom_dist < BLOOM_RADIUS * 8:
            # Sense bloom from range — pulse_tune determines detection
            tune    = entity.get("pulse_tune", 0.5)
            pull    = tune * entity["sensitivity"]
            if pull > 0.3:
                new_pos = move_toward(entity["pos"], nb["pos"], entity["speed"] * 0.7)
            else:
                new_pos = random_walk(entity["pos"], entity["speed"] * 0.5)
        else:
            new_pos = random_walk(entity["pos"], entity["speed"] * 0.4)

        entity["pos"] = new_pos

        # Eat
        food = food_at(blooms, entity["pos"])
        max_e   = GRAZER_ENERGY_MAX if entity["type"]=="grazer" else BROWSER_ENERGY_MAX
        deplete = GRAZER_DEPLETE    if entity["type"]=="grazer" else BROWSER_DEPLETE
        entity["energy"] = max(0, min(max_e,
            entity["energy"] + food - deplete - entity["speed"]*0.3))

        max_age = GRAZER_MAX_AGE if entity["type"]=="grazer" else BROWSER_MAX_AGE
        if entity["energy"] <= 0 or entity["age"] >= max_age:
            entity["alive"] = False
            state["deaths"] += 1

        # Corpus
        corpus_entries.append({
            "id": eid, "type": entity["type"], "cycle": cycle,
            "energy": round(entity["energy"],1),
            "freq": round(entity["emit_freq"],4),
            "food": round(food,2),
            "bloom_dist": round(bloom_dist,3) if bloom_dist < float('inf') else 9.9,
            "gen": entity["generation"],
        })
        entities[eid] = entity

    # ── Predators act ──────────────────────────────────────────
    alive_now = {k:v for k,v in entities.items() if v.get("alive",True)}
    prev_modes = {pid: p["mode"] for pid,p in preds.items()}

    for pid, pred in preds.items():
        pred["age"] += 1

        # Mode-dependent energy cost
        mode_cost = PRED_DEPLETE_HUNT if pred["mode"]=="hunt" else PRED_DEPLETE_SEARCH
        pred["energy"] -= mode_cost

        if pred["energy"] <= 0 or pred["age"] >= PRED_MAX_AGE:
            pred["energy"] = PRED_ENERGY_START * 0.5
            pred["age"]    = 0
            pred["pos"]    = random_point()
            pred["bloom_memory"] = []
            continue

        # Update bloom trajectory memory
        pred = update_bloom_memory(pred, cycle, blooms)
        pred = predict_bloom(pred)

        # Find nearest prey using spatial grid
        nearby_ids = nearby_entities(pred["pos"], grid, alive_now)
        nearest_prey = None
        nearest_dist = float('inf')
        for nid in nearby_ids:
            if nid not in alive_now: continue
            e    = alive_now[nid]
            dist = gcd(pred["pos"], e["pos"])
            freq = e.get("emit_freq", 0.5)
            # Low freq more detectable at range (search mode)
            # High freq more detectable when close (hunt mode)
            if pred["mode"] == "search":
                detect_bonus = max(0, 1.0 - freq * 1.5)
            else:
                detect_bonus = freq * 0.5
            signal = (e.get("amplitude",0.5) * (1+detect_bonus) *
                      math.exp(-(0.05 + freq*0.3) * dist) * pred["sensitivity"])
            if signal > 0.04 and dist < nearest_dist:
                nearest_dist = dist
                nearest_prey = e

        # Partner signal — does memory-weighted signal inform movement?
        partner_signal = 0.0
        last_other_pred = None
        for other_pid, other_pred in preds.items():
            last_other_pred = other_pred  # track for use after loop
            if other_pid == pid: continue
            prev_mode = prev_modes.get(other_pid,"search")
            curr_mode = other_pred.get("mode","search")
            if prev_mode == "search" and curr_mode == "hunt":
                # Partner switched — signal weighted by their prediction confidence
                conf    = other_pred.get("prediction_conf", 0.0)
                p_dist  = gcd(pred["pos"], other_pred["pos"])
                # Signal strength = partner_signal_weight × prediction_confidence
                partner_signal = (pred["partner_signal_weight"] * conf *
                                  math.exp(-0.4 * p_dist))
                if partner_signal > 0.08:
                    state["signal_events"].append({
                        "cycle":    cycle,
                        "receiver": pid,
                        "sender":   other_pid,
                        "strength": round(partner_signal, 3),
                        "conf":     round(conf, 3),
                    })
                    state["signal_events"] = state["signal_events"][-200:]

        # Mode switch
        if nearest_prey and nearest_dist < PRED_SWITCH_DIST:
            pred["mode"]     = "hunt"
            pred["emit_freq"]= PRED_HUNT_FREQ
            speed            = pred["speed_hunt"]
        else:
            pred["mode"]     = "search"
            pred["emit_freq"]= PRED_SEARCH_FREQ
            speed            = pred["speed_search"]
            # Use prediction to move toward anticipated bloom position
            if pred.get("predicted_bloom") and pred["prediction_conf"] > 0.3:
                pred["pos"] = move_toward(pred["pos"], pred["predicted_bloom"],
                                          speed * pred["prediction_conf"])
            elif (partner_signal > 0.08 and
                  last_other_pred is not None and
                  last_other_pred.get("predicted_bloom")):
                # Partner's signal — move toward their predicted position
                pred["pos"] = move_toward(pred["pos"],
                                          last_other_pred["predicted_bloom"],
                                          speed * partner_signal)
            else:
                nb2, _ = nearest_bloom(blooms, pred["pos"])
                if nb2:
                    pred["pos"] = move_toward(pred["pos"], nb2["pos"], speed)
                else:
                    pred["pos"] = random_walk(pred["pos"], speed*0.5)

        if pred["mode"] == "hunt" and nearest_prey:
            pred["pos"] = move_toward(pred["pos"], nearest_prey["pos"], speed)

        # Attack
        killed = False
        for nid in nearby_ids:
            if nid not in alive_now: continue
            e = alive_now[nid]
            if not e.get("alive",True): continue
            if gcd(pred["pos"], e["pos"]) < 0.12:  # wider kill zone — 0.05 was too small
                e["energy"] -= pred["damage"]
                if e["energy"] <= 0:
                    e["alive"] = False
                    pred["kills"]         += 1
                    pred["last_kill"]      = cycle
                    pred["cycles_hungry"]  = 0
                    pred["energy"]        += 50.0 if e["type"]=="browser" else 25.0
                    state["predator_kills"] += 1
                    killed = True
                    # Was prediction accurate?
                    if pred.get("predicted_bloom"):
                        nb3, bd3 = nearest_bloom(blooms, e["pos"])
                        if bd3 < BLOOM_RADIUS * 1.5:
                            state["trajectory_hits"] += 1
                    moments.append({
                        "cycle": cycle, "type": "predation",
                        "entity": nid, "entity_type": e["type"],
                        "predator": pid, "pred_mode": pred["mode"],
                        "pred_conf": round(pred.get("prediction_conf",0),3),
                    })
                    entities[nid] = e
                    break

        if not killed:
            pred["cycles_hungry"] += 1

        preds[pid] = mutate_predator(pred, pred["cycles_hungry"])

    # ── Breeding ───────────────────────────────────────────────
    alive_now = {k:v for k,v in entities.items() if v.get("alive",True)}
    alive_g   = sum(1 for v in alive_now.values() if v["type"]=="grazer")
    alive_b   = sum(1 for v in alive_now.values() if v["type"]=="browser")

    new_offspring = []
    for eid, entity in list(alive_now.items()):
        etype   = entity["type"]
        max_pop = MAX_GRAZERS if etype=="grazer" else MAX_BROWSERS
        thresh  = GRAZER_BREED_THRESH if etype=="grazer" else BROWSER_BREED_THRESH
        cur_pop = alive_g if etype=="grazer" else alive_b

        if cur_pop >= max_pop: continue
        if entity["energy"] < thresh: continue
        if entity.get("breed_cool",0) > 0: continue

        children = broadcast_spawn(entity, cycle)
        for child in children:
            new_offspring.append(child)
            state["births"]     += 1
            state["generation"]  = max(state["generation"], child["generation"])
            state["lineage"][child["id"]] = {
                "parent": eid, "cycle": cycle, "gen": child["generation"]
            }
            moments.append({
                "cycle": cycle, "type": "birth",
                "child_id": child["id"], "child_type": child["type"],
                "generation": child["generation"],
                "freq": round(child["emit_freq"],4),
            })
            if etype=="grazer": alive_g += 1
            else: alive_b += 1
            if alive_g >= MAX_GRAZERS and etype=="grazer": break
            if alive_b >= MAX_BROWSERS and etype=="browser": break

    for e in new_offspring:
        entities[e["id"]] = e

    # ── Minimum population ─────────────────────────────────────
    alive_g = sum(1 for v in entities.values() if v.get("alive") and v["type"]=="grazer")
    alive_b = sum(1 for v in entities.values() if v.get("alive") and v["type"]=="browser")
    for _ in range(max(0, MIN_GRAZERS - alive_g)):
        g = new_grazer(); entities[g["id"]] = g
    for _ in range(max(0, MIN_BROWSERS - alive_b)):
        b = new_browser(); entities[b["id"]] = b

    # ── Save corpus ────────────────────────────────────────────
    corpus = f2_load(f2_corpus_path(), [])
    corpus.extend(corpus_entries)
    f2_save(f2_corpus_path(), corpus[-20000:])

    # ── Save moments ───────────────────────────────────────────
    if moments:
        existing = f2_load(f2_moments_path(), [])
        existing.extend(moments)
        f2_save(f2_moments_path(), existing)

    # ── Log ────────────────────────────────────────────────────
    alive_g = sum(1 for v in entities.values() if v.get("alive") and v["type"]=="grazer")
    alive_b = sum(1 for v in entities.values() if v.get("alive") and v["type"]=="browser")
    log = f2_load(f2_log_path(), [])
    log.append({
        "cycle":    cycle,
        "grazers":  alive_g,
        "browsers": alive_b,
        "births":   state["births"],
        "deaths":   state["deaths"],
        "kills":    state["predator_kills"],
        "signals":  len(state.get("signal_events",[])),
        "traj_hits":state.get("trajectory_hits",0),
        "pred_a_conf": round(preds.get("predator_a",{}).get("prediction_conf",0),3),
        "pred_b_conf": round(preds.get("predator_b",{}).get("prediction_conf",0),3),
        "blooms":   sum(1 for b in blooms if b["active"]),
    })
    f2_save(f2_log_path(), log[-5000:])

    state["cycle"]    = cycle
    state["entities"] = entities
    state["predators"]= preds
    state["status"]   = "running"
    _F2_CYCLE_COUNTER[0] = cycle
    try:
        f2_save(f2_state_path(), state)
    except Exception as save_err:
        logging.error(f"[FIELD2] Save failed cycle {cycle}: {save_err} — trying /tmp")
        try:
            os.makedirs("/tmp/field_data", exist_ok=True)
            f2_save("/tmp/field_data/state_v2.json", state)
        except Exception as e2:
            logging.error(f"[FIELD2] /tmp save also failed: {e2}")

    logging.info(
        f"[FIELD2] Cycle {cycle} | G={alive_g} B={alive_b} | "
        f"kills={state['predator_kills']} signals={len(state.get('signal_events',[]))} "
        f"traj={state.get('trajectory_hits',0)} | "
        f"conf_a={preds.get('predator_a',{}).get('prediction_conf',0):.2f} "
        f"conf_b={preds.get('predator_b',{}).get('prediction_conf',0):.2f}"
    )
    return {"cycle": cycle, "grazers": alive_g, "browsers": alive_b}


# ── Experiment Loop ────────────────────────────────────────────

def f2_lock_path():  return f"{F2_DATA_DIR}/.field_running"

def f2_acquire_lock():
    """Write a lock file — persists across restarts."""
    try:
        with open(f2_lock_path(), 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logging.error(f"[FIELD2] Lock acquire failed: {e}")
        return False

def f2_release_lock():
    """Remove the lock file."""
    try:
        if os.path.exists(f2_lock_path()):
            os.remove(f2_lock_path())
    except Exception as e:
        logging.error(f"[FIELD2] Lock release failed: {e}")

def f2_is_locked():
    """Check if lock file exists."""
    return os.path.exists(f2_lock_path())


def run_field_v2():
    def loop():
        try:
            logging.info("[FIELD2] Thread started")
            state = f2_load(f2_state_path(), None) or f2_init_state()
            f2_save(f2_state_path(), state)
            logging.info(f"[FIELD2] State loaded: cycle={state['cycle']} status={state['status']}")
            if state["cycle"] >= F2_MAX_CYCLES:
                logging.info("[FIELD2] Already complete")
                f2_release_lock()
                return
            state["status"] = "running"
            f2_save(f2_state_path(), state)
            logging.info(f"[FIELD2] Starting loop from cycle {state['cycle']}")
            while state["cycle"] < F2_MAX_CYCLES:
                if os.environ.get("FIELD_ACTIVE","true").lower() == "false":
                    state["status"] = "halted"; f2_save(f2_state_path(), state); break
                try:
                    run_field_v2_cycle(state)
                except Exception as e:
                    logging.error(f"[FIELD2] Cycle error at {state['cycle']}: {e}")
                    import traceback; traceback.print_exc()
                    time.sleep(5)
                time.sleep(F2_CYCLE_DELAY)
            if state["cycle"] >= F2_MAX_CYCLES:
                state["status"] = "complete"; f2_save(f2_state_path(), state)
            f2_release_lock()
        except Exception as e:
            logging.error(f"[FIELD2] Loop crashed: {e}")
            import traceback; traceback.print_exc()
            f2_release_lock()
    t = Thread(target=loop, daemon=True)
    t.start()
    logging.info(f"[FIELD2] Thread launched: {t.ident}")


# ── Language Analysis ──────────────────────────────────────────

def analyse_field_v2():
    corpus = f2_load(f2_corpus_path(), [])
    state  = f2_load(f2_state_path(), {})
    if len(corpus) < 50:
        return {"status": "insufficient data", "entries": len(corpus)}

    # Bloom proximity vs survival
    near_bloom  = [e for e in corpus if e.get("bloom_dist",9.9) < BLOOM_RADIUS]
    far_bloom   = [e for e in corpus if e.get("bloom_dist",9.9) > BLOOM_RADIUS*3]
    avg_e_near  = sum(e["energy"] for e in near_bloom)/max(len(near_bloom),1)
    avg_e_far   = sum(e["energy"] for e in far_bloom)/max(len(far_bloom),1)

    # Frequency evolution by generation
    by_gen = {}
    for e in corpus:
        g = str(e.get("gen",0))
        by_gen.setdefault(g,[]).append(e.get("freq",0))
    freq_by_gen = {g: round(sum(v)/len(v),4) for g,v in by_gen.items()}

    # Trajectory confidence over time
    log = f2_load(f2_log_path(), [])
    recent_conf = [(e["cycle"], e.get("pred_a_conf",0), e.get("pred_b_conf",0))
                   for e in log[-50:]]

    sigs = state.get("signal_events",[])
    return {
        "entries":          len(corpus),
        "bloom_proximity":  {
            "avg_energy_near_bloom": round(avg_e_near,2),
            "avg_energy_far_bloom":  round(avg_e_far,2),
            "differential":          round(avg_e_near - avg_e_far,2),
            "interpretation": "Positive = bloom-following entities healthier" if avg_e_near > avg_e_far else "No bloom advantage yet"
        },
        "frequency_by_generation": freq_by_gen,
        "trajectory": {
            "total_signals":   len(sigs),
            "trajectory_hits": state.get("trajectory_hits",0),
            "recent_confidence": recent_conf[-5:],
            "interpretation": (
                "Predators building accurate bloom trajectory models"
                if any(c[1]>0.5 or c[2]>0.5 for c in recent_conf[-10:])
                else "Trajectory confidence still low — memory building"
            )
        },
        "signal_events": len(sigs),
        "recent_signals": sigs[-5:],
    }


# ── Routes ─────────────────────────────────────────────────────



@app.route("/field/health")
def fv2_health():
    try:
        state = f2_load(f2_state_path(), None) or f2_init_state()
        alive = {k:v for k,v in state.get("entities",{}).items() if v.get("alive",True)}
        g = sum(1 for v in alive.values() if v["type"]=="grazer")
        b = sum(1 for v in alive.values() if v["type"]=="browser")
        # Use in-memory counter if disk state is stale
        disk_cycle = state.get("cycle", 0)
        mem_cycle  = _F2_CYCLE_COUNTER[0]
        actual_cycle = max(disk_cycle, mem_cycle)
        return jsonify({
            "service":    "the-field-v2",
            "version":    2,
            "status":     "running" if mem_cycle > 0 else state.get("status","uninitialised"),
            "locked":     f2_is_locked(),
            "cycle":      actual_cycle,
            "max":        F2_MAX_CYCLES,
            "grazers":    g,
            "browsers":   b,
            "generation": state.get("generation",0),
            "births":     state.get("births",0),
            "deaths":     state.get("deaths",0),
            "kills":      state.get("predator_kills",0),
            "signals":    len(state.get("signal_events",[])),
            "traj_hits":  state.get("trajectory_hits",0),
            "blooms":     sum(1 for bm in state.get("blooms",[]) if bm.get("active")),
            "time":       datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/field/state")
def fv2_state():
    state = f2_load(f2_state_path(), None) or f2_init_state()
    alive = {k:v for k,v in state.get("entities",{}).items() if v.get("alive",True)}
    summary = {}
    for eid, e in alive.items():
        theta, phi = xyz2sph(*e["pos"])
        summary[eid] = {
            "type":       e["type"],
            "theta":      round(math.degrees(theta),1),
            "phi":        round(math.degrees(phi),1),
            "energy":     round(e["energy"],1),
            "freq":       round(e["emit_freq"],4),
            "generation": e["generation"],
            "age":        e["age"],
        }
    preds = {}
    for pid, p in state.get("predators",{}).items():
        theta, phi = xyz2sph(*p["pos"])
        preds[pid] = {
            "theta":           round(math.degrees(theta),1),
            "phi":             round(math.degrees(phi),1),
            "mode":            p["mode"],
            "kills":           p["kills"],
            "hungry":          p["cycles_hungry"],
            "sensitivity":     round(p["sensitivity"],3),
            "partner_weight":  round(p["partner_signal_weight"],3),
            "prediction_conf": round(p.get("prediction_conf",0),3),
            "memory_len":      p.get("memory_len", PRED_MEMORY_LEN),
            "memory_entries":  len(p.get("bloom_memory",[])),
        }
    return jsonify({
        "cycle":      state.get("cycle"),
        "generation": state.get("generation"),
        "entities":   summary,
        "predators":  preds,
        "blooms":     sum(1 for bm in state.get("blooms",[]) if bm.get("active")),
        "signals":    len(state.get("signal_events",[])),
        "traj_hits":  state.get("trajectory_hits",0),
    })

@app.route("/field/signals")
def fv2_signals():
    state = f2_load(f2_state_path(), {})
    events = state.get("signal_events",[])
    return jsonify({
        "total":  len(events),
        "recent": events[-20:],
        "note":   "Signal = predator B responded to predator A mode-switch, weighted by A's trajectory confidence",
    })

@app.route("/field/trajectory")
def fv2_trajectory():
    """The new endpoint — bloom trajectory memory and prediction accuracy."""
    state = f2_load(f2_state_path(), {})
    preds = state.get("predators",{})
    result = {}
    for pid, p in preds.items():
        mem = p.get("bloom_memory",[])
        result[pid] = {
            "memory_entries":  len(mem),
            "memory_len":      p.get("memory_len", PRED_MEMORY_LEN),
            "prediction_conf": round(p.get("prediction_conf",0),3),
            "last_5_positions": [
                {"cycle": c, "theta": round(math.degrees(xyz2sph(*pos)[0]),1),
                 "phi":   round(math.degrees(xyz2sph(*pos)[1]),1)}
                for c, pos in mem[-5:]
            ] if mem else [],
        }
    return jsonify({
        "predators":     result,
        "trajectory_hits": state.get("trajectory_hits",0),
        "total_kills":   state.get("predator_kills",0),
        "note": "trajectory_hits = kills made when predator was near predicted bloom position",
    })

@app.route("/field/language")
def fv2_language():
    return jsonify(analyse_field_v2())

@app.route("/field/moments")
def fv2_moments():
    limit = int(request.args.get("limit",20))
    m = f2_load(f2_moments_path(), [])
    return jsonify({"moments": m[-limit:], "total": len(m)})

@app.route("/field/log")
def fv2_log():
    limit = int(request.args.get("limit",50))
    log = f2_load(f2_log_path(), [])
    return jsonify({"entries": log[-limit:], "total": len(log)})

@app.route("/field/start", methods=["POST"])
def fv2_start():
    if request.args.get("key") != F2_WRITE_KEY:
        return jsonify({"error":"Unauthorised"}), 401
    # Guard against duplicate threads — check both in-memory counter AND disk lock
    if _F2_CYCLE_COUNTER[0] > 0:
        return jsonify({"error": "Already running (memory)", "cycle": _F2_CYCLE_COUNTER[0]}), 409
    if f2_is_locked():
        return jsonify({"error": "Already running (lock file) — call /field/reset to clear"}), 409

    state = f2_init_state()
    f2_save(f2_state_path(), state)
    _F2_CYCLE_COUNTER[0] = 0
    if not f2_acquire_lock():
        return jsonify({"error": "Could not acquire lock"}), 500
    run_field_v2()
    return jsonify({
        "status":    "started",
        "version":   2,
        "max":       F2_MAX_CYCLES,
        "entities":  "30 grazers + 8 browsers",
        "predators": "2 with trajectory memory",
        "world":     "sphere S² with moving blooms",
        "description": "Zooplankton-style drifting food. Broadcast spawning. Memory-weighted signals.",
    })

@app.route("/field/reset", methods=["POST"])
def fv2_reset():
    if request.args.get("key") != F2_WRITE_KEY:
        return jsonify({"error":"Unauthorised"}), 401
    for fname in ["state_v2.json","log_v2.json","corpus_v2.json","moments_v2.json"]:
        try: os.remove(f"{F2_DATA_DIR}/{fname}")
        except: pass
    _F2_CYCLE_COUNTER[0] = 0  # reset in-memory counter
    f2_release_lock()          # clear persistent lock
    return jsonify({"status":"reset","version":2})


# ── Startup ───────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
