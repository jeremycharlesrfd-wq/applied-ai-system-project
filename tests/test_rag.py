"""
Reliability tests for the RAG explanation layer (src/rag.py).

These cover the two pieces that make the AI feature trustworthy without needing a
live API key: the grounding guardrail (does it catch hallucinated / dropped songs?)
and the offline fallback (does the app still produce a grounded write-up with no key?).
"""
import src.rag as rag


def _sample_recommendations():
    """Two retrieved rows in the (song_dict, score, reasons) shape main.py passes."""
    return [
        (
            {
                "id": 7, "title": "Coffee Shop Stories", "artist": "Slow Stereo",
                "genre": "jazz", "mood": "relaxed", "energy": 0.37, "tempo_bpm": 90,
                "valence": 0.71, "danceability": 0.54, "acousticness": 0.89,
            },
            6.37,
            "genre match (+3.0), mood match (+1.5)",
        ),
        (
            {
                "id": 15, "title": "Requiem for Dawn", "artist": "String Theory Ensemble",
                "genre": "classical", "mood": "melancholy", "energy": 0.33,
                "tempo_bpm": 66, "valence": 0.28, "danceability": 0.22,
                "acousticness": 0.95,
            },
            1.93,
            "energy fit (+0.98), acoustic fit (+0.95)",
        ),
    ]


def test_grounding_passes_when_titles_match():
    recs = _sample_recommendations()
    picks = [
        {"title": "Coffee Shop Stories", "reason": "jazz/relaxed at 0.37 energy."},
        {"title": "Requiem for Dawn", "reason": "acousticness 0.95 fits the mood."},
    ]
    ok, issues = rag._validate_grounding(picks, recs)
    assert ok, issues


def test_grounding_catches_hallucinated_song():
    recs = _sample_recommendations()
    picks = [
        {"title": "Coffee Shop Stories", "reason": "grounded."},
        {"title": "Imaginary Track", "reason": "this song was never retrieved."},
    ]
    ok, issues = rag._validate_grounding(picks, recs)
    assert not ok
    assert any("not in retrieved set" in i for i in issues)


def test_grounding_catches_dropped_song():
    recs = _sample_recommendations()
    picks = [{"title": "Coffee Shop Stories", "reason": "only one of two picks."}]
    ok, issues = rag._validate_grounding(picks, recs)
    assert not ok
    assert any("did not explain" in i for i in issues)


def test_grounding_catches_empty_reason():
    recs = _sample_recommendations()
    picks = [
        {"title": "Coffee Shop Stories", "reason": "fine."},
        {"title": "Requiem for Dawn", "reason": "   "},
    ]
    ok, issues = rag._validate_grounding(picks, recs)
    assert not ok
    assert any("empty reason" in i for i in issues)


def test_fallback_runs_without_api_key(monkeypatch):
    """With no key the public API must still return a non-empty, grounded write-up."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    recs = _sample_recommendations()
    user_prefs = {
        "favorite_genre": "jazz", "favorite_mood": "relaxed",
        "target_energy": 0.35, "likes_acoustic": True,
    }
    text, used_ai = rag.explain_recommendations("Late-Night Jazz", user_prefs, recs)

    assert used_ai is False
    assert text.strip()
    # Grounded: every retrieved title appears in the fallback text.
    for song, _, _ in recs:
        assert song["title"] in text


def test_empty_recommendations_handled():
    text, used_ai = rag.explain_recommendations("Empty", {}, [])
    assert used_ai is False
    assert "No songs" in text