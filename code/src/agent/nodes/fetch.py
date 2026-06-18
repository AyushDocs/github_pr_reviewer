from github import GithubException

from agent.tools.github_tool import get_pr_files
from agent.utils.logger import get_logger

log = get_logger(__name__)


def fetch_node(state):
    repo = state["repo_name"]
    pr = state["pr_number"]
    log.info("Fetching PR %s #%s", repo, pr)

    try:
        pr_data = get_pr_files(repo, pr)
    except GithubException as e:
        log.error("GitHub API error for %s #%s: %s", repo, pr, e)
        return {"files": [], "diffs": [], "error": str(e)}

    log.info("Fetched %s files", len(pr_data["files"]))
    return {"files": pr_data["files"], "diffs": pr_data["diffs"]}
