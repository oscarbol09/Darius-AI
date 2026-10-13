"""
test_workflow_dag.py — Unit tests for Workflow DAG Engine in Darius AI.
"""

import pytest

from src.darius_ai.core.workflow_dag import (
    WorkflowDAG,
    WorkflowEdge,
    WorkflowNode,
)


def test_workflow_node_initialization():
    """Validates WorkflowNode dataclass creation and defaults."""
    node = WorkflowNode(id="step_1", action="analyze_screen")
    assert node.id == "step_1"
    assert node.action == "analyze_screen"
    assert node.params == {}
    assert node.description == ""

    custom_node = WorkflowNode(
        id="step_2",
        action="search_web",
        params={"query": "python async"},
        description="Search for async patterns",
    )
    assert custom_node.params["query"] == "python async"
    assert custom_node.description == "Search for async patterns"


def test_workflow_edge_initialization():
    """Validates WorkflowEdge dataclass creation and defaults."""
    edge = WorkflowEdge(source="step_1", target="step_2")
    assert edge.source == "step_1"
    assert edge.target == "step_2"
    assert edge.condition is None

    cond_edge = WorkflowEdge(source="step_1", target="step_3", condition="success")
    assert cond_edge.condition == "success"


def test_workflow_dag_add_nodes_and_edges():
    """Validates adding nodes and edges, preventing duplicate nodes and dangling edges."""
    dag = WorkflowDAG()
    n1 = WorkflowNode(id="A", action="act_a")
    n2 = WorkflowNode(id="B", action="act_b")

    dag.add_node(n1)
    dag.add_node(n2)
    assert len(dag.nodes) == 2

    # Duplicate node ID
    with pytest.raises(ValueError, match="Duplicate node id: A"):
        dag.add_node(n1)

    # Edge with non-existent source
    with pytest.raises(ValueError, match="Source node 'X' not found"):
        dag.add_edge(WorkflowEdge(source="X", target="B"))

    # Edge with non-existent target
    with pytest.raises(ValueError, match="Target node 'Y' not found"):
        dag.add_edge(WorkflowEdge(source="A", target="Y"))

    # Valid edge
    dag.add_edge(WorkflowEdge(source="A", target="B"))
    assert len(dag.edges) == 1


def test_workflow_dag_validation_valid():
    """Validates cycle-free DAGs return valid tuple."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="A", action="act"))
    dag.add_node(WorkflowNode(id="B", action="act"))
    dag.add_node(WorkflowNode(id="C", action="act"))
    dag.add_edge(WorkflowEdge(source="A", target="B"))
    dag.add_edge(WorkflowEdge(source="B", target="C"))

    valid, msg = dag.validate()
    assert valid is True
    assert msg == ""


def test_workflow_dag_validation_cycle_detection():
    """Validates cycle detection via DFS."""
    # Self loop
    dag_self = WorkflowDAG()
    dag_self.add_node(WorkflowNode(id="A", action="act"))
    dag_self.add_edge(WorkflowEdge(source="A", target="A"))
    valid, msg = dag_self.validate()
    assert valid is False
    assert "Cycle detected" in msg

    # Direct 2-node cycle
    dag_2 = WorkflowDAG()
    dag_2.add_node(WorkflowNode(id="A", action="act"))
    dag_2.add_node(WorkflowNode(id="B", action="act"))
    dag_2.add_edge(WorkflowEdge(source="A", target="B"))
    dag_2.add_edge(WorkflowEdge(source="B", target="A"))
    valid, msg = dag_2.validate()
    assert valid is False
    assert "Cycle detected" in msg

    # 3-node cycle
    dag_3 = WorkflowDAG()
    dag_3.add_node(WorkflowNode(id="A", action="act"))
    dag_3.add_node(WorkflowNode(id="B", action="act"))
    dag_3.add_node(WorkflowNode(id="C", action="act"))
    dag_3.add_edge(WorkflowEdge(source="A", target="B"))
    dag_3.add_edge(WorkflowEdge(source="B", target="C"))
    dag_3.add_edge(WorkflowEdge(source="C", target="A"))
    valid, msg = dag_3.validate()
    assert valid is False
    assert "Cycle detected" in msg


def test_workflow_dag_topological_sort():
    """Validates Kahn's algorithm topological sorting."""
    dag = WorkflowDAG()
    for nid in ["A", "B", "C", "D"]:
        dag.add_node(WorkflowNode(id=nid, action="act"))

    dag.add_edge(WorkflowEdge(source="A", target="B"))
    dag.add_edge(WorkflowEdge(source="A", target="C"))
    dag.add_edge(WorkflowEdge(source="B", target="D"))
    dag.add_edge(WorkflowEdge(source="C", target="D"))

    order = dag.topological_sort()
    assert len(order) == 4
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")


def test_workflow_dag_topological_sort_with_cycle():
    """Validates topological sort raises ValueError on cycles."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="A", action="act"))
    dag.add_node(WorkflowNode(id="B", action="act"))
    dag.add_edge(WorkflowEdge(source="A", target="B"))
    dag.add_edge(WorkflowEdge(source="B", target="A"))

    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort()


def test_workflow_dag_execution_stages():
    """Validates execution stages for parallel-ready groupings."""
    dag = WorkflowDAG()
    for nid in ["A", "B", "C", "D", "E"]:
        dag.add_node(WorkflowNode(id=nid, action="act"))

    # A -> B, A -> C
    # B -> D, C -> D
    # E is independent root
    dag.add_edge(WorkflowEdge(source="A", target="B"))
    dag.add_edge(WorkflowEdge(source="A", target="C"))
    dag.add_edge(WorkflowEdge(source="B", target="D"))
    dag.add_edge(WorkflowEdge(source="C", target="D"))

    stages = dag.execution_stages()
    assert len(stages) == 3
    # Stage 0: nodes with no dependencies (A and E)
    assert sorted(stages[0]) == ["A", "E"]
    # Stage 1: B and C
    assert sorted(stages[1]) == ["B", "C"]
    # Stage 2: D
    assert stages[2] == ["D"]


def test_workflow_dag_execution_stages_with_cycle():
    """Validates execution_stages raises ValueError on cyclic graphs."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="A", action="act"))
    dag.add_edge(WorkflowEdge(source="A", target="A"))

    with pytest.raises(ValueError, match="cycle"):
        dag.execution_stages()


