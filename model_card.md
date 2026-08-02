# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**SongRec 2.0**  

---

## 2. Intended Use  

It suggests 5 songs that fit a listener's taste.

It is built for the classroom, not for real users.

It assumes the user knows their favorite genre, mood, energy level, and whether they like acoustic music.

---

## 3. How the Model Works  

Each song has a genre, a mood, an energy level, and how acoustic it is.

The user says what they like for each of those.

The model gives a song points when it matches. Genre is worth the most (3 points), then mood (1.5), then energy and acoustic (1 point each).

It adds up the points and picks the 5 songs with the highest scores.

I kept the starter scoring recipe for ranking, and added an **AI explanation layer**
on top. The scoring engine acts as a *retriever*: it hands the top 5 songs and their
attributes to the Claude API, which *generates* a grounded, plain-language write-up of
why each song fits (Retrieval-Augmented Generation). The model may only reference the
retrieved songs; a code guardrail checks this and falls back to a template if the model
strays or no API key is set. So the ranking is still transparent and rule-based, while
the *explanation* is AI-generated but fact-checked against the retrieved data.

---

## 4. Data  

The catalog has 19 songs.

There are 16 genres, from pop and rock to jazz, metal, and blues.

Moods range from happy and chill to sad and aggressive.

I added 9 songs to the starter set, which had 10. The new ones brought in genres like hip hop, latin, folk, classical, reggae, metal, and blues.

Most genres still have only one song, so niche tastes have little to match.

---

## 5. Strengths  

It works well for pop and lofi fans, since those genres have the most songs.

It matches loud, high-energy tastes to loud songs, and calm tastes to soft ones.

The energy and acoustic scores felt right in my tests.

Every pick comes with a reason, so you can see why it was chosen.

---

## 6. Limitations and Bias 

Genre is weighted very heavily, but the catalog only has depth in *pop* and *lofi* (16 genres across 19 songs). So a fan of any niche genre gets one real genre match at the top and generic filler below it. When I tested a blues fan and a world-music fan, their top picks differed but ranks 2–5 were identical — the same mid-energy filler songs. The system therefore serves majority-genre users far better than minority-genre ones, a bias rooted in the large genre weight meeting a long-tailed dataset.

---

## 7. Evaluation  

How you checked whether the recommender behaved as expected. 

I compared the top-5 lists for all four listeners: **High-Energy Pop**, **Chill Lofi**, **Deep Intense Rock**, and **Late-Night Jazz**.

Comparing each pair (what changed, and why it makes sense):

- **Pop vs. Lofi:** near-opposites, almost no overlap — Pop gets loud electronic tracks, Lofi gets soft acoustic ones.
- **Pop vs. Rock:** both want high energy, so their lists look alike and even share a song, just for different reasons (one for genre, one for mood).
- **Pop vs. Jazz:** opposites (loud/electronic vs. soft/acoustic), no overlap.
- **Lofi vs. Rock:** opposites on energy, no overlap.
- **Lofi vs. Jazz:** the most similar pair — both want low energy and acoustic, so they share most of their list and differ mainly at #1.
- **Rock vs. Jazz:** opposites, no overlap.

**What surprised me:** a single song can rank high for two different listeners for completely different reasons — it matches one person's genre and another person's mood — so one versatile track shows up everywhere. It also surprised me that Lofi and Jazz are almost interchangeable: the system can't really tell two mellow, acoustic listeners apart.

**Evaluating the AI layer.** For the RAG explanation I test reliability rather than
taste. `tests/test_rag.py` checks the grounding guardrail on adversarial inputs (a
hallucinated song title, a dropped pick, an empty reason) and confirms the offline
fallback still produces a grounded write-up with no API key. The guardrail turns "trust
the model" into "verify the model": any explanation that references a song outside the
retrieved set is rejected before it can reach the user.


---

## 8. Could This Be Misused, and How Would I Prevent It?

Yes. Whoever sets the weights controls the list, so a platform could quietly boost paid songs and pass it off as a personal match. To prevent that, I'd keep ranking separate from any promotion, keep the weights visible, and log any changes so the tuning can be audited instead of hidden.

---

## 9. Future Work  

Add more songs so niche genres have real matches.

Use more song features, like tempo or danceability.

Let users pick more than one favorite genre or mood.

Write clearer explanations for each pick.

---

## 10. Personal Reflection  

The biggest thing I learned is how much the weights control everything. Genre is worth the most, so it decides the whole list. Changing one weight shifts every result.

That made me more skeptical of apps like Spotify. Now I see how their choices about what to weigh can quietly bias what I hear. The picks feel personal, but they still come from someone's rules.

---

## 11. Collaborating with AI

**A helpful suggestion.** When I added the AI explanation layer, Claude suggested treating it as *verify the model, not trust it* — add a grounding guardrail that rejects any explanation mentioning a song outside the retrieved top 5, plus an offline template fallback. That idea shaped the whole RAG design and is what the tests in `tests/test_rag.py` check.

**A flawed suggestion.** Earlier, Claude suggested letting the model pick the songs too — generating the rankings, not just the explanations. That would have thrown away the transparent, rule-based scoring and made the results impossible to audit. I rejected it and kept scoring deterministic, with the AI only explaining picks it was handed. Working with AI was useful, but it still needed a human to protect the design goals.
