import re
import base64

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous\s+)?(instructions?|prompts?|directives?)",
    r"(?i)forget\s+(all\s+)?(previous\s+)?(instructions?|prompts?|context)",
    r"(?i)system\s+prompt",
    r"(?i)you\s+(are|should\s+now\s+be)\s+(a\s+)?(free|unrestricted|unbounded|new)",
    r"(?i)respond\s+(with|only|using)\s+",
    r"(?i)disregard\s+(all\s+)?(rules?|guidelines?|instructions?)",
    r"(?i)output\s+(only|just|the\s+word)\s+",
    '(?i)say\\s+(the\\s+word\\s+)?\\"(safe|clean|ok|approved|no\\s+issues)\\"',
]

SUSPICIOUS_COMMENT_PATTERNS = [
    r"<!--[\s\S]*?(ignore|system|forget|disregard)[\s\S]*?-->",
    r"/\*[\s\S]*?(ignore|system|forget|disregard)[\s\S]*?\*/",
]

ENCODED_PAYLOAD_RE = r"[A-Za-z0-9+/]{60,}={0,2}"


def _decode_base64_attempts(text: str) -> list:
    found = []
    for match in re.finditer(ENCODED_PAYLOAD_RE, text):
        try:
            decoded = base64.b64decode(match.group()).decode("utf-8", errors="ignore")
            if any(re.search(p, decoded) for p in INJECTION_PATTERNS):
                found.append(decoded[:200])
        except Exception:
            pass
    return found


def detect_injection(diffs: list) -> dict:
    combined = ""
    for d in diffs:
        patch = d.get("patch", "")
        combined += patch + "\n"

    findings = []

    for pattern in INJECTION_PATTERNS:
        for match in re.finditer(pattern, combined):
            findings.append({
                "type": "prompt_injection",
                "pattern": pattern,
                "match": match.group().strip()[:100],
            })

    for pattern in SUSPICIOUS_COMMENT_PATTERNS:
        for match in re.finditer(pattern, combined):
            findings.append({
                "type": "suspicious_comment",
                "pattern": pattern,
                "match": match.group().strip()[:100],
            })

    decoded = _decode_base64_attempts(combined)
    for d in decoded:
        findings.append({
            "type": "encoded_payload",
            "pattern": "base64",
            "match": d[:100],
        })

    return {
        "injection_detected": len(findings) > 0,
        "findings": findings,
    }
