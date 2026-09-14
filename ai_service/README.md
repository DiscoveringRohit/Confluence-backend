# Confluence AI Triage Service

FastAPI sidecar for issue categorization + dedup, per `01-architecture-overview.md`
and `04-backend-stack.md`. Runs independently of the Django backend so it can
never block issue creation.

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

First request will be slow (~10-30s) — that's the zero-shot and embedding
models downloading/loading, not a bug. Subsequent requests are fast.

## Endpoint

`POST /triage`

```json
{
  "title": "Broken solar micro-grid inverter in Bundu",
  "description": "The community solar unit has broken inverter capacitors causing blackouts.",
  "district": "Ranchi",
  "existing_issues": [
    {"id": 12, "title": "...", "description": "...", "district": "Ranchi"}
  ]
}
```

Response:

```json
{
  "predicted_category": "energy",
  "confidence": 0.87,
  "summary": "The community solar unit has broken inverter capacitors causing blackouts",
  "potential_duplicate_id": null
}
```

## Payload contract (confirmed from apps/issues/views.py)

Django's `run_ai_triage()` always sends `existing_issues` — up to 50 other
issues from the whole DB (not pre-filtered by district; this service does
that filtering itself in `dedupe.py`), excluding the issue being triaged.
No auth token is needed — it's a plain unauthenticated POST from Django to
`AI_SERVICE_URL` (default `http://127.0.0.1:8001`). If this service is
down or times out (Django's `requests.post(..., timeout=3)`), Django falls
back to its own keyword heuristic — this service crashing does not break
issue submission.

## Config (env vars, see `app/config.py`)

| Var | Default | Purpose |
|---|---|---|
| `ZERO_SHOT_MODEL` | `facebook/bart-large-mnli` | Categorization model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Dedup embedding model |
| `LOW_CONFIDENCE_THRESHOLD` | `0.35` | Below this, category downgrades to `"other"` |
| `DUPLICATE_SIMILARITY_THRESHOLD` | `0.82` | Cosine similarity to flag a duplicate |

## Design choices (and why)

- **Zero-shot NLI, not an LLM API call** — the category set is fixed and
  small (11 values from `BACKEND_API.md` §4.4), which is what NLI zero-shot
  classifiers are built for. No API key, no per-request cost, no network
  dependency, rides the same HF/torch stack as the dedup embeddings.
- **`"other"` as a real fallback category**, not just a UI label — if the
  top zero-shot score is below `LOW_CONFIDENCE_THRESHOLD`, we return
  `"other"` rather than force a low-confidence guess into a field the
  backend treats as authoritative.
- **Never auto-merges duplicates** — only returns `potential_duplicate_id`
  for a moderator to review, per `01-architecture-overview.md`.
- **District-scoped dedup** — two identical descriptions in different
  districts are two real, separate problems, not a duplicate.
- **Model load is lazy + cached (`lru_cache`)**, not at import time — so
  `/health` responds instantly and doesn't force a model download on every
  container restart during dev.

## Not yet done (next steps)

- No test suite yet — worth adding `test_categorize.py` (a handful of
  known-category examples) and `test_dedupe.py` (paraphrase pairs that
  should/shouldn't trip the duplicate threshold) before the demo.
- No `/triage` timeout guard on the Django side is this service's concern,
  but this service itself has no request-level timeout on the outbound
  `httpx.get` fallback other than the 3s in `backend_client.py` — tune if
  district issue lists get large.
- Confidence threshold and similarity threshold are unvalidated guesses —
  tune against a sample of real issue text before demo day, not launch day.
