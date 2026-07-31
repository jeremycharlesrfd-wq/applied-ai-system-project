# Music Recommender Simulation — System Diagram

A retrieval-augmented (RAG) music recommender. A deterministic scorer **retrieves**
the top songs, Claude **generates** a grounded explanation of them, a code
**guardrail** verifies the AI stayed grounded, and **pytest + humans** check the
results.

```mermaid
flowchart TD
    %% ---------- Inputs ----------
    subgraph INPUT["📥 Input"]
        CSV[("data/songs.csv<br/>song catalog")]
        PROFILE["User taste profile<br/>(USER_PROFILES persona:<br/>genre, mood, energy, acoustic)"]
    end

    %% ---------- Retrieval / scoring ----------
    subgraph RETRIEVE["⚙️ Retriever — recommender.py (deterministic)"]
        LOAD["load_songs()<br/>parse catalog"]
        SCORE["score_song()<br/>weighted-sum recipe<br/>genre·mood·energy·acoustic"]
        RANK["recommend_songs()<br/>greedy top-k +<br/>diversity penalty"]
    end

    %% ---------- RAG / generation ----------
    subgraph RAG["🤖 Agent — rag.py (RAG generation)"]
        BUILD["_build_user_message()<br/>retrieved rows = only source of truth"]
        CLAUDE["Claude (claude-opus-4-8)<br/>generates grounded write-up"]
        GUARD{"_validate_grounding()<br/>hallucinated / dropped /<br/>empty pick?"}
        RETRY["retry once, then give up"]
        FALLBACK["_fallback_writeup()<br/>deterministic template<br/>(no key / SDK / API error)"]
    end

    %% ---------- Output ----------
    subgraph OUTPUT["📤 Output — main.py"]
        EXPLAIN["Natural-language explanation<br/>(+ source: AI vs offline)"]
        TABLE["ASCII scoring table<br/>(auditable detail)"]
        LOG[("logs/recommender.log<br/>run trail")]
    end

    %% ---------- Verification ----------
    subgraph CHECK["🧪 Testing & Human Review"]
        PYTEST["pytest<br/>test_recommender.py — scoring/ranking<br/>test_rag.py — guardrail + fallback"]
        HUMAN["👤 Human reviewer<br/>reads explanation + table + logs,<br/>judges quality"]
    end

    %% ---------- Data flow ----------
    CSV --> LOAD
    PROFILE --> SCORE
    LOAD --> SCORE --> RANK
    RANK -->|"top-k (song, score, reasons)"| BUILD
    BUILD --> CLAUDE --> GUARD
    GUARD -- pass --> EXPLAIN
    GUARD -- fail --> RETRY --> CLAUDE
    RETRY -.->|exhausted| FALLBACK
    GUARD -. no key / error .-> FALLBACK
    FALLBACK --> EXPLAIN
    RANK --> TABLE

    %% ---------- Logging + verification edges ----------
    RETRIEVE -.log.-> LOG
    RAG -.log.-> LOG
    EXPLAIN --> HUMAN
    TABLE --> HUMAN
    LOG --> HUMAN
    RANK -. verified by .-> PYTEST
    GUARD -. verified by .-> PYTEST

    %% ---------- Styles ----------
    classDef ai fill:#e8dbff,stroke:#7a3ff2,color:#1a1a1a;
    classDef det fill:#dbeeff,stroke:#2b6cb0,color:#1a1a1a;
    classDef check fill:#e6ffe6,stroke:#2f855a,color:#1a1a1a;
    classDef io fill:#fff4d6,stroke:#b7791f,color:#1a1a1a;
    class CLAUDE,BUILD ai;
    class LOAD,SCORE,RANK,FALLBACK,GUARD det;
    class PYTEST,HUMAN check;
    class CSV,PROFILE,EXPLAIN,TABLE,LOG io;
```

## How to read it

| Stage | Component | Role |
|-------|-----------|------|
| **Input** | `data/songs.csv` + a `USER_PROFILES` persona | The catalog and the listener's taste |
| **Retriever** | `recommender.py` (`load_songs`, `score_song`, `recommend_songs`) | Deterministically scores every song and retrieves the diversity-aware top-k |
| **Agent (RAG)** | `rag.py` → Claude | Generates a natural-language explanation grounded **only** in the retrieved rows |
| **Guardrail** | `_validate_grounding()` | Rejects hallucinated, dropped, or empty picks; retries once, else falls back |
| **Fallback** | `_fallback_writeup()` | Deterministic template so the app always runs without an API key |
| **Output** | `main.py` | Prints the explanation, an auditable scoring table, and logs the run |
| **Testing** | `tests/` (pytest) | `test_recommender.py` checks scoring/ranking; `test_rag.py` checks the guardrail + fallback |
| **Human** | Reviewer | Reads the explanation, table, and logs to judge whether the AI output is trustworthy |

### Where AI results get checked
1. **Automated in-code guardrail** — `_validate_grounding()` verifies every Claude
   generation against the retrieved set on each run (with one retry, then fallback).
2. **Automated tests** — pytest exercises the guardrail and fallback offline (no key needed).
3. **Human review** — a person inspects the printed explanation against the
   transparent scoring table and `logs/recommender.log`.