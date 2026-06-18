from langgraph.pregel import Pregel
from langgraph.graph import StateGraph
from agent.graph import graph, app, app_auto


def test_graph_is_stategraph():
    assert isinstance(graph, StateGraph)


def test_app_is_pregel():
    assert isinstance(app, Pregel)


def test_app_auto_is_pregel():
    assert isinstance(app_auto, Pregel)


def test_graph_has_expected_nodes():
    nodes = list(graph.nodes.keys())
    assert "fetch" in nodes
    assert "jailbreak_gate" in nodes
    assert "pr_size_gate" in nodes
    assert "review" in nodes
    assert "summarize" in nodes
    assert "evaluate" in nodes
    assert "validity_gate" in nodes
    assert "human_gate" in nodes
    assert "flag_injection" in nodes
    assert "flag_blocked" in nodes
    assert "comment" in nodes


def test_compiled_graph_has_expected_nodes():
    nodes = list(app.nodes.keys())
    assert "fetch" in nodes
    assert "jailbreak_gate" in nodes
    assert "pr_size_gate" in nodes
    assert "review" in nodes
    assert "summarize" in nodes
    assert "evaluate" in nodes
    assert "validity_gate" in nodes
    assert "human_gate" in nodes
    assert "flag_injection" in nodes
    assert "flag_blocked" in nodes
    assert "comment" in nodes
