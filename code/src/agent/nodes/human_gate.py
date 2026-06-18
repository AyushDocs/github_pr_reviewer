from agent.utils.logger import get_logger

log = get_logger(__name__)


def human_gate_node(state):
    log.info("Awaiting human approval for PR #%s", state["pr_number"])
    return {}
