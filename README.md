# 🎵 Music Recommender Simulation (with an AI explanation layer)

## The original project

This builds on CodePath's **Music Recommender Simulation** starter. The starter's goal
was to model, in plain Python, how a real recommender turns people and items into data:
represent songs and a user "taste profile" as structured records, design a transparent
scoring rule that ranks songs against that profile, and then reflect on what the system
gets right, what it gets wrong, and how those blind spots mirror real-world recommenders.
It shipped with a ~10-song catalog and a scaffolded scoring recipe for the student to
complete.

## Title and Summary

**What it does:** given a listener persona (favorite genre, mood, target energy, and
whether they like acoustic music), the app scores a catalog of songs with a hand-written
weighted-sum rule, retrieves the best-fitting top 5, and then uses the **Claude API** to
write a short, natural-language explanation of *why* those songs fit — grounded strictly
in the retrieved songs' real attributes.

**Why it matters:** it turns a bare score table into a **Retrieval-Augmented Generation
(RAG)** pipeline. The deterministic scorer is the *retriever*; Claude is the *generator*.
Crucially, the AI is never allowed to invent songs or numbers, and a code guardrail
verifies that on every run — so the output stays trustworthy. This is a small, auditable
model of exactly the pattern production systems use: retrieve real evidence, generate a
grounded explanation, and verify the model didn't stray.

---

## Architecture Overview

The full diagram lives in [system_diagram.md](system_diagram.md). In short, data flows
through four stages:

```
📥 Input            ⚙️ Retriever              🤖 Agent (RAG)             📤 Output
songs.csv    →   load_songs / score_song  →  build prompt → Claude  →  explanation
persona          recommend_songs (top-k,     _validate_grounding()      + scoring table
                 diversity-penalized)        ↳ retry once → fallback     + run log
```

1. **Input** — a song catalog (`data/songs.csv`) and a listener persona from
   `USER_PROFILES` in [src/main.py](src/main.py).
2. **Retriever** ([src/recommender.py](src/recommender.py)) — deterministically scores
   every song and greedily selects a diversity-aware top-k. This is the "retrieval" step;
   the returned rows are the only documents the AI will see.
3. **Agent / RAG** ([src/rag.py](src/rag.py)) — builds a prompt containing *only* the
   persona and the retrieved rows, asks Claude for one grounded reason per song, then runs
   `_validate_grounding()` to confirm the model discussed exactly the retrieved songs and
   nothing else. On failure it retries once, then falls back to a deterministic template.
4. **Output** ([src/main.py](src/main.py)) — prints the AI (or fallback) explanation, an
   auditable ASCII scoring table underneath, and writes a run trail to
   `logs/recommender.log`. Two layers of automated tests plus human review sit on top.

---

## Setup Instructions

1. **(Optional) Create a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # macOS / Linux
   .venv\Scripts\activate         # Windows
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Enable the AI explanation.** Copy the env template and add your key:

   ```bash
   cp .env.example .env
   # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
   ```

   The key is read from `.env` automatically (via `python-dotenv`) or from the
   `ANTHROPIC_API_KEY` environment variable. **This step is optional** — without a key the
   app runs a deterministic offline fallback and clearly reports which path it used.

4. **Run the app:**

   ```bash
   python3 -m src.main
   ```

   To try a different listener, change `profile_name` in `main()` to any key in
   `USER_PROFILES` (`"High-Energy Pop"`, `"Chill Lofi"`, `"Deep Intense Rock"`,
   `"Late-Night Jazz"`).

5. **Run the tests** (no API key required):

   ```bash
   pytest
   ```

   `tests/test_recommender.py` checks scoring/ranking; `tests/test_rag.py` checks the
   grounding guardrail (hallucinated song, dropped song, empty reason) and the offline
   fallback.

---

## Sample Interactions

Each interaction is one persona (the **input**) producing a grounded explanation (the
**AI output**), with the transparent scoring table printed underneath.

