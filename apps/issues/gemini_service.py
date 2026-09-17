"""
Gemini AI Triage and Verification Engine
Configured with Gemini API keys in reversed order with automatic fallback rotation.
"""

import base64
import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

# Loaded from environment variables (gitignored .env) in reversed order:
# 1. Primary: Reversed Key 3
# 2. Backup 1: Reversed Key 2
# 3. Backup 2: Reversed Key 1
# 4. Backup 3: Reversed Primary
ENV_KEYS = [
    k for k in [
        os.getenv("GEMINI_PRIMARY_KEY"),
        os.getenv("GEMINI_BACKUP_KEY_1"),
        os.getenv("GEMINI_BACKUP_KEY_2"),
        os.getenv("GEMINI_BACKUP_KEY_3"),
    ] if k
]

FALLBACK_KEYS = []

GEMINI_API_KEYS = ENV_KEYS if ENV_KEYS else FALLBACK_KEYS

GEMINI_MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """
You are an expert civic infrastructure AI triage engineer for the Confluence civic platform.
Analyze this civic issue report. If an image is provided, examine it carefully.
Categorize the issue into strictly one of:
- "water"
- "urban_infra"
- "education"
- "healthcare"
- "agriculture"
- "environment"
- "energy"
- "rural_livelihoods"

Return valid JSON with:
{
  "is_civic_issue": true or false,
  "confidence_score": 0.60 to 0.99,
  "category": "one of the 8 valid categories",
  "title": "Concise, professional title",
  "description": "Thorough description of the hazard",
  "expected_outcome": "Corrective resolution required",
  "severity": "low" | "medium" | "high" | "critical",
  "detected_objects": ["list", "of", "elements"],
  "verification_status": "verified" | "flagged_non_civic",
  "verification_notes": "Summary of verification"
}
"""


def call_gemini_triage(title, description, district="", photo_path=None, photo_url=None):
    """
    Invokes Gemini 3.6 Flash using key rotation across 4 API keys.
    Returns parsed dict or None if all fail.
    """
    parts = [{"text": SYSTEM_PROMPT}]

    user_text = f"Title: {title}\nDescription: {description}\nDistrict: {district or 'Statewide'}\n"
    if photo_url:
        user_text += f"Photo URL: {photo_url}\n"
    parts.append({"text": user_text})

    # If local photo exists, embed base64 inline data
    if photo_path and os.path.exists(photo_path):
        try:
            with open(photo_path, "rb") as f:
                photo_bytes = f.read()
            b64_data = base64.b64encode(photo_bytes).decode("utf-8")
            ext = os.path.splitext(photo_path)[1].lower()
            mime_type = "image/jpeg"
            if ext == ".png":
                mime_type = "image/png"
            elif ext == ".webp":
                mime_type = "image/webp"

            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data,
                }
            })
        except Exception as e:
            logger.warning("Could not read local photo for Gemini inline_data: %s", e)

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    for idx, key in enumerate(GEMINI_API_KEYS):
        key_label = "Primary" if idx == 0 else f"Backup {idx}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        try:
            res = requests.post(url, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)
                parsed["key_used"] = key_label
                return parsed
            else:
                logger.warning("Gemini key %s failed with HTTP %s: %s", key_label, res.status_code, res.text[:120])
        except Exception as e:
            logger.warning("Gemini key %s request error: %s", key_label, e)

    return None
