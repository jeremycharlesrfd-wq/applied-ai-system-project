# AI Interactions Log

> The project's **primary AI feature is Retrieval-Augmented Generation (RAG)** — see
> the "AI Feature" section of the README and `src/rag.py`. This log documents the AI
> *coding agent* I used to build it.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

Turn the rule-based recommender into something that "does something useful with AI" by
adding a fully integrated RAG feature, with guardrails, logging, tests, reproducible
setup, and a fallback so it runs without an API key.

**Prompts used:**

- "This project should do something useful with AI… add a RAG / agentic / testing
  feature that meaningfully changes how the system behaves, with logging, guardrails,
  and clear setup steps."
- Follow-up decisions: use **RAG explanations** as the centerpiece, and support the
  **real Claude API with an offline fallback** for reproducible grading.

**What did the agent generate or change?**

- `src/rag.py` — retrieval-context builder, Claude call (structured output), grounding
  guardrail, deterministic offline fallback, logging.
- `src/main.py` — wired the grounded write-up in as the primary output; added logging
  and `.env` loading.
- `tests/test_rag.py` — guardrail + fallback tests.
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `model_card.md`.

**What did you verify or fix manually?**

- Ran `pytest` (8 passing) and `python -m src.main` to confirm the offline fallback
  path works and logs correctly.
- Confirmed the installed Anthropic SDK actually exposes `messages.parse(...)` +
  `output_format` before relying on it, and that the "SDK present but no key" branch
  degrades gracefully instead of erroring.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
