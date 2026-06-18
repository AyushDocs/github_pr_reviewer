import json
from pydantic import BaseModel, Field, ValidationError


class ReviewFinding(BaseModel):
    severity: str = Field(..., pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    issue: str = Field(..., min_length=5)
    explanation: str = Field(..., min_length=10)
    suggested_fix: str = Field(..., min_length=10)


def _extract_json(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json")
    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```")
    cleaned = cleaned.strip()
    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start : brace_end + 1]
    return cleaned


def parse_review_output(raw) -> ReviewFinding | None:
    if hasattr(raw, "content"):
        raw = raw.content
    if not raw or not isinstance(raw, str):
        return None
    try:
        data = json.loads(_extract_json(raw))
        return ReviewFinding(**data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None
