from github import Github, Auth
from agent.config import GITHUB_TOKEN

gh = Github(auth=Auth.Token(GITHUB_TOKEN))


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


def get_latest_commit(repo_name: str, pr_number: int):
    pr = get_pr(repo_name, pr_number)
    return list(pr.get_commits())[-1]


def post_review_comments(repo_name: str, pr_number: int, file_comments: list):
    pr = get_pr(repo_name, pr_number)
    commit = get_latest_commit(repo_name, pr_number)
    comments = [
        {
            "body": fc["body"],
            "path": fc["path"],
            "subject_type": "file",
        }
        for fc in file_comments
    ]
    pr.create_review(
        commit=commit,
        comments=comments,
        event="COMMENT",
    )
