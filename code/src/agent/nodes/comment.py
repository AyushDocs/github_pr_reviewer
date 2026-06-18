import json

from agent.tools.github_tool import post_pr_comment, post_review_comments
from agent.utils.logger import get_logger

log = get_logger(__name__)


def _parse_review(raw_review):
    try:
        cleaned = raw_review.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None


def _build_file_comment(filename, reviews, security_reviews):
    lines = [f"## Review: {filename}\n"]
    for r in reviews:
        p = _parse_review(r["review"])
        if p:
            lines.append(f"**{p.get('severity', '?').upper()}** — {p.get('issue', '?')}")
            lines.append(f"> {p.get('explanation', '')}")
            lines.append(f"_{p.get('suggested_fix', '')}_\n")
    for r in security_reviews:
        p = _parse_review(r["review"])
        if p:
            lines.append(f"**{p.get('severity', '?').upper()}** (security) — {p.get('issue', '?')}")
            lines.append(f"> {p.get('explanation', '')}")
            lines.append(f"_{p.get('suggested_fix', '')}_\n")
    return "\n".join(lines)


def comment_node(state):
    repo = state["repo_name"]
    pr = state["pr_number"]
    summary = state.get("summary", "")

    if not summary:
        log.warning("No summary to post for %s #%s", repo, pr)
        return {}

    if state.get("review_degraded"):
        log.warning("Skipping inline comments for degraded review on %s #%s", repo, pr)
        log.info("Posting degraded summary to %s #%s", repo, pr)
        try:
            post_pr_comment(repo, pr, summary)
        except Exception as e:
            log.error("Failed to post degraded summary: %s", e)
        return {}

    log.info("Posting summary comment to %s #%s", repo, pr)
    try:
        post_pr_comment(repo, pr, summary)
        log.info("Summary comment posted")
    except Exception as e:
        log.error("Failed to post summary comment: %s", e)

    file_comments = []
    filenames = set()
    for r in state.get("reviews", []):
        filenames.add(r["file"])
    for r in state.get("security_reviews", []):
        filenames.add(r["file"])

    for filename in filenames:
        file_reviews = [r for r in state.get("reviews", []) if r["file"] == filename]
        file_security = [r for r in state.get("security_reviews", []) if r["file"] == filename]
        body = _build_file_comment(filename, file_reviews, file_security)
        file_comments.append({"path": filename, "body": body})

    if file_comments:
        log.info("Posting %s inline review comments", len(file_comments))
        try:
            post_review_comments(repo, pr, file_comments)
            log.info("Inline comments posted")
        except Exception as e:
            log.error("Failed to post inline comments (summary was posted): %s", e)

    return {}