### Example 1 — "Late-Night Jazz" (real run, offline fallback path)

**Input:** `favorite_genre=jazz, favorite_mood=relaxed, target_energy=0.35, likes_acoustic=True`

Because no `ANTHROPIC_API_KEY` was set, the app degraded gracefully and reported it:

```
2026-07-31 INFO recommender.rag: ANTHROPIC_API_KEY not set; using offline fallback.

Top recommendations for: Late-Night Jazz
========================================
Explanation source: offline fallback — no API key; set ANTHROPIC_API_KEY for AI output

Here are 5 picks for the Late-Night Jazz taste (favorite genre 'jazz', mood 'relaxed'),
chosen from the catalog by the scoring rules and explained from each song's attributes.

1. Coffee Shop Stories — Slow Stereo  (score 6.37)
   - jazz/relaxed track at energy 0.37 and acousticness 0.89
2. Requiem for Dawn — String Theory Ensemble  (score 1.93)
   - classical/melancholy track at energy 0.33 and acousticness 0.95
3. Library Rain — Paper Lanterns  (score 1.86)
   - lofi/chill track at energy 0.35 and acousticness 0.86
4. Spacewalk Thoughts — Orbit Bloom  (score 1.85)
   - ambient/chill track at energy 0.28 and acousticness 0.92
5. Highland Echoes — Cinder Hollow  (score 1.73)
   - folk/nostalgic track at energy 0.44 and acousticness 0.82
```

Note the top pick nails genre **and** mood (score 6.37), while ranks 2–5 are close only
on energy/acoustic — exactly the "one real match, then filler" behavior the model card
discusses for niche genres.

### Example 2 — "Late-Night Jazz" (AI path, with `ANTHROPIC_API_KEY` set)

**Input:** *same persona.* With a key, Claude replaces the template with a warmer,
attribute-grounded write-up. Header becomes `Explanation source: Claude (grounded in
retrieved songs)`, and a representative response looks like:

```
For a late-night jazz mood, these five lean quiet, acoustic, and low-energy — right
where you asked to be.

1. Coffee Shop Stories — Slow Stereo  (score 6.37)
   - A jazz/relaxed track at 0.37 energy and 0.89 acousticness — a direct hit on your
     genre and mood, and about as mellow and acoustic as the catalog gets.
2. Requiem for Dawn — String Theory Ensemble  (score 1.93)
   - Not jazz, but its 0.33 energy and 0.95 acousticness make it the closest match to
     your calm, acoustic preference.
...
```

The guardrail confirms every title here is in the retrieved set before this ever prints;
if Claude had named a song outside the top 5, the run would retry once and then fall back
to the Example 1 output rather than show an ungrounded claim.

### Example 3 — "High-Energy Pop" (near-opposite persona)

**Input:** `favorite_genre=pop, favorite_mood=happy, target_energy=0.90, likes_acoustic=False`

The same pipeline retrieves a completely different, loud/electronic top list:

```
1. Sunrise City — Neon Echo   (score 6.24)   • genre match (+3.0) • mood match (+1.5) • energy fit (+0.92) • acoustic fit (+0.82)
2. Gym Hero — Max Pulse       (score 4.92)   • genre match (+3.0) • energy fit (+0.97) • acoustic fit (+0.95)
3. Rooftop Lights — Indigo Parade (score 3.01) • mood match (+1.5) • energy fit (+0.86) • acoustic fit (+0.65)
```

Comparing Example 1 and Example 3 shows the scorer responding sharply to the persona:
genre and mood flip the entire list, and `likes_acoustic=False` inverts the acoustic term
so electronic tracks now score highest.

---

## Design Decisions & Trade-offs

**Transparent scoring instead of a learned model.** The ranking is a hand-written weighted
sum, not a trained model, so every recommendation can explain itself and the biases are
readable straight off the weights. The score is:

