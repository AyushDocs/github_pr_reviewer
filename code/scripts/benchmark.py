"""Benchmark the PR review pipeline.

Usage:
    python scripts/benchmark.py AyushDocs/pr-review-agent-lab 3
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.graph import app_auto


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/benchmark.py <owner/repo> <pr_number>")
        sys.exit(1)

    repo_name = sys.argv[1]
    pr_number = int(sys.argv[2])

    total_start = time.time()

    result = app_auto.invoke(
        {"repo_name": repo_name, "pr_number": pr_number},
        {"configurable": {"thread_id": f"bench-{pr_number}"}},
    )

    total_time = time.time() - total_start

    reviews = result.get("reviews", [])
    security = result.get("security_reviews", [])
    summary = result.get("summary", "")
    quality = result.get("quality_score", "N/A")

    print("\n=== BENCHMARK RESULTS ===\n")
    print(f"Repository:     {repo_name}")
    print(f"PR Number:      #{pr_number}")
    print(f"Total time:     {total_time:.2f}s")
    print(f"Files changed:  {len(result.get('files', []))}")
    print(f"Code reviews:   {len(reviews)}")
    print(f"Security revs:  {len(security)}")
    print(f"Quality score:  {quality}")
    print(f"Summary length: {len(summary)} chars")
    print(f"Avg time/file:  {total_time / max(len(reviews), 1):.2f}s")


if __name__ == "__main__":
    main()
