import os

# Exact enum from Confluence-backend Issue.category (BACKEND_API.md §4.4)
# "other" is a real DB value — used when zero-shot confidence is too low to trust.
CATEGORIES = [
    "education",
    "healthcare",
    "agriculture",
    "water",
    "environment",
    "energy",
    "urban_infra",
    "accessibility",
    "public_admin",
    "rural_livelihoods",
    "other",
]

# Human-readable hypothesis templates per label — zero-shot NLI models score
# much better with a natural-language template than with the raw enum token
# (e.g. "public_admin" alone is a poor NLI hypothesis; "This issue is about
# public administration or governance." is much clearer to the model).
CATEGORY_DESCRIPTIONS = {
    "education": "education, schools, teachers, or colleges",
    "healthcare": "healthcare, hospitals, doctors, or medicine",
    "agriculture": "agriculture, farming, crops, or irrigation",
    "water": "water supply, pipes, drainage, or borewells",
    "environment": "environment, pollution, forests, or mining",
    "energy": "energy, electricity, solar power, or the power grid",
    "urban_infra": "urban infrastructure, roads, bridges, or potholes",
    "accessibility": "accessibility for persons with disabilities",
    "public_admin": "public administration or government services",
    "rural_livelihoods": "rural livelihoods or village-level economic activity",
}

# Below this confidence, downgrade the prediction to "other" rather than
# ship a low-confidence guess into a field the backend treats as authoritative.
LOW_CONFIDENCE_THRESHOLD = float(os.environ.get("LOW_CONFIDENCE_THRESHOLD", 0.35))

# Above this cosine similarity, flag as a potential duplicate.
DUPLICATE_SIMILARITY_THRESHOLD = float(os.environ.get("DUPLICATE_SIMILARITY_THRESHOLD", 0.82))

# Used only when the request doesn't include existing_issues[] — see README
# for why the payload contract is ambiguous between BACKEND_API.md and Flow.md.
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://127.0.0.1:8000")
BACKEND_SERVICE_TOKEN = os.environ.get("BACKEND_SERVICE_TOKEN", "")

ZERO_SHOT_MODEL = os.environ.get("ZERO_SHOT_MODEL", "facebook/bart-large-mnli")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
