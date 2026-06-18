import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from agent.graph import app_auto
from agent.tools.github_tool import gh
from notify import send_email_notification


def _check_langsmith():
    if not os.getenv("LANGSMITH_API_KEY"):
        print("FATAL: LANGSMITH_API_KEY is required for CI review tracing.")
        sys.exit(1)


def get_pr_info():
    return os.getenv("GITHUB_REPOSITORY", "AyushDocs/pr-review-agent-lab"), int(
        os.getenv("PR_NUMBER", "1")
    )


def get_recipients(repo_name, pr_number):
    recipients = []
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        author = pr.user
        if author.email:
            recipients.append(author.email)
        for reviewer in pr.get_review_requests()[0]:
            if reviewer.email:
                recipients.append(reviewer.email)
    except Exception as e:
        print(f"Could not fetch email recipients: {e}")
    return list(set(recipients))


def _cache_key(repo_name, pr_number):
    raw = f"{repo_name}#{pr_number}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _load_cached_result(cache_dir):
    if not cache_dir:
        return None
    cache_file = os.path.join(cache_dir, "result.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_cached_result(cache_dir, result):
    if not cache_dir:
        return
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "result.json")
    serializable = {
        "summary": result.get("summary", ""),
        "reviews": result.get("reviews", []),
        "security_reviews": result.get("security_reviews", []),
        "quality_score": result.get("quality_score", 0),
        "hallucination_flags": result.get("hallucination_flags", []),
        "block_review": result.get("block_review", False),
        "review_degraded": result.get("review_degraded", False),
        "injection_detected": result.get("injection_detected", False),
    }
    with open(cache_file, "w") as f:
        json.dump(serializable, f, default=str)


def _build_summary_report(repo_name, pr_number, result, duration_s):
    reviews = result.get("reviews", [])
    security_reviews = result.get("security_reviews", [])
    quality_score = result.get("quality_score", 0)
    hallucination_flags = result.get("hallucination_flags", [])
    review_degraded = result.get("review_degraded", False)
    injection_detected = result.get("injection_detected", False)
    pr_too_large = result.get("pr_too_large", False)

    lines = ["## PR Review Report", ""]
    lines.append(f"- **Repository**: {repo_name}#{pr_number}")
    lines.append(f"- **Duration**: {duration_s}s")
    if pr_too_large:
        lines.append("- **PR Size**: Skipped — PR too large")
        lines.append("")
        lines.append(result.get("summary", ""))
        return "\n".join(lines)

    lines.append(f"- **Code findings**: {len(reviews)}")
    lines.append(f"- **Security findings**: {len(security_reviews)}")
    lines.append(f"- **Quality score**: {quality_score}")
    lines.append(f"- **Hallucination flags**: {len(hallucination_flags)}")
    lines.append(f"- **Degraded**: {'Yes' if review_degraded else 'No'}")
    lines.append(f"- **Injection detected**: {'Yes' if injection_detected else 'No'}")

    if review_degraded:
        lines.append("")
        lines.append("> ⚠️ Review was degraded — some LLM calls failed.")
    if injection_detected:
        lines.append("")
        lines.append("> ⚠️ Prompt injection detected in PR description or title.")
    if hallucination_flags:
        lines.append("")
        lines.append("> ⚠️ Potential hallucination flags raised during review.")

    return "\n".join(lines)


def _post_comment_with_email_note(repo_name, pr_number, summary, email_sent):
    if email_sent is not False:
        return
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        note = (
            f"\n\n---\n_Note: Email notification failed."
            f" SMTP configuration may be incorrect._"
        )
        pr.create_issue_comment(summary + note)
    except Exception as e:
        print(f"Could not post email failure note: {e}")


def main():
    _check_langsmith()

    repo_name, pr_number = get_pr_info()
    cache_dir = os.getenv("REVIEW_CACHE_DIR")

    start = time.time()
    cached = _load_cached_result(cache_dir)
    if cached:
        print(f"Loading cached review for PR #{pr_number} in {repo_name}...")
        result = cached
    else:
        print(f"Reviewing PR #{pr_number} in {repo_name}...")
        result = app_auto.invoke({"repo_name": repo_name, "pr_number": pr_number})
        _save_cached_result(cache_dir, result)
    duration = time.time() - start

    summary = result.get("summary", "")
    reviews = result.get("reviews", [])
    security_reviews = result.get("security_reviews", [])

    print("\n=== REVIEW COMPLETE ===")
    print(summary)

    # GITHUB_STEP_SUMMARY report
    report = _build_summary_report(repo_name, pr_number, result, round(duration, 1))
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "w") as f:
            f.write(report)
        print(f"Wrote job summary to {step_summary}")
    else:
        print(report)

    # Email notification
    recipients = get_recipients(repo_name, pr_number)
    email_sent = None
    if recipients:
        email_sent = send_email_notification(
            repo_name=repo_name,
            pr_number=pr_number,
            recipients=recipients,
            summary=summary,
            findings_count=len(reviews) + len(security_reviews),
        )

    # Fallback: email failure → PR comment note
    if email_sent is False:
        _post_comment_with_email_note(repo_name, pr_number, summary, email_sent)

    print("Done.")


if __name__ == "__main__":
    main()
