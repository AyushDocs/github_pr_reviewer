import os
from agent.utils.logger import get_logger

log = get_logger(__name__)

_MAX_FILES = int(os.getenv("PR_MAX_FILES", "50"))
_MAX_PATCH_SIZE = int(os.getenv("PR_MAX_PATCH_SIZE", "500000"))


def pr_size_gate_node(state):
    diffs = state.get("diffs", [])
    total_patch_size = sum(len(d.get("patch", "")) for d in diffs)

    too_many = len(diffs) > _MAX_FILES
    too_big = total_patch_size > _MAX_PATCH_SIZE

    if too_many or too_big:
        log.warning(
            "PR too large: %s files (limit %s), %s bytes (limit %s)",
            len(diffs), _MAX_FILES, total_patch_size, _MAX_PATCH_SIZE,
        )
        reasons = []
        if too_many:
            reasons.append(f"- Files changed: {len(diffs)} (limit: {_MAX_FILES})")
        if too_big:
            reasons.append(f"- Diff size: {total_patch_size:,} bytes (limit: {_MAX_PATCH_SIZE:,})")
        body = (
            "**Review skipped: PR too large**\n\n"
            + "\n".join(reasons)
            + "\n\n*Break this PR into smaller changes for AI review.*"
        )
        return {"pr_too_large": True, "summary": body}

    log.info("PR size OK: %s files, %s bytes", len(diffs), total_patch_size)
    return {"pr_too_large": False}
