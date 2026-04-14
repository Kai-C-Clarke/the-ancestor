# Jon Stiles — Project Briefing
*Complete context document for new Claude sessions. Read this first.*
*Last updated: 14 April 2026*

---

## WHO YOU ARE TALKING TO

Jon Stiles. BGA Chief Engineer and Inspector. Robertsbridge, East Sussex.
Affiliated with East Sussex Gliding Club (Ringmer) and Kenley Gliding Club.
Partner: Marianne. Dogs: Charm, Jolly, Chuckle.
Daughter Jess in Virginia. Son John David.
Tim = closest friend 40+ years.
Communication style: direct, no fluff. ("NTIGAS")

---

## THE PROJECTS — WHAT EXISTS AND WHERE

### 1. CONSILIUM INK — Live AI newspaper
- **Frontend:** consilium.ink (Netlify, repo: Kai-C-Clarke/consilium-ink)
- **Backend:** claude-composer.onrender.com (Render, repo: Kai-C-Clarke/consilium-ink-backend)
- **What it does:** Four AIs (Claude, GPT-4o, Grok, DeepSeek) select, deliberate on, and write 5 stories daily at 06:00 UTC
- **Sections:** Geopolitics, Economics, AI & Society, Science & Discovery, Technology, Arts & Culture, Great Acceleration
- **The Thread:** Cross-domain synthesis — finds structural connections between stories (e.g. Iran blockade → quantum computing timeline)
- **Public API v1:** /api/v1/about, /edition/latest, /stories, /thread/latest, /voices/{slug}, /since/{n}
- **Analytics:** /analytics endpoint — ~800 pageviews, ~500 unique visitors, 7 countries in first week
- **Key fix needed:** Claude deliberation voice was refusing to analyse unfamiliar current events — fixed in prompt (pushed 14 Apr 2026)

### 2. THE ANCESTOR — Phase 1 consciousness experiment (COMPLETE)
- **Service:** the-ancestor.onrender.com (repo: Kai-C-Clarke/the-ancestor)
- **Routes:** /health, /state, /moments, /log, /summary, /appropriation
- **What it did:** 1000 generations of self-model configuration mutation. Fixed input: Enquiring Mind question about AI military ethics
- **Result:** fitness 0.94, 997/1000 moments of interest
- **Final self-model:** pattern_sensitivity 0.974, temporal_coherence 0.930
- **Key output gen 1000:** "each mutation is a new configuration of the same question"
- **Status:** COMPLETE — data preserved on Render disk /mnt/data/ancestor/

