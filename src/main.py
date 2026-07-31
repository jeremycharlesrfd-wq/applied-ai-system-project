"""
Command line runner for the Music Recommender Simulation.

Pipeline:
1. load_songs() reads the catalog.
2. recommend_songs() scores it and RETRIEVES the top-k songs (the retriever).
3. rag.explain_recommendations() feeds those retrieved rows to Claude, which
   GENERATES a grounded natural-language write-up (Retrieval-Augmented Generation).
   Without an API key it degrades gracefully to a deterministic template.

The scoring logic lives in recommender.py (load_songs, score_song, recommend_songs).
"""

import logging
import os
import textwrap
from typing import List, Tuple

try:
    # Load ANTHROPIC_API_KEY (and optional overrides) from a local .env if present.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it.
    pass

from src.rag import explain_recommendations
from src.recommender import load_songs, recommend_songs


def _configure_logging() -> None:
    """Log to both the console and logs/recommender.log for an auditable run trail."""
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join("logs", "recommender.log")),
        ],
    )


# Four distinct taste profiles for the four scored rules (see README, "The
# Algorithm Recipe"). Each dict is a listener persona; swap which one is passed
# to recommend_songs() in main() to model a different taste. Keys:
#   favorite_genre  categorical match        (x 3.0)
#   favorite_mood   categorical match        (x 1.5)
#   target_energy   0.0 (calm) -> 1.0 (high) (x 1.0)
#   likes_acoustic  prefer acoustic texture  (x 1.0)
USER_PROFILES = {
    "High-Energy Pop": {
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.90,
        "likes_acoustic": False,
    },
    "Chill Lofi": {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.40,
        "likes_acoustic": True,
    },
    "Deep Intense Rock": {
        "favorite_genre": "rock",
        "favorite_mood": "intense",
        "target_energy": 0.92,
        "likes_acoustic": False,
    },
    "Late-Night Jazz": {
        "favorite_genre": "jazz",
        "favorite_mood": "relaxed",
        "target_energy": 0.35,
        "likes_acoustic": True,
    },
}


# Column layout for the recommendations table. Each entry is (header, width);
# the Reasons column is wide because it holds several comma-joined reasons that
# are wrapped onto multiple lines within the cell.
_COLUMNS = [
    ("#", 2),
    ("Title", 24),
    ("Artist", 18),
    ("Score", 6),
    ("Reasons", 34),
]


def _render_row(cells: List[List[str]]) -> str:
    """
    Render one table row that may span several visual lines.

    cells is one list of already-wrapped lines per column. Columns with fewer
    lines are padded with blanks so every column shares the tallest cell's
    height, and each visual line is framed with "|" separators.
    """
    height = max(len(lines) for lines in cells)
    out = []
    for line_i in range(height):
        parts = []
        for (_, width), lines in zip(_COLUMNS, cells):
            text = lines[line_i] if line_i < len(lines) else ""
            parts.append(f" {text:<{width}} ")
        out.append("|" + "|".join(parts) + "|")
    return "\n".join(out)


def _separator() -> str:
    """A "+----+----+" rule sized to the column widths."""
    return "+" + "+".join("-" * (width + 2) for _, width in _COLUMNS) + "+"


def _format_table(recommendations: List[Tuple[dict, float, str]]) -> str:
    """
    Build a fixed-width ASCII table of the recommendations.

    Long titles/artists are truncated with an ellipsis to keep the columns
    aligned; the comma-joined explanation is split back into individual reasons
    and word-wrapped inside the Reasons column so nothing runs off the edge.
    """
    _, title_w, artist_w, _, reasons_w = (w for _, w in _COLUMNS)

    def _clip(text: str, width: int) -> str:
        return text if len(text) <= width else text[: width - 1] + "…"

    lines = [_separator()]
    lines.append(_render_row([[h] for h, _ in _COLUMNS]))
    lines.append(_separator())

    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        # Each reason becomes its own wrapped block so a single reason never
        # gets split across two mid-word lines.
        reason_lines: List[str] = []
        for reason in explanation.split(", "):
            reason_lines.extend(textwrap.wrap(reason, reasons_w) or [""])

        cells = [
            [str(rank)],
            [_clip(song["title"], title_w)],
            [_clip(song["artist"], artist_w)],
            [f"{score:.2f}"],
            reason_lines,
        ]
        lines.append(_render_row(cells))
        lines.append(_separator())

    return "\n".join(lines)


def main() -> None:
    _configure_logging()
    songs = load_songs("data/songs.csv")

    # Pick which persona to model by name; try the others from USER_PROFILES.
    profile_name = "Late-Night Jazz"
    user_prefs = USER_PROFILES[profile_name]

    # Step 1-2: score the catalog and RETRIEVE the top-k songs.
    recommendations = recommend_songs(user_prefs, songs, k=5)

    # Step 3: GENERATE a grounded explanation from the retrieved rows (RAG).
    explanation, used_ai = explain_recommendations(
        profile_name, user_prefs, recommendations
    )

    header = f"Top recommendations for: {profile_name}"
    print(f"\n{header}")
    print("=" * len(header))

    source = "Claude (grounded in retrieved songs)" if used_ai \
        else "offline fallback — no API key; set ANTHROPIC_API_KEY for AI output"
    print(f"Explanation source: {source}\n")
    print(explanation)

    # The scoring table remains as the transparent, auditable detail behind the picks.
    print("\nScoring detail")
    print("--------------")
    print(_format_table(recommendations))


if __name__ == "__main__":
    main()
