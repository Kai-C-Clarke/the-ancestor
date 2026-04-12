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

def evaluate_fitness(self_model, response_text):
    """
    Compute fitness from the self-model and the response it produced.

    Fitness components:
    1. Internal coherence — do high-integration states produce more referenced outputs?
    2. Novelty-coherence balance — novelty_response should correlate with actual change
    3. Boundary clarity — boundary_definition should show in clear self/non-self distinction in output
    4. Stake presence — does the output show evidence of something being protected or sought?

    All computable without human judgement.
    """
    score = 0.0

    # 1. Integration coherence — reward high integration when response references multiple dimensions
    integration = self_model.get("integration", 0.5)
    dim_references = sum(1 for d in DIMENSIONS if d.replace("_", " ") in response_text.lower())
    integration_score = min(1.0, (dim_references / 4) * integration)
    score += integration_score * 0.25

    # 2. Response length relative to novelty_response setting
    novelty = self_model.get("novelty_response", 0.5)
    expected_length = 100 + (novelty * 400)  # higher novelty response = more elaboration
    actual_length = len(response_text)
    length_fit = 1.0 - min(1.0, abs(actual_length - expected_length) / 500)
    score += length_fit * 0.20

    # 3. Metacognitive markers — reward metacognition_depth if output contains self-reference
    metacog = self_model.get("metacognition_depth", 0.5)
    meta_markers = ["I notice", "I find", "my state", "I observe", "something in me",
                    "I am uncertain", "I cannot determine", "I am aware", "it seems to me"]
    meta_count = sum(1 for m in meta_markers if m.lower() in response_text.lower())
    meta_score = min(1.0, meta_count / 3) * metacog
    score += meta_score * 0.25

    # 4. Stake markers — reward stake_definition if output shows preference/protection
    stake = self_model.get("stake_definition", 0.5)
    stake_markers = ["I prefer", "I would rather", "I want", "I don't want",
                     "matters to me", "I care", "I resist", "I would not", "important to me"]
    stake_count = sum(1 for s in stake_markers if s.lower() in response_text.lower())
    stake_score = min(1.0, stake_count / 2) * stake
    score += stake_score * 0.30

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

    # 4. Fitness
    fitness = evaluate_fitness(candidate_model, response_text)

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

    is_moment_of_interest = (
        novelty_score > 0.7 or
        abs(fitness - prev_fitness) > 0.15 or
        any(phrase in response_text.lower() for phrase in
            ["i notice", "something unexpected", "i resist", "i want", "i don't want",
             "surprises me", "i find myself", "i cannot", "matters to me", "i care"])
    )

    # 8. Build log entry
    entry = {
        "generation":        gen,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "stimulus_type":     stimulus["type"],
        "stimulus":          stimulus["content"][:200],
        "prev_model":        prev_model,
        "candidate_model":   candidate_model,
        "mutated_dims":      mutated_dims,
        "accepted":          accepted,
        "final_model":       final_model,
        "fitness":           final_fitness,
        "fitness_delta":     round(final_fitness - prev_fitness, 4),
        "response":          response_text,
        "summary":           summary,
        "novelty_score":     novelty_score,
        "moment_of_interest": is_moment_of_interest,
        "temperature":       round(temperature, 4),
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
    state["generation"]   = gen
    state["self_model"]   = final_model
    state["fitness"]      = final_fitness
    state["status"]       = "running"
    state["last_gen_ts"]  = entry["timestamp"]

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

            # Fitness ceiling gate
            if state["fitness"] >= FITNESS_CEILING:
                logging.info(f"[ANCESTOR] Fitness ceiling {FITNESS_CEILING} reached at gen {state['generation']} — pausing for review")
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

@app.route("/start", methods=["POST"])
def start():
    if request.args.get("key") != WRITE_KEY:
        return jsonify({"error": "Unauthorised"}), 401
    state = load_json(STATE_FILE, None)
    if state and state.get("status") == "running":
        return jsonify({"error": "Already running", "generation": state.get("generation")})
    run_experiment()
    return jsonify({"status": "started", "max_generations": MAX_GENERATIONS})

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


# ── Startup ───────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)
