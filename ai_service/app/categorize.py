"""
Zero-shot categorization against the fixed Confluence category enum.

Why zero-shot NLI instead of an LLM call: the label set is small and fixed
(11 values), which is exactly what NLI-based zero-shot classifiers are built
for — no training data needed, no API key, no network dependency at request
time, and it rides the same HF/torch stack the dedup module already needs.
See the design discussion for the accuracy trade-off vs LLM prompting.
"""
from functools import lru_cache

from transformers import pipeline

from app.config import CATEGORIES, CATEGORY_DESCRIPTIONS, LOW_CONFIDENCE_THRESHOLD, ZERO_SHOT_MODEL

# Labels actually passed to the model — natural-language hypotheses score
# better than raw enum tokens. "other" is deliberately excluded from the
# candidate list: it's not a real topic, it's our fallback when nothing
# scores above the confidence threshold.
_SCORABLE_CATEGORIES = [c for c in CATEGORIES if c != "other"]
_CANDIDATE_LABELS = [CATEGORY_DESCRIPTIONS[c] for c in _SCORABLE_CATEGORIES]
_LABEL_TO_CATEGORY = dict(zip(_CANDIDATE_LABELS, _SCORABLE_CATEGORIES))


@lru_cache(maxsize=1)
def _get_classifier():
    # Loaded once per process, not per request — this is the expensive part.
    return pipeline("zero-shot-classification", model=ZERO_SHOT_MODEL)


def categorize(title: str, description: str) -> tuple[str, float]:
    """Returns (predicted_category, confidence) using the real DB enum values."""
    text = f"{title}. {description}".strip()
    classifier = _get_classifier()
    result = classifier(text, candidate_labels=_CANDIDATE_LABELS, multi_label=False)

    top_label = result["labels"][0]
    top_score = float(result["scores"][0])
    category = _LABEL_TO_CATEGORY[top_label]

    if top_score < LOW_CONFIDENCE_THRESHOLD:
        return "other", top_score

    return category, top_score


def summarize(title: str, description: str) -> str:
    """Cheap extractive summary — first sentence of description, capped.
    Swap for a real summarization model later if judges care; not worth the
    latency/complexity for a hackathon demo where the moderator reads the
    full description anyway."""
    first_sentence = description.strip().split(". ")[0].strip()
    if len(first_sentence) > 160:
        first_sentence = first_sentence[:157].rstrip() + "..."
    return first_sentence or title
