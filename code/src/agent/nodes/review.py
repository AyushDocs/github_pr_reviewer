from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.chains.review_chain import review_chain
from agent.chains.security_chain import security_chain
from agent.chains.models import parse_review_output
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


def _is_trivial(filename: str) -> bool:
    for ext in TRIVIAL_EXTENSIONS:
        if filename.endswith(ext):
            return True
    base = filename.rsplit("/", 1)[-1]
    return base in TRIVIAL_FILENAMES


def _run_safe(chain_fn, diff, diffs, node_type, filename):
    try:
        result = chain_fn(diff=diff["patch"], diffs=diffs)
        return (node_type, filename, result, None)
    except Exception as e:
        log.error("Review failed for %s %s: %s", node_type, filename, e)
        if isinstance(e, (ConnectionError, TimeoutError)):
            raise
        return (node_type, filename, None, str(e))


def review_node(state):
    diffs = state["diffs"]
    reviews = []
    security_reviews = []

    if not diffs:
        log.warning("No diffs to review")
        return {"reviews": [], "security_reviews": []}

    filtered = [d for d in diffs if not _is_trivial(d.get("filename", ""))]
    skipped = len(diffs) - len(filtered)
    if skipped:
        log.info("Skipped %s trivial file(s)", skipped)

    if not filtered:
        log.warning("No non-trivial diffs to review")
        return {"reviews": [], "security_reviews": []}

    log.info("Starting parallel review on %s files", len(filtered))

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

    reviews = _filter_low_severity(reviews, "code review")
    security_reviews = _filter_low_severity(security_reviews, "security review")

    total_attempted = len(filtered) * 2
    degraded = bool(filtered) and not reviews and not security_reviews

    log.info("Review done: %s code, %s security (degraded=%s)", len(reviews), len(security_reviews), degraded)
    return {"reviews": reviews, "security_reviews": security_reviews, "review_degraded": degraded}


def _filter_low_severity(entries: list, label: str) -> list:
    kept = []
    dropped = 0
    for e in entries:
        parsed = parse_review_output(e["review"])
        if parsed and parsed.severity == "LOW":
            dropped += 1
            continue
        kept.append(e)
    if dropped:
        log.info("Filtered out %s LOW severity %s findings", dropped, label)
    return kept
