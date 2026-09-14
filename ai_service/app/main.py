import logging

from fastapi import FastAPI

from app.categorize import _get_classifier, categorize, summarize
from app.dedupe import _get_embedder, find_duplicate
from app.schemas import TriageRequest, TriageResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_triage.main")

app = FastAPI(title="Confluence AI Triage Service")


@app.on_event("startup")
def warm_models():
    logger.info("Warming models — this may take a minute on first run...")
    _get_classifier()
    _get_embedder()
    logger.info("Models warm. Ready to serve /triage.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage(payload: TriageRequest):
    category, confidence = categorize(payload.title, payload.description)
    summary = summarize(payload.title, payload.description)

    existing_issues = payload.existing_issues or []

    duplicate_id, _similarity = find_duplicate(
        payload.title, payload.description, payload.district, existing_issues
    )

    return TriageResponse(
        predicted_category=category,
        confidence=round(confidence, 4),
        summary=summary,
        potential_duplicate_id=duplicate_id,
    )