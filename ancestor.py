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

# ── Startup ───────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
