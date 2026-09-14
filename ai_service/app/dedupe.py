"""
Deduplication via sentence-embedding cosine similarity.

Flags likely duplicates for moderator review — never auto-merges (per
01-architecture-overview.md: "does not auto-merge"). We only compare against
issues in the same district, since two identical descriptions in different
districts are two real, separate problems.
"""
from functools import lru_cache
from typing import List, Optional, Tuple

from sentence_transformers import SentenceTransformer, util

from app.config import DUPLICATE_SIMILARITY_THRESHOLD, EMBEDDING_MODEL
from app.schemas import ExistingIssue


@lru_cache(maxsize=1)
def _get_embedder():
    return SentenceTransformer(EMBEDDING_MODEL)


def find_duplicate(
    title: str,
    description: str,
    district: Optional[str],
    existing_issues: List[ExistingIssue],
) -> Tuple[Optional[int], float]:
    candidates = [
        issue for issue in existing_issues
        if district is None or issue.district is None or issue.district == district
    ]
    if not candidates:
        return None, 0.0

    embedder = _get_embedder()
    query_text = f"{title}. {description}"
    candidate_texts = [f"{c.title}. {c.description}" for c in candidates]

    all_vecs = embedder.encode(
        [query_text] + candidate_texts, convert_to_tensor=True, show_progress_bar=False
    )
    query_vec, candidate_vecs = all_vecs[0], all_vecs[1:]

    scores = util.cos_sim(query_vec, candidate_vecs)[0]
    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])

    if best_score >= DUPLICATE_SIMILARITY_THRESHOLD:
        return candidates[best_idx].id, best_score

    return None, best_score