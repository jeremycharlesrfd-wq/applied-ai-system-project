# 🎵 Music Recommender Simulation (with an AI explanation layer)

## The original project

This builds on CodePath's **Music Recommender Simulation** starter. The starter's goal
was to model, in plain Python, how a real recommender turns people and items into data:
represent songs and a user "taste profile" as structured records, design a transparent
scoring rule that ranks songs against that profile, and then reflect on what the system
gets right, what it gets wrong, and how those blind spots mirror real-world recommenders.
It shipped with a ~10-song catalog and a scaffolded scoring recipe for the student to
complete.

Github link: https://github.com/jeremycharlesrfd-wq/applied-ai-system-project

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
2. Gym Hero — Max Pulse       (score 3.92)   • genre match (+3.0) • energy fit (+0.97) • acoustic fit (+0.95) • genre repeat (-1.0)
3. Rooftop Lights — Indigo Parade (score 3.01) • mood match (+1.5) • energy fit (+0.86) • acoustic fit (+0.65)
```

(These are the real captured numbers — see the full run in
[Reproducible Execution Evidence](#reproducible-execution-evidence) below.)

Comparing Example 1 and Example 3 shows the scorer responding sharply to the persona:
genre and mood flip the entire list, and `likes_acoustic=False` inverts the acoustic term
so electronic tracks now score highest.

---

## Reproducible Execution Evidence

Each block below was produced by running the exact command shown, on Python 3.13.7 / macOS, with **no
`ANTHROPIC_API_KEY` set** (so every run takes the deterministic offline-fallback path and
is byte-for-byte reproducible). The raw logs are committed under
[docs/evidence/](docs/evidence/) so anyone can diff their own run against them:

| Evidence | Command | Captured log |
|---|---|---|
| Test suite (reliability) | `python3 -m pytest -v` | [pytest.txt](docs/evidence/pytest.txt) |
| Default run — Late-Night Jazz | `python3 -m src.main` | [run_main_default.txt](docs/evidence/run_main_default.txt) |
| Second persona — High-Energy Pop | `python3 -c "…"` (below) | [run_high_energy_pop.txt](docs/evidence/run_high_energy_pop.txt) |
| Grounding guardrail outcomes | `python3 -c "…"` (below) | [guardrail.txt](docs/evidence/guardrail.txt) |
| Run trail | (written by every run) | [recommender.log.txt](docs/evidence/recommender.log.txt) |

To regenerate all of them yourself:

```bash
python3 -m pytest -v            # reliability / guardrail unit tests
python3 -m src.main             # default persona, full pipeline + table
```

### 1. Test suite — reliability & guardrail results

**Command:**

```bash
python3 -m pytest -v
```

**Output** (verbatim, [docs/evidence/pytest.txt](docs/evidence/pytest.txt)):

```text
============================= test session starts ==============================
platform darwin -- Python 3.13.7, pytest-9.0.3, pluggy-1.6.0
collecting ... collected 8 items

tests/test_rag.py::test_grounding_passes_when_titles_match PASSED        [ 12%]
tests/test_rag.py::test_grounding_catches_hallucinated_song PASSED       [ 25%]
tests/test_rag.py::test_grounding_catches_dropped_song PASSED            [ 37%]
tests/test_rag.py::test_grounding_catches_empty_reason PASSED            [ 50%]
tests/test_rag.py::test_fallback_runs_without_api_key PASSED             [ 62%]
tests/test_rag.py::test_empty_recommendations_handled PASSED             [ 75%]
tests/test_recommender.py::test_recommend_returns_songs_sorted_by_score PASSED [ 87%]
tests/test_recommender.py::test_explain_recommendation_returns_non_empty_string PASSED [100%]

============================== 8 passed in 0.34s ===============================
```

All 8 tests pass with no API key: 4 assert the grounding guardrail rejects hallucinated /
dropped / empty picks and accepts a valid set, 2 assert the offline fallback and empty-input
paths, and 2 assert scoring/ranking.

### 2. Default run — full pipeline (Late-Night Jazz)

**Command:**

```bash
python3 -m src.main
```

**Input persona:** `favorite_genre=jazz, favorite_mood=relaxed, target_energy=0.35, likes_acoustic=True`

**Output** (verbatim, [docs/evidence/run_main_default.txt](docs/evidence/run_main_default.txt)):

```text
2026-08-02 16:00:26,988 INFO recommender.rag: ANTHROPIC_API_KEY not set; using offline fallback.

