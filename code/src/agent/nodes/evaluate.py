from langsmith import traceable
from agent.evaluators.quality import evaluate_quality
from agent.evaluators.hallucination import detect_hallucinations
from agent.utils.logger import get_logger

log = get_logger(__name__)


@traceable(name="evaluate_node", run_type="chain")
def evaluate_node(state):
    reviews = state.get("reviews", [])
    security_reviews = state.get("security_reviews", [])
    diffs = state.get("diffs", [])

    quality = evaluate_quality(reviews, security_reviews)
    flags = detect_hallucinations(reviews, security_reviews, diffs)

    log.info(
        "Quality score: %s, hallucination flags: %s",
        quality["score"],
        len(flags),
    )
    if quality["issues"]:
        for issue in quality["issues"]:
            log.warning("Quality issue: %s", issue)
    if flags:
        for f in flags:
            log.warning("Hallucination: %s in %s", f["issue"], f["file"])

    return {
        "quality_score": quality["score"],
        "hallucination_flags": flags,
    }
