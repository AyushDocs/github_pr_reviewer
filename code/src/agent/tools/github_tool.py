import os
from github import Github,Auth


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
auth=Auth.Token(GITHUB_TOKEN)

if not GITHUB_TOKEN:
    raise ValueError("Github token is needed")

gh = Github(auth=auth)


def get_repo(repo_name: str):
    return gh.get_repo(repo_name)


def get_pr(repo_name: str, pr_number: int):
    repo = get_repo(repo_name)
    return repo.get_pull(pr_number)


def get_pr_files(repo_name: str, pr_number: int):
    pr = get_pr(repo_name, pr_number)

    files = []
    diffs = []

    for file in pr.get_files():
        files.append(file.filename)

        if file.patch:
            diffs.append(
                {"filename": file.filename, "patch": file.patch, "status": file.status}
            )

    return {"files": files, "diffs": diffs}


def post_pr_comment(repo_name: str, pr_number: int, comment: str):
    pr = get_pr(repo_name, pr_number)
    pr.create_issue_comment(comment)


if __name__ == "__main__":
    repo = get_repo("AyushDocs/pr-review-agent-lab")
    print(repo)
