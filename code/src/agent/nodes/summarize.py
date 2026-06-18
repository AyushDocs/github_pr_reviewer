import json

from agent.chains.summary_chain import summary_chain
from agent.utils.logger import get_logger

log = get_logger(__name__)


def _format_reviews(reviews, label):
    text = ""
    for r in reviews:
        try:
            raw = r["review"].strip().removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(raw)
            severity = parsed.get("severity", "?")
            issue = parsed.get("issue", "?")
        except (json.JSONDecodeError, AttributeError):
            severity = "?"
            issue = r["review"][:100]

        text += f"- [{label}] {r['file']} | {severity} | {issue}\n"
    return text


def summarize_node(state):
    degraded = state.get("review_degraded", False)
    reviews_text = ""
    reviews_text += _format_reviews(state.get("reviews", []), "Code")
    reviews_text += _format_reviews(state.get("security_reviews", []), "Security")

    if degraded:
        log.warning("Review degraded — LLM API unavailable")
        return {"summary": "## Review Unavailable\n\nThe AI review could not be completed because the LLM API was unavailable. Please re-run the workflow later or review manually."}

    if not reviews_text.strip():
        log.warning("No reviews to summarize")
        return {"summary": "## Summary\n\nNo issues found in this PR."}

    log.info("Generating summary")
    result = summary_chain.invoke({"reviews": reviews_text})

    log.info("Summary generated: %s chars", len(result.content))
    summary = result.content + "\n\n---\n*Was this review helpful? React with 👍 or 👎 on this comment to give feedback.*"
    return {"summary": summary}