Top recommendations for: Late-Night Jazz
========================================
Explanation source: offline fallback — no API key; set ANTHROPIC_API_KEY for AI output

_Here are 5 picks for the Late-Night Jazz taste (favorite genre 'jazz', mood 'relaxed'), chosen from the catalog by the scoring rules and explained straight from each song's attributes._

1. **Coffee Shop Stories** — Slow Stereo  (score 6.37)
   - jazz/relaxed track at energy 0.37 and acousticness 0.89
2. **Requiem for Dawn** — String Theory Ensemble  (score 1.93)
   - classical/melancholy track at energy 0.33 and acousticness 0.95
3. **Library Rain** — Paper Lanterns  (score 1.86)
   - lofi/chill track at energy 0.35 and acousticness 0.86
4. **Spacewalk Thoughts** — Orbit Bloom  (score 1.85)
   - ambient/chill track at energy 0.28 and acousticness 0.92
5. **Highland Echoes** — Cinder Hollow  (score 1.73)
   - folk/nostalgic track at energy 0.44 and acousticness 0.82

Scoring detail
--------------
+----+--------------------------+--------------------+--------+------------------------------------+
| #  | Title                    | Artist             | Score  | Reasons                            |
+----+--------------------------+--------------------+--------+------------------------------------+
| 1  | Coffee Shop Stories      | Slow Stereo        | 6.37   | genre match (+3.0)                 |
|    |                          |                    |        | mood match (+1.5)                  |
|    |                          |                    |        | energy fit (+0.98)                 |
|    |                          |                    |        | acoustic fit (+0.89)               |
+----+--------------------------+--------------------+--------+------------------------------------+
| 2  | Requiem for Dawn         | String Theory Ens… | 1.93   | energy fit (+0.98)                 |
|    |                          |                    |        | acoustic fit (+0.95)               |
+----+--------------------------+--------------------+--------+------------------------------------+
| 3  | Library Rain             | Paper Lanterns     | 1.86   | energy fit (+1.00)                 |
|    |                          |                    |        | acoustic fit (+0.86)               |
+----+--------------------------+--------------------+--------+------------------------------------+
| 4  | Spacewalk Thoughts       | Orbit Bloom        | 1.85   | energy fit (+0.93)                 |
|    |                          |                    |        | acoustic fit (+0.92)               |
+----+--------------------------+--------------------+--------+------------------------------------+
| 5  | Highland Echoes          | Cinder Hollow      | 1.73   | energy fit (+0.91)                 |
|    |                          |                    |        | acoustic fit (+0.82)               |
+----+--------------------------+--------------------+--------+------------------------------------+
```

### 3. Second persona — High-Energy Pop (same pipeline, different input)

To exercise a different persona without editing `main()`, drive the real pipeline
functions directly. This is the exact command that produced
[docs/evidence/run_high_energy_pop.txt](docs/evidence/run_high_energy_pop.txt):

**Command:**

```bash
python3 -c "
from src.main import USER_PROFILES, _format_table
from src.recommender import load_songs, recommend_songs
from src.rag import explain_recommendations

name = 'High-Energy Pop'
prefs = USER_PROFILES[name]
songs = load_songs('data/songs.csv')
recs = recommend_songs(prefs, songs, k=5)
text, used_ai = explain_recommendations(name, prefs, recs)
print('Input persona:', name, prefs)
print('Explanation source:', 'Claude' if used_ai else 'offline fallback')
print(); print(text); print(); print(_format_table(recs))
"
```

**Input persona:** `favorite_genre=pop, favorite_mood=happy, target_energy=0.9, likes_acoustic=False`

**Output** (excerpt — full table in the log file):

```text
Input persona: High-Energy Pop {'favorite_genre': 'pop', 'favorite_mood': 'happy', 'target_energy': 0.9, 'likes_acoustic': False}
Explanation source: offline fallback

_Here are 5 picks for the High-Energy Pop taste (favorite genre 'pop', mood 'happy'), chosen from the catalog by the scoring rules and explained straight from each song's attributes._

1. **Sunrise City** — Neon Echo  (score 6.24)
   - pop/happy track at energy 0.82 and acousticness 0.18