def test_workflow_dag_execute_linear_flow():
    """Validates execute() sequentially evaluates nodes and stores outputs in context."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="fetch", action="fetch_data", params={"url": "http://api"}))
    dag.add_node(WorkflowNode(id="process", action="process_data"))
    dag.add_node(WorkflowNode(id="save", action="save_data"))

    dag.add_edge(WorkflowEdge(source="fetch", target="process"))
    dag.add_edge(WorkflowEdge(source="process", target="save"))

    execution_log = []

    def executor(node: WorkflowNode, ctx: dict) -> str:
        execution_log.append(node.id)
        if node.id == "fetch":
            return f"raw_data_from_{node.params['url']}"
        if node.id == "process":
            return f"cleaned_{ctx['fetch']}"
        if node.id == "save":
            return f"saved_{ctx['process']}"
        return "ok"

    ctx = dag.execute(executor)
    assert execution_log == ["fetch", "process", "save"]
    assert ctx["fetch"] == "raw_data_from_http://api"
    assert ctx["process"] == "cleaned_raw_data_from_http://api"
    assert ctx["save"] == "saved_cleaned_raw_data_from_http://api"


def test_workflow_dag_execute_parallel_propagation():
    """Validates execute() propagates intermediate variables through multiple stages."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="init", action="setup"))
    dag.add_node(WorkflowNode(id="branch_1", action="calc_1"))
    dag.add_node(WorkflowNode(id="branch_2", action="calc_2"))
    dag.add_node(WorkflowNode(id="combine", action="merge"))

    dag.add_edge(WorkflowEdge(source="init", target="branch_1"))
    dag.add_edge(WorkflowEdge(source="init", target="branch_2"))
    dag.add_edge(WorkflowEdge(source="branch_1", target="combine"))
    dag.add_edge(WorkflowEdge(source="branch_2", target="combine"))

    def executor(node: WorkflowNode, ctx: dict):
        if node.id == "init":
            return 10
        if node.id == "branch_1":
            return ctx["init"] * 2
        if node.id == "branch_2":
            return ctx["init"] + 5
        if node.id == "combine":
            return ctx["branch_1"] + ctx["branch_2"]
        return None

    ctx = dag.execute(executor)
    assert ctx["init"] == 10
    assert ctx["branch_1"] == 20
    assert ctx["branch_2"] == 15
    assert ctx["combine"] == 35


def test_workflow_dag_execute_conditional_edges():
    """Validates execute() checks edge conditions against context."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="check", action="health_check"))
    dag.add_node(WorkflowNode(id="on_success", action="proceed"))
    dag.add_node(WorkflowNode(id="on_failure", action="remediate"))

    dag.add_edge(WorkflowEdge(source="check", target="on_success", condition="check == True"))
    dag.add_edge(WorkflowEdge(source="check", target="on_failure", condition="check == False"))

    executed = []

    def executor(node: WorkflowNode, ctx: dict):
        executed.append(node.id)
        if node.id == "check":
            return True
        return f"done_{node.id}"

    ctx = dag.execute(executor)
    assert "on_success" in executed
    assert "on_failure" not in executed
    assert ctx["on_success"] == "done_on_success"
    assert "on_failure" not in ctx


def test_workflow_dag_execute_invalid_cycle():
    """Validates execute() raises ValueError if graph contains a cycle."""
    dag = WorkflowDAG()
    dag.add_node(WorkflowNode(id="A", action="act"))
    dag.add_edge(WorkflowEdge(source="A", target="A"))

    with pytest.raises(ValueError, match="Invalid workflow DAG"):
        dag.execute(lambda node, ctx: None)


def test_workflow_dag_get_node():
    """Validates get_node returns existing node or None."""
    dag = WorkflowDAG()
    n = WorkflowNode(id="X", action="test")
    dag.add_node(n)
    assert dag.get_node("X") is n
    assert dag.get_node("nonexistent") is None


def test_workflow_dag_advanced_condition_expressions():
    """Validates condition evaluation with logic operators and fallback."""
    from src.darius_ai.core.workflow_dag import _safe_eval_condition

    ctx = {"count": 5, "tag": "prod", "ready": True, "items": ["a", "b"], "empty_val": None}

    assert _safe_eval_condition("", ctx) is True
    assert _safe_eval_condition("ready and count > 2", ctx) is True
    assert _safe_eval_condition("not ready or count == 5", ctx) is True
    assert _safe_eval_condition("'a' in items", ctx) is True
    assert _safe_eval_condition("'c' not in items", ctx) is True
    assert _safe_eval_condition("empty_val is None", ctx) is True
    assert _safe_eval_condition("count != 10", ctx) is True
    assert _safe_eval_condition("tag == 'dev'", ctx) is False
    # Fallback to key lookup on syntax error
    assert _safe_eval_condition("ready", ctx) is True
    assert _safe_eval_condition("nonexistent", ctx) is False

