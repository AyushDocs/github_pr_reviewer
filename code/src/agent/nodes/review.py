import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.chains.review_chain import review_chain
from agent.chains.security_chain import security_chain
from agent.chains.models import parse_review_output
from agent.config import MAX_CONCURRENT_LLM, MAX_DIFF_CHARS, drain_tokens, estimate_cost
from agent.config_loader import load_config, matches_skip_pattern
from agent.utils.logger import get_logger

log = get_logger(__name__)

TRIVIAL_EXTENSIONS = frozenset({
    ".lock", ".sum", ".hash", ".map",
})
TRIVIAL_FILENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "Gemfile.lock",
    "go.sum", "composer.lock",
})

_MAX_CONTEXT_LINES_PER_HUNK = 3
_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _is_trivial(filename: str) -> bool:
    for ext in TRIVIAL_EXTENSIONS:
        if filename.endswith(ext):
            return True
    base = filename.rsplit("/", 1)[-1]
    return base in TRIVIAL_FILENAMES


_REMOVE_LINE_NUMBERS = re.compile(r"^@@.*@@", re.MULTILINE)


def _preprocess_diff(patch: str) -> str:
    lines = patch.splitlines(keepends=True)
    out = []
    context_count = 0
    for line in lines:
        if line.startswith("+") or line.startswith("-"):
            out.append(line)
            context_count = 0
        elif line.startswith(" "):
            context_count += 1
            if context_count <= _MAX_CONTEXT_LINES_PER_HUNK:
                out.append(line)
        elif line.startswith("@@"):
            context_count = 0
            out.append(line)
        else:
            out.append(line)
    return "".join(out)


def _truncate_diff(patch: str, max_chars: int) -> str:
    if len(patch) <= max_chars:
        return patch
    half = max_chars // 2
    head = patch[:half]
    tail = patch[-half:]
    return f"{head}\n\n... [diff truncated to {max_chars} chars] ...\n\n{tail}"


def _should_skip(filename: str, skip_patterns: list) -> bool:
    if _is_trivial(filename):
        return True
    return matches_skip_pattern(filename, skip_patterns)


def _run_safe(chain_fn, diff, diffs, node_type, filename):
    try:
        raw = diff["patch"]
        processed = _truncate_diff(_preprocess_diff(raw), MAX_DIFF_CHARS)
        result = chain_fn(diff=processed, diffs=diffs)
        return (node_type, filename, result, None)
    except Exception as e:
        log.error("Review failed for %s %s: %s", node_type, filename, e)
        if isinstance(e, (ConnectionError, TimeoutError)):
            raise
        return (node_type, filename, None, str(e))


def review_node(state):
    diffs = state["diffs"]
    repo_name = state.get("repo_name", "")
    config = load_config(repo_name) if repo_name else {}
    skip_patterns = config.get("skip_files", [])
    min_severity = config.get("min_severity", "LOW")
    min_level = _SEVERITY_ORDER.get(min_severity.upper(), 0)

    reviews = []
    security_reviews = []

    if not diffs:
        log.warning("No diffs to review")
        return {"reviews": [], "security_reviews": []}

    filtered = [d for d in diffs if not _should_skip(d.get("filename", ""), skip_patterns)]
    skipped = len(diffs) - len(filtered)
    if skipped:
        log.info("Skipped %s trivial/configured file(s)", skipped)

    if not filtered:
        log.warning("No non-trivial diffs to review")
        return {"reviews": [], "security_reviews": []}

    log.info("Starting parallel review on %s files (semaphore=%s)", len(filtered), MAX_CONCURRENT_LLM)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for diff in filtered:
            futures[executor.submit(_run_safe, review_chain, diff, filtered, "review", diff["filename"])] = diff["filename"]
            futures[executor.submit(_run_safe, security_chain, diff, filtered, "security", diff["filename"])] = diff["filename"]

        for future in as_completed(futures, timeout=300):
            node_type, filename, content, error = future.result()
            if error:
                continue
            entry = {"file": filename, "review": content}
            if node_type == "review":
                reviews.append(entry)
            else:
                security_reviews.append(entry)

    reviews = _filter_low_severity(reviews, "code review", min_level)
    security_reviews = _filter_low_severity(security_reviews, "security review", min_level)

    total_attempted = len(filtered) * 2
    degraded = bool(filtered) and not reviews and not security_reviews

    tokens = drain_tokens()
    prompt_tok = tokens.get("prompt", 0)
    completion_tok = tokens.get("completion", 0)
    cost = estimate_cost(prompt_tok, completion_tok)

    log.info(
        "Review done: %s code, %s security (degraded=%s) | tokens: %s in, %s out | cost: $%.4f",
        len(reviews), len(security_reviews), degraded,
        prompt_tok, completion_tok, cost,
    )

    result = {
        "reviews": reviews,
        "security_reviews": security_reviews,
        "review_degraded": degraded,
        "prompt_tokens": prompt_tok,
        "completion_tokens": completion_tok,
        "total_tokens": prompt_tok + completion_tok,
        "estimated_cost": round(cost, 6),
    }
    return result


def _filter_low_severity(entries: list, label: str, min_level: int = 0) -> list:
    kept = []
    dropped = 0
    for e in entries:
        parsed = parse_review_output(e["review"])
        if parsed:
            sev = _SEVERITY_ORDER.get(parsed.severity.upper(), 0)
            if sev < min_level:
                dropped += 1
                continue
        kept.append(e)
    if dropped:
        log.info("Filtered out %s finding(s) below min severity level %s", dropped, min_level)
    return kept
