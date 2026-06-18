import json


def _parse(raw):
    try:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return None


def evaluate_quality(reviews, security_reviews):
    total = reviews + security_reviews
    if not total:
        return {"score": 0.0, "issues": ["No reviews to evaluate"]}

    score = 100.0
    issues = []

    parseable = sum(1 for r in total if _parse(r["review"]) is not None)
    unparseable = len(total) - parseable
    if unparseable:
        score -= unparseable * 15
        issues.append(f"{unparseable} review(s) returned unparseable JSON")

    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    for r in total:
        p = _parse(r["review"])
        if p:
            sev = str(p.get("severity", "")).upper()
            if sev not in valid_severities:
                score -= 10
                issues.append(f"Invalid severity '{sev}' in {r['file']}")

            if not p.get("explanation") or len(p["explanation"]) < 10:
                score -= 5
                issues.append(f"Vague explanation in {r['file']}")

            if not p.get("suggested_fix") or len(p["suggested_fix"]) < 10:
                score -= 5
                issues.append(f"Missing actionable fix in {r['file']}")

    critical_count = sum(
        1
        for r in total
        if (p := _parse(r["review"])) and str(p.get("severity", "")).upper() == "CRITICAL"
    )
    if critical_count > len(total) * 0.5:
        score -= 20
        issues.append(f"High proportion of CRITICAL findings ({critical_count}/{len(total)})")

    return {"score": round(max(0, score), 1), "issues": issues}
