from agent.utils.logger import get_logger

log = get_logger(__name__)


def validity_gate_node(state):
    quality = state.get("quality_score", 100)
    flags = state.get("hallucination_flags", [])
    injection = state.get("injection_detected", False)
    has_reviews = bool(state.get("reviews", []) or state.get("security_reviews", []))

    should_block = bool(flags) or injection
    if not should_block and has_reviews and quality < 60:
        should_block = True

    if should_block:
        reasons = []
        if injection:
            reasons.append("injection detected")
        if flags:
            reasons.append(f"{len(flags)} hallucination flag(s)")
        if has_reviews and quality < 60:
            reasons.append(f"low quality score ({quality})")
        log.warning("Review blocked: %s", "; ".join(reasons))
    else:
        log.info("Validity check passed (score=%s, flags=%s)", quality, len(flags))

    return {"block_review": should_block}
