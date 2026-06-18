from typing import TypedDict, List, Dict, NotRequired


class PRState(TypedDict):
    repo_name: str
    pr_number: int
    files: List[str]
    diffs: List[Dict]
    reviews: List[Dict]
    security_reviews: List[Dict]
    summary: str
    quality_score: float
    hallucination_flags: List[Dict]
    error: NotRequired[str]
    injection_detected: NotRequired[bool]
    injection_findings: NotRequired[List[Dict]]
    block_review: NotRequired[bool]
    review_degraded: NotRequired[bool]
    pr_too_large: NotRequired[bool]
