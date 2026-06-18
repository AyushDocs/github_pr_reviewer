import json


def _parse(raw):
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None


def detect_hallucinations(reviews, security_reviews, diffs):
    total = reviews + security_reviews
    flagged = []
    diff_text = "\n".join(d.get("patch", "") for d in diffs).lower()

    generic_patterns = [
        "potential sql injection",
        "potential security vulnerability",
        "potential buffer overflow",
        "should use parameterized",
    ]

    for r in total:
        p = _parse(r["review"])
        if not p:
            continue

        issue = (p.get("issue", "") or "").lower()
        explanation = (p.get("explanation", "") or "").lower()

        for pattern in generic_patterns:
            if pattern in issue and pattern not in diff_text:
                flagged.append(
                    {
                        "file": r["file"],
                        "issue": p.get("issue"),
                        "reason": f"Mentions '{pattern}' but diff doesn't contain related code",
                    }
                )
                break

    return flagged
