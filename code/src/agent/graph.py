from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy, CachePolicy
from agent.state import PRState
from agent.nodes.fetch import fetch_node
from agent.nodes.jailbreak_gate import jailbreak_gate_node
from agent.nodes.review import review_node
from agent.nodes.summarize import summarize_node
from agent.nodes.evaluate import evaluate_node
from agent.nodes.validity_gate import validity_gate_node
from agent.nodes.size_gate import pr_size_gate_node
from agent.nodes.human_gate import human_gate_node
from agent.nodes.flag_nodes import flag_injection_node, flag_blocked_node
from agent.nodes.comment import comment_node

graph = StateGraph(PRState)

graph.set_node_defaults(
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        backoff_factor=2.0,
        max_interval=30.0,
        jitter=True,
    ),
    cache_policy=CachePolicy(ttl=1800),
)

graph.add_node("fetch", fetch_node)
graph.add_node("jailbreak_gate", jailbreak_gate_node)
graph.add_node("pr_size_gate", pr_size_gate_node)
graph.add_node("review", review_node,
    retry_policy=RetryPolicy(
        max_attempts=2,
        retry_on=[ConnectionError],
    ),
)
graph.add_node("summarize", summarize_node)
graph.add_node("evaluate", evaluate_node)
graph.add_node("validity_gate", validity_gate_node)
graph.add_node("human_gate", human_gate_node)
graph.add_node("flag_injection", flag_injection_node)
graph.add_node("flag_blocked", flag_blocked_node)
graph.add_node("comment", comment_node,
    retry_policy=RetryPolicy(
        max_attempts=3,
        retry_on=[ConnectionError],
    ),
)

graph.set_entry_point("fetch")


def route_after_jailbreak(state):
    if state.get("injection_detected", False):
        return "flag_injection"
    return "pr_size_gate"


def route_after_size_gate(state):
    if state.get("pr_too_large", False):
        return "flag_blocked"
    return "review"


def route_after_validity(state):
    if state.get("block_review", False):
        return "flag_blocked"
    return "human_gate"


graph.add_edge("fetch", "jailbreak_gate")
graph.add_edge("flag_injection", END)
graph.add_edge("flag_blocked", END)
graph.add_edge("pr_size_gate", "review")

graph.add_edge("review", "summarize")
graph.add_edge("summarize", "evaluate")
graph.add_edge("evaluate", "validity_gate")

graph.add_conditional_edges(
    "jailbreak_gate",
    route_after_jailbreak,
    {"pr_size_gate": "pr_size_gate", "flag_injection": "flag_injection"},
)

graph.add_conditional_edges(
    "pr_size_gate",
    route_after_size_gate,
    {"review": "review", "flag_blocked": "flag_blocked"},
)

graph.add_conditional_edges(
    "validity_gate",
    route_after_validity,
    {"human_gate": "human_gate", "flag_blocked": "flag_blocked"},
)

graph.add_edge("human_gate", "comment")
graph.add_edge("comment", END)

checkpointer = MemorySaver()

app = graph.compile(checkpointer=checkpointer, interrupt_before=["human_gate"])
app_auto = graph.compile()
