from agent.config_loader import load_config
from agent.utils.logger import get_logger

log = get_logger(__name__)


def pr_size_gate_node(state):
    repo_name = state.get("repo_name", "")
    config = load_config(repo_name) if repo_name else {}
    max_files = config.get("max_files", 50)
    max_patch_size = config.get("max_patch_size", 500000)

    diffs = state.get("diffs", [])
    total_patch_size = sum(len(d.get("patch", "")) for d in diffs)

    too_many = len(diffs) > max_files
    too_big = total_patch_size > max_patch_size

    if too_many or too_big:
        log.warning(
            "PR too large: %s files (limit %s), %s bytes (limit %s)",
            len(diffs), max_files, total_patch_size, max_patch_size,
        )
        reasons = []
        if too_many:
            reasons.append(f"- Files changed: {len(diffs)} (limit: {max_files})")
        if too_big:
            reasons.append(f"- Diff size: {total_patch_size:,} bytes (limit: {max_patch_size:,})")
        body = (
            "**Review skipped: PR too large**\n\n"
            + "\n".join(reasons)
            + "\n\n*Break this PR into smaller changes for AI review.*"
        )
        return {"pr_too_large": True, "summary": body}

    log.info("PR size OK: %s files, %s bytes", len(diffs), total_patch_size)
    return {"pr_too_large": False}