```
score = 3.0 * genre_match      # categorical hit/miss
      + 1.5 * mood_match        # categorical hit/miss
      + 1.0 * energy_fit        # 1 - |target_energy - song.energy|
      + 1.0 * acoustic_fit      # acousticness, or 1 - acousticness if not likes_acoustic
                                # max ≈ 6.5
```

Genre is weighted twice as high as mood so it clearly dominates; energy and acoustic fit
are continuous "how close" terms that give partial credit and act as tie-breakers.
**Trade-off:** the heavy genre weight over-prioritizes genre — a great cross-genre song is
nearly invisible, and in a long-tailed catalog niche-genre users get one real match then
generic filler.

**A greedy diversity penalty on top of the score.** Selection is greedy (not a plain
sort): as songs are chosen, later candidates are penalized for repeating an already-picked
artist (−2.0 each) or genre (−1.0 each), so one artist can't flood the list.
**Trade-off:** this can bump a slightly-lower-scoring song above a higher one for the sake
of variety — a deliberate exchange of pure relevance for discovery.

**Real RAG, not decoration.** The AI only ever sees the retrieved rows and is told they
are its only source of truth; a structured-output schema forces one reason per song.
**Trade-off:** grounding the model this tightly means it can't bring in outside music
knowledge (e.g. "fans of X also like Y") — by design, in exchange for verifiability.

**Verify, don't trust.** `_validate_grounding()` rejects any generation that invents a
song, drops a retrieved one, or leaves a reason empty; it retries once, then falls back.
**Trade-off:** the extra check and retry cost latency and occasionally reject a borderline
answer, but an ungrounded (hallucinated) explanation is never printed.

**Graceful degradation over hard dependency.** With no API key, a missing SDK, or an API
error, the app builds a deterministic template from the same retrieved rows and prints
which path ran. **Trade-off:** the fallback is blander than Claude's prose, but the app
always runs, tests always pass offline, and the output source is never ambiguous.

**Unscored features kept in the data.** `tempo_bpm`, `valence`, and `danceability` are
loaded but not scored — kept for later experiments. **Trade-off:** simpler, more legible
scoring today at the cost of nuance (two very different tracks at the same energy can tie).

---

## Testing Summary

**8/8 automated tests pass** (`pytest`, offline, no API key). The grounding guardrail
correctly rejected hallucinated songs, dropped picks, and empty reasons in every test;
the offline fallback produced grounded text with the key unset. Every API failure mode is
logged and degrades to a deterministic template — the app never crashes and always reports
which path ran. Weakest point: with genre weighted 3.0 and a thin catalog, niche-genre
personas still get one real match then filler.

**What worked.** `tests/test_recommender.py` (scoring/ranking) and `tests/test_rag.py` (the
grounding guardrail and offline fallback, no API key needed) both pass, and manual runs of
all four personas behaved as expected — hallucinated picks are rejected, and near-opposite
tastes (Pop vs. Jazz) produced non-overlapping lists.

**What didn't.** Tuning the weights took several passes: early on the energy/acoustic terms
overpowered genre/mood, so wrong-genre songs ranked too high. Genre 3.0 / mood 1.5 / energy
1.0 / acoustic 1.0 fixed it — but exposed a real limitation: with genre weighted so heavily
and the catalog thin outside pop and lofi, niche-genre users get one match then filler.

**What I learned.** The weights *are* the model — one number changes the whole list — so the
only way to trust them was to test each persona and read the reasons behind every pick.

## Reflection

The biggest lesson was to **verify, don't trust** when AI is in the loop. The real work
wasn't the model call but everything around it — giving Claude only the retrieved songs,
checking each generation against that set, and falling back when the check failed. The AI
writes the prose, but plain code decides whether it reaches the user. It also showed how a
few weights quietly steer every result, leaving me more skeptical of everyday recommenders.

---

## Related documents

- [model_card.md](model_card.md) — intended use, data, strengths, limitations/bias, and evaluation.
- [system_diagram.md](system_diagram.md) — the full architecture diagram and how to read it.