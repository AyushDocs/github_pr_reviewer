from agent.tools.github_tool import post_pr_comment
from agent.utils.logger import get_logger

log = get_logger(__name__)


def flag_injection_node(state):
    repo = state["repo_name"]
    pr = state["pr_number"]
    findings = state.get("injection_findings", [])

    log.warning("Flagging injection on %s #%s (%s findings)", repo, pr, len(findings))

    body = (
        "**Review blocked: Potential prompt injection detected**\n\n"
        "The AI review was skipped because the PR diff contains patterns "
        "that may attempt to manipulate the code review system.\n\n"
        f"{len(findings)} suspicious pattern(s) found.\n\n"
        "*This PR requires manual review.*"
    )

    try:
        post_pr_comment(repo, pr, body)
        log.info("Injection warning posted")
    except Exception as e:
        log.error("Failed to post injection warning: %s", e)

    return {}


def flag_blocked_node(state):
    repo = state["repo_name"]
    pr = state["pr_number"]

    log.warning("Skipping review for %s #%s (blocked by validity gate)", repo, pr)

    body = (
        "**Review skipped**\n\n"
        "The AI review was not posted because the generated review did not pass "
        "quality and hallucination checks.\n\n"
        "*This PR requires manual review.*"
    )

    try:
        post_pr_comment(repo, pr, body)
        log.info("Blocked notice posted")
    except Exception as e:
        log.error("Failed to post blocked notice: %s", e)

    return {}