2. **Gym Hero** — Max Pulse  (score 3.92)
   - pop/intense track at energy 0.93 and acousticness 0.05
3. **Rooftop Lights** — Indigo Parade  (score 3.01)
   - indie pop/happy track at energy 0.76 and acousticness 0.35
4. **Basslight** — Deep Circuit  (score 1.91)
   - drum and bass/euphoric track at energy 0.95 and acousticness 0.04
5. **Iron Verdict** — Grave Meridian  (score 1.91)
   - metal/aggressive track at energy 0.97 and acousticness 0.02
```

Two things to note in the *real* numbers: the Pop list shares **zero** titles with the Jazz
list (the persona flips the whole ranking), and **Gym Hero** lands at 3.92 — a full 1.0 below
its raw score — because the diversity penalty deducts `genre repeat (-1.0)` for being the
second `pop` track chosen. That deduction is visible in the `Reasons` column of the committed
log, and is exactly the "relevance-for-variety" trade-off described below.

### 4. Reliability / guardrail results (the verifier in action)

This drives `_validate_grounding()` — the code that decides whether Claude's output is
allowed to reach the user — through one valid and three invalid generations. Captured in
[docs/evidence/guardrail.txt](docs/evidence/guardrail.txt):

**Command:**

```bash
python3 -c "
from src.rag import _validate_grounding
recs = [({'title': 'Coffee Shop Stories'}, 6.37, ''),
        ({'title': 'Requiem for Dawn'},   1.93, '')]
cases = {
  'GOOD  (both titles match)': [
      {'title': 'Coffee Shop Stories', 'reason': 'jazz/relaxed, 0.37 energy.'},
      {'title': 'Requiem for Dawn',   'reason': 'acousticness 0.95 fits.'}],
  'BAD   (hallucinated song)': [
      {'title': 'Coffee Shop Stories', 'reason': 'grounded.'},
      {'title': 'Imaginary Track',     'reason': 'never retrieved.'}],
  'BAD   (dropped a pick)': [
      {'title': 'Coffee Shop Stories', 'reason': 'only one of two.'}],
  'BAD   (empty reason)': [
      {'title': 'Coffee Shop Stories', 'reason': 'fine.'},
      {'title': 'Requiem for Dawn',   'reason': '   '}]}
for label, picks in cases.items():
    ok, issues = _validate_grounding(picks, recs)
    verdict = 'PASS -> printed to user' if ok else 'REJECT -> retry, then fallback'
    print(f'{label:32} {verdict}')
    for i in issues: print(f'      reason: {i}')
"
```

**Output** (verbatim):

```text
Retrieved (only valid) titles: ['Coffee Shop Stories', 'Requiem for Dawn']

GOOD  (both titles match)        PASS -> printed to user
BAD   (hallucinated song)        REJECT -> retry, then fallback
      reason: cited songs not in retrieved set: ['Imaginary Track']
      reason: did not explain retrieved songs: ['Requiem for Dawn']
BAD   (dropped a pick)           REJECT -> retry, then fallback
      reason: did not explain retrieved songs: ['Requiem for Dawn']
BAD   (empty reason)             REJECT -> retry, then fallback
      reason: empty reason for: ['Requiem for Dawn']
```

Only the fully-grounded generation is allowed through; a hallucinated song, a dropped pick,
or an empty reason is each rejected with a specific issue string. In the live pipeline a
`REJECT` triggers one retry and then the deterministic fallback (Evidence 2) — so an
ungrounded explanation is **never** printed.

### 5. Run trail (audit log)

Every run appends a timestamped line to `logs/recommender.log`, recording which path ran
(and, on the AI path, model + token usage + guardrail result). The offline runs above
produced ([docs/evidence/recommender.log.txt](docs/evidence/recommender.log.txt)):

```text
2026-08-02 16:00:26,988 INFO recommender.rag: ANTHROPIC_API_KEY not set; using offline fallback.
```

> **AI path:** with `ANTHROPIC_API_KEY` set, the header becomes
> `Explanation source: Claude (grounded in retrieved songs)`, the prose is Claude's, and the
> log gains `Requesting grounded explanation…`, `Token usage: input=… output=…`, and
> `Grounding guardrail passed on attempt 1` lines. Every title is still checked by the same
> `_validate_grounding()` verified above before it prints.

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