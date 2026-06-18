from agent.guards.jailbreak import detect_injection
from agent.utils.logger import get_logger

log = get_logger(__name__)


def jailbreak_gate_node(state):
    diffs = state.get("diffs", [])
    log.info("Running jailbreak scan on %s files", len(diffs))

    result = detect_injection(diffs)

    if result["injection_detected"]:
        log.warning("Jailbreak attempt detected: %s findings", len(result["findings"]))
        for f in result["findings"]:
            log.warning("  %s: %s", f["type"], f["match"])
    else:
        log.info("No injection detected")

    return {
        "injection_detected": result["injection_detected"],
        "injection_findings": result["findings"],
    }
