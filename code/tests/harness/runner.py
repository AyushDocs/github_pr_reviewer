"""Harness runner for regression testing the PR reviewer against ground-truth data.

Usage:
    python -m tests.harness.runner                          # run all
    python -m tests.harness.runner sql_injection            # run one
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.chains.review_chain import review_chain
from agent.chains.security_chain import security_chain
from tests.harness.test_cases import TEST_CASES, get_test_case


def _parse_review(raw):
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None


def run_test_case(tc):
    diffs_data = tc["diffs"]
    expected = tc["expected"]

    reviews = []
    security_reviews = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for diff in diffs_data:
            futures[
                executor.submit(review_chain, diff["patch"], diffs_data)
            ] = ("review", diff["filename"])
            futures[
                executor.submit(security_chain, diff["patch"], diffs_data)
            ] = ("security", diff["filename"])

        for future in as_completed(futures):
            chain_type, filename = futures[future]
            try:
                result = future.result()
                content = result.content if hasattr(result, "content") else str(result)
            except Exception as e:
                content = None

            entry = {"file": filename, "review": content, "type": chain_type}
            if chain_type == "review":
                reviews.append(entry)
            else:
                security_reviews.append(entry)

    findings = []
    for r in reviews:
        p = _parse_review(r["review"])
        if p:
            findings.append({"file": r["file"], "severity": p.get("severity", ""), "issue": p.get("issue", ""), "type": r["type"]})
    for r in security_reviews:
        p = _parse_review(r["review"])
        if p:
            findings.append({"file": r["file"], "severity": p.get("severity", ""), "issue": p.get("issue", ""), "type": r["type"]})

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    matched_expected = set()
    for f in findings:
        matched = False
        for i, exp in enumerate(expected):
            if i in matched_expected:
                continue
            if (
                f["file"] == exp["file"]
                and exp["issue_contains"].lower() in (f.get("issue") or "").lower()
                and f["type"] == exp["type"]
            ):
                matched_expected.add(i)
                true_positives += 1
                matched = True
                break
        if not matched:
            false_positives += 1

    false_negatives = len(expected) - len(matched_expected)

    if true_positives + false_positives == 0:
        precision = 1.0
    else:
        precision = true_positives / (true_positives + false_positives)

    if true_positives + false_negatives == 0:
        recall = 1.0
    else:
        recall = true_positives / (true_positives + false_negatives)

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "name": tc["name"],
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "findings": findings,
        "expected_count": len(expected),
    }


def main():
    names = sys.argv[1:] if len(sys.argv) > 1 else [tc["name"] for tc in TEST_CASES]

    for name in names:
        tc = get_test_case(name)
        if not tc:
            print(f"Unknown test case: {name}")
            continue
        print(f"\n{'=' * 60}")
        print(f"Test case: {tc['name']}")
        print(f"{'=' * 60}")
        result = run_test_case(tc)
        print(f"  Findings: {len(result['findings'])} (expected {result['expected_count']})")
        for f in result["findings"]:
            print(f"    [{f['type']}] {f['file']}: {f.get('severity', '?')} - {f.get('issue', '?')}")
        print(f"  TP={result['true_positives']} FP={result['false_positives']} FN={result['false_negatives']}")
        print(f"  Precision={result['precision']} Recall={result['recall']} F1={result['f1']}")


if __name__ == "__main__":
    main()
