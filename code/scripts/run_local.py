import sys
import json

from langgraph.types import Command
from agent.graph import app


def main(repo_name, pr_number):
    config = {"configurable": {"thread_id": f"pr-{repo_name}-{pr_number}"}}

    result = app.invoke(
        {"repo_name": repo_name, "pr_number": pr_number},
        config,
    )

    if app.get_state(config).next:
        print("\n=== REVIEW GENERATED — AWAITING APPROVAL ===\n")
        print(result.get("summary", ""))

        while True:
            choice = input("\nPost this review to GitHub? (y/n): ").strip().lower()
            if choice == "y":
                result = app.invoke(Command(resume="proceed"), config)
                print("\n=== REVIEW POSTED ===")
                print(result.get("summary", ""))
                break
            elif choice == "n":
                print("Review cancelled.")
                break
    else:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_local.py <owner/repo> <pr_number>")
        sys.exit(1)
    main(sys.argv[1], int(sys.argv[2]))
