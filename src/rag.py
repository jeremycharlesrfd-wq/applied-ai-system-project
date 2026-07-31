"""
Retrieval-Augmented Generation (RAG) explanation layer.

The deterministic recommender in `recommender.py` is the **retriever**: it scores
the whole catalog and returns the top-k songs together with their full attributes.
Those retrieved rows — and nothing else — are handed to Claude, which **generates**
a grounded, natural-language write-up of why the picks fit the listener.

This is real RAG, not decoration: Claude never sees the full catalog and is told the
retrieved rows are its only source of truth. We then *verify* that grounding in code
(`_validate_grounding`) — if the model names a song outside the retrieved set, or
skips one, we reject the answer and fall back rather than print an ungrounded claim.

Guardrails & reliability:
- **Grounding check** on every generation; one retry, then deterministic fallback.
- **Graceful degradation**: no ANTHROPIC_API_KEY, missing SDK, or any API error →
  a template write-up built from the same retrieved rows, so the app always runs.
- **Logging**: retrieval, model call, token usage, guardrail results, and fallbacks
  are logged to `logs/recommender.log` and the console.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("recommender.rag")

# A recommendation is (song_dict, score, scoring_explanation) — see recommender.py.
Recommendation = Tuple[Dict, float, str]

DEFAULT_MODEL = "claude-opus-4-8"

# Attributes exposed to the model as the "retrieved document" for each song. These are
# the only facts the model may cite; keeping the list explicit keeps grounding checkable.
_GROUNDED_FIELDS = (
    "title", "artist", "genre", "mood",
    "energy", "tempo_bpm", "valence", "danceability", "acousticness",
)

SYSTEM_PROMPT = (
    "You are a music concierge. You explain, warmly and concisely, why a short list "
    "of songs was recommended to a listener with a known taste profile.\n\n"
    "You are given (1) the listener's taste profile and (2) a list of RETRIEVED songs "
    "with their attributes. The retrieved songs are your ONLY source of truth.\n\n"
    "Rules:\n"
    "- Mention ONLY songs that appear in the retrieved list. Never invent a song, an "
    "artist, or an attribute value.\n"
    "- Ground every claim in the provided attributes (genre, mood, energy 0-1, "
    "acousticness 0-1, tempo in BPM, valence 0-1, danceability 0-1). Refer to the real "
    "numbers when they support the point (e.g. 'low 0.35 energy').\n"
    "- Provide exactly one 'reason' per retrieved song, in the same order, and set each "
    "'title' to the song's exact title from the list.\n"
    "- Keep the intro to one or two sentences and each reason to one or two sentences."
)


# ---------------------------------------------------------------------------
# Retrieval-context construction
# ---------------------------------------------------------------------------
def _format_profile(profile_name: str, user_prefs: Dict) -> str:
    """Render the listener taste profile as a compact block for the prompt."""
    return (
        f"Listener persona: {profile_name}\n"
        f"- favorite_genre: {user_prefs.get('favorite_genre')}\n"
        f"- favorite_mood: {user_prefs.get('favorite_mood')}\n"
        f"- target_energy: {user_prefs.get('target_energy')} (0.0 calm -> 1.0 high)\n"
        f"- likes_acoustic: {user_prefs.get('likes_acoustic')}"
    )


def _format_retrieved(recommendations: List[Recommendation]) -> str:
    """
    Render the retrieved songs as the grounding context (the "documents").

    Only `_GROUNDED_FIELDS` plus the deterministic score/reasons are exposed, so the
    model has exactly — and only — the facts we later verify it stayed within.
    """
    lines = []
    for rank, (song, score, scoring_reasons) in enumerate(recommendations, start=1):
        attrs = ", ".join(f"{f}={song[f]}" for f in _GROUNDED_FIELDS if f in song)
        lines.append(
            f"{rank}. {attrs}\n"
            f"   score={score:.2f}; rule_reasons=[{scoring_reasons}]"
        )
    return "\n".join(lines)


def _build_user_message(profile_name: str, user_prefs: Dict,
                        recommendations: List[Recommendation]) -> str:
    return (
        f"{_format_profile(profile_name, user_prefs)}\n\n"
        f"RETRIEVED songs (your only source of truth):\n"
        f"{_format_retrieved(recommendations)}\n\n"
        "Write the grounded recommendation explanation now."
    )


# ---------------------------------------------------------------------------
# Guardrail: verify the generation is grounded in the retrieved rows
# ---------------------------------------------------------------------------
def _validate_grounding(picks: List[Dict], recommendations: List[Recommendation]
                        ) -> Tuple[bool, List[str]]:
    """
    Confirm the model only talked about songs we actually retrieved.

    `picks` is a list of {"title", "reason"} dicts. Returns (ok, issues). We reject if
    the model named a title outside the retrieved set (hallucination) or failed to
    cover a retrieved song (dropped a pick). Both make the write-up untrustworthy.
    """
    retrieved_titles = {song["title"] for song, _, _ in recommendations}
    cited_titles = {p.get("title", "") for p in picks}
    issues: List[str] = []

    invented = cited_titles - retrieved_titles
    if invented:
        issues.append(f"cited songs not in retrieved set: {sorted(invented)}")

    missing = retrieved_titles - cited_titles
    if missing:
        issues.append(f"did not explain retrieved songs: {sorted(missing)}")

    empty = [p.get("title", "?") for p in picks if not p.get("reason", "").strip()]
    if empty:
        issues.append(f"empty reason for: {empty}")

    return (not issues), issues


# ---------------------------------------------------------------------------
# Deterministic offline fallback (no API key / SDK / on error)
# ---------------------------------------------------------------------------
def _fallback_writeup(profile_name: str, user_prefs: Dict,
                      recommendations: List[Recommendation]) -> str:
    """
    Build an explanation from the retrieved rows without any model call.

    Uses the same grounded facts a model would get, so the app's behavior degrades
    gracefully instead of breaking when the API is unavailable.
    """
    genre = user_prefs.get("favorite_genre")
    mood = user_prefs.get("favorite_mood")
    intro = (
        f"Here are {len(recommendations)} picks for the {profile_name} taste "
        f"(favorite genre '{genre}', mood '{mood}'), chosen from the catalog by the "
        f"scoring rules and explained straight from each song's attributes."
    )
    lines = [f"_{intro}_", ""]
    for rank, (song, score, _) in enumerate(recommendations, start=1):
        reason = (
            f"{song['genre']}/{song['mood']} track at energy {song['energy']:.2f} "
            f"and acousticness {song['acousticness']:.2f}"
        )
        lines.append(f"{rank}. **{song['title']}** — {song['artist']}  "
                     f"(score {score:.2f})")
        lines.append(f"   - {reason}")
    return "\n".join(lines)


def _render_ai_writeup(intro: str, picks: List[Dict],
                       recommendations: List[Recommendation]) -> str:
    """Render a validated model write-up, pairing each reason with its score/artist."""
    by_title = {song["title"]: (song, score) for song, score, _ in recommendations}
    lines = [f"_{intro.strip()}_", ""]
    for rank, pick in enumerate(picks, start=1):
        song, score = by_title[pick["title"]]
        lines.append(f"{rank}. **{song['title']}** — {song['artist']}  "
                     f"(score {score:.2f})")
        lines.append(f"   - {pick['reason'].strip()}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------
def _generate_with_claude(profile_name: str, user_prefs: Dict,
                          recommendations: List[Recommendation],
                          model: str) -> Optional[str]:
    """
    Call Claude to generate a grounded write-up, validate it, and retry once.

    Returns the rendered markdown on success, or None to signal the caller to fall
    back. Every failure mode (missing SDK/key, API error, ungrounded output) is
    logged and turned into None rather than raised, so the CLI never crashes.
    """
    try:
        import anthropic
        from pydantic import BaseModel
    except ImportError:
        logger.warning("anthropic SDK not installed; using offline fallback.")
        return None

    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.info("ANTHROPIC_API_KEY not set; using offline fallback.")
        return None

    class _SongBlurb(BaseModel):
        title: str
        reason: str

    class _Writeup(BaseModel):
        intro: str
        picks: List[_SongBlurb]

    client = anthropic.Anthropic()
    user_message = _build_user_message(profile_name, user_prefs, recommendations)

    for attempt in (1, 2):
        try:
            logger.info("Requesting grounded explanation (model=%s, attempt=%d, "
                        "retrieved=%d songs)", model, attempt, len(recommendations))
            response = client.messages.parse(
                model=model,
                max_tokens=1500,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_message}],
                output_format=_Writeup,
            )
        except anthropic.APIError as exc:
            logger.error("Claude API error on attempt %d: %s", attempt, exc)
            continue

        usage = response.usage
        logger.info("Token usage: input=%s output=%s (cache_read=%s)",
                    usage.input_tokens, usage.output_tokens,
                    getattr(usage, "cache_read_input_tokens", 0))

        writeup = response.parsed_output
        if writeup is None:
            logger.warning("Model refused or returned no structured output "
                           "(stop_reason=%s).", response.stop_reason)
            continue

        picks = [{"title": p.title, "reason": p.reason} for p in writeup.picks]
        ok, issues = _validate_grounding(picks, recommendations)
        if ok:
            logger.info("Grounding guardrail passed on attempt %d.", attempt)
            return _render_ai_writeup(writeup.intro, picks, recommendations)

        logger.warning("Grounding guardrail FAILED on attempt %d: %s",
                       attempt, "; ".join(issues))

    logger.error("All generation attempts failed grounding; using offline fallback.")
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def explain_recommendations(profile_name: str, user_prefs: Dict,
                            recommendations: List[Recommendation],
                            model: Optional[str] = None) -> Tuple[str, bool]:
    """
    Produce a grounded, natural-language explanation of the retrieved recommendations.

    Returns (markdown_text, used_ai). `used_ai` is True when the Claude-generated,
    grounding-verified write-up was used, and False when the deterministic fallback
    was used — the CLI surfaces this so it's always clear which path ran.
    """
    if not recommendations:
        return "_No songs matched this profile._", False

    model = model or os.getenv("RECOMMENDER_MODEL", DEFAULT_MODEL)
    ai_writeup = _generate_with_claude(profile_name, user_prefs,
                                       recommendations, model)
    if ai_writeup is not None:
        return ai_writeup, True

    return _fallback_writeup(profile_name, user_prefs, recommendations), False