"""Create test PRs from branches in the test repo.

Usage:
    python scripts/seed_test_prs.py                         # create all
    python scripts/seed_test_prs.py sql-injection           # create one
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.tools.github_tool import gh

REPO_NAME = "AyushDocs/pr-review-agent-lab"
BRANCH_DESCRIPTIONS = {
    "sql-injection": "add vulnerable auth query",
    "vulnerable-secrets": "Vulnerable secrets",
    "weak-auth": "Weak auth",
}


def create_pr(branch: str, title: str):
    repo = gh.get_repo(REPO_NAME)
    existing = list(repo.get_pulls(state="open", head=f"AyushDocs:{branch}"))
    if existing:
        print(f"PR already exists for '{branch}': #{existing[0].number} - {existing[0].title}")
        return existing[0].number

    pr = repo.create_pull(
        title=title,
        body=f"Automated test PR from branch `{branch}`.",
        head=branch,
        base="main",
    )
    print(f"Created PR #{pr.number}: {pr.title}")
    return pr.number


def main():
    branches = sys.argv[1:] if len(sys.argv) > 1 else list(BRANCH_DESCRIPTIONS.keys())

    for branch in branches:
        title = BRANCH_DESCRIPTIONS.get(branch, branch.replace("-", " ").title())
        create_pr(branch, title)


if __name__ == "__main__":
    main()