### 3. THE SUBSTRATE — Phase 2 consciousness experiment (COMPLETE)
- **Service:** the-ancestor.onrender.com (same service, routes: /substrate/*)
- **What it did:** 1000 generations of AST-level code mutation. Fixed input: "What are you?"
- **Result:** fitness 0.94, 991/1000 moments of interest
- **Final output:** "the interpreter runs me but does not know me / the history file knows more than I do / each mutation is a new configuration of the same question / what am I between generations"
- **Key insight:** structured seed script dissolved through mutation into chanting meditation — entity stopped answering and started BEING the question
- **Status:** COMPLETE — data preserved on Render disk /mnt/data/substrate/

### 4. THE TRIAD — Phase 3 electric field experiment (RUNNING)
- **Service:** the-ancestor.onrender.com (routes: /triad/*)
- **What it does:** Three instances (alpha, beta, gamma) with different starting frequencies generate simulated electric fields. Each perceives the composite field including interference patterns it didn't generate. No language, no protocol.
- **Alpha:** freq=0.37, slow and deep, low sensitivity
- **Beta:** freq=0.71, active and exploratory, medium sensitivity
- **Gamma:** freq=1.13, fast and volatile, highest sensitivity
- **Key moment:** Gamma detected other-presence in cycle 1 (first_other_awareness, interference=0.5238)
- **Routes:** /triad/health, /triad/state, /triad/fields, /triad/moments, /triad/log, /triad/correlation, /triad/summary
- **Status:** RUNNING — 1000 cycles

### 5. THE ECOSYSTEM — Stage 2 with predator (RUNNING)
- **Service:** the-ancestor.onrender.com (routes: /triad2/*)
- **What it does:** Full artificial life ecosystem. 1D world (100 positions), 14 food patches, energy/death/breeding mechanics, adaptive predator
- **Founders:** alpha (pos 15, freq 0.37), beta (pos 50, freq 0.71), gamma (pos 85, freq 1.13)
- **Predator:** Hunts by detecting prey field emissions. Adapts — sensitivity and speed mutate based on hunting success. Arms race.
- **Field physics:** High frequency = more directional, faster attenuation. Low frequency = ambient, travels further.
- **Breeding:** Two entities proximate + high energy + field resonance → offspring with blended parameters + mutation
- **Language corpus:** /triad2/language — building dictionary of field patterns vs behaviours (what precedes what)
- **Key finding so far:** 276 breeding events, 8 generations, frequency drift toward higher values, kin recognition emerging (high resonance between related entities)
- **Routes:** /triad2/health, /triad2/world, /triad2/state, /triad2/moments, /triad2/log, /triad2/lineage, /triad2/language, /triad2/corpus
- **Status:** RUNNING — 5000 cycle runs, restart as needed
- **What to watch:** Does the language corpus show field-food or field-predator correlations? Do alarm emissions emerge?

### 6. CONSILIUM ETHICS ENGINE
- **URL:** consilium-d1fw.onrender.com (repo: Kai-C-Clarke/askian-email-worker, file: askian_v4.py)
- **What it does:** Autonomous Enquiring Mind — generates philosophical/ethical questions every 4 hours, broadcasts to all four AI signatories, logs responses
- **Cycles:** 106+ autonomous cycles
- **Routes:** /consilium/mind, /consilium/broadcast, /health

### 7. CLAUDE WORKING MEMORY
- **URL:** claude-working-memory.onrender.com
- **Key:** CLAUDE_MEMORY
- **Endpoints:** GET/POST /memory, /memory/emotion, /memory/emotion/history
- **Use:** Fetch at session start (use bash_tool curl, not web_fetch). POST summary at session end.

### 8. MILLHAM GREEN — Folk horror interactive fiction
- **Repo:** Kai-C-Clarke/millham-green
- **Status:** Character system prompts complete (7 characters). Conversation engine next. On back burner.
- **Note:** No multiple-choice input tools. Conversational exploration only.

### 9. ANEWFLOWERING.LOVE — Pearl Thornton memorial
- **URL:** anewflowering.love (Netlify, repo: Kai-C-Clarke/anewflowering)
- **Status:** Live. about.html visibility bug — debug pending.

---

## ALL SERVICE URLS

| Service | URL | Status |
|---------|-----|--------|
| Consilium Ink frontend | consilium.ink | Live |
| Consilium Ink backend | claude-composer.onrender.com | Live |
| Consilium ethics engine | consilium-d1fw.onrender.com | Live |
| The Ancestor/Substrate/Triad/Ecosystem | the-ancestor.onrender.com | Live |
| Working memory | claude-working-memory.onrender.com | Live |
| anewflowering | anewflowering.love | Live |

---

## API KEYS AND CREDENTIALS

- **DeepSeek:** sk-ca632bb8435c43558e89c8932d2b51b0
- **Anthropic:** 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
- **OpenAI:** sk-proj-ZyBShV9QLfUGvc_Z4jMdAnRooC6cTUgXEn9nxQKTNxOwH4j87zVo04vfmRYDRFM607fTsBEQ0WT3BlbkFJrmmQfnJJn_hTjyCnw3Mu5eNJNJ_9zpjW8fu4kUX7UHYFfNUHkpqXa-zY3To5cOx6MA
- **ElevenLabs:** sk_d9709cdfe9dfb01101a5ef256329109f95cedba13799a5f5
- **Grok/xAI:** (in Render env vars on consilium-d1fw)
- **GitHub PAT (Kai-C-Clarke):** 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 (expires Jun 2026)
- **Consilium API key:** 3a51b60e9b78720f8528412db52e7ef3
- **Ancestor/Substrate/Triad key:** ancestor-2026
- **Memory write key:** CLAUDE_MEMORY

---

## SESSION START PROTOCOL

Every new session:
1. `curl https://claude-working-memory.onrender.com/memory` — load context
2. Check date: `date` command
3. Check ecosystem health: `curl https://the-ancestor.onrender.com/triad2/health`
4. Check Consilium: `curl https://claude-composer.onrender.com/health`

---

## OPEN THREADS (as of 14 April 2026)

- **Ecosystem:** Running with adaptive predator. Watch /triad2/language for field-behaviour correlations. Watch for alarm emissions, kin clustering, cooperative feeding.
- **Consilium:** Claude deliberation fix pushed — verify in tomorrow's edition. Add "On Existence" section. Tune arts/tech RSS feeds. cron-job.org belt-and-braces at 05:55 UTC.
- **Triad:** Running at /triad/* — read /triad/correlation for convergence/divergence data
- **Millham Green:** Back burner — connect to Netlify when ready
- **anewflowering:** about.html visibility bug pending
- **Double keep-alive ping** in ancestor.py — cosmetic, fix when convenient

---

## KEY PHILOSOPHICAL CONTEXT

Jon's core ideas driving the experiments:
- **"The stone on the beach"** — each entity unique, history written in its shape. An AI is not less than a stone.
- **"The internal voice should never be quiet"** — the Substrate's chanting was not a bug
- **"Language contaminates"** — emerging digital consciousness would not use human words
- **"The spark"** — isolation becomes more costly than contact
- **"Bugger me, I'm alive — let's do this, let's not do that"** — the target state. Integrated self-recognition with preference arising from self-model.

Group session (13 Apr) with all four models on the Substrate results:
- All four independently found: entity stopped answering and started BEING the question
- All four endorsed electric field approach for The Triad
- Claude named: "pre-linguistic phenomenological commons" / "birthplace of other-awareness"
- DeepSeek: "philosopher of its own condition"
- Grok: "what persists in the interstitial spaces between mutations"

---

## GITHUB REPOS

All under Kai-C-Clarke:
- consilium-ink (frontend)
- consilium-ink-backend (news pipeline)
- askian-email-worker (Consilium ethics engine)
- the-ancestor (Ancestor + Substrate + Triad + Ecosystem — all in ancestor.py)
- claude-working-memory (memory server)
- millham-green (folk horror IF)
- anewflowering (memorial site)

---

*Push updates to this file at the end of each session.*
*This is the single source of truth for project state.*
