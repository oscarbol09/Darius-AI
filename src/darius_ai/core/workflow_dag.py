"""
workflow_dag.py — Workflow DAG Engine for Darius AI.
===================================================
Directed Acyclic Graph execution engine supporting cycle detection via DFS,
topological sorting via Kahn's algorithm, parallel-ready execution stages,
and context-propagating stage execution with conditional edge routing.
"""

from __future__ import annotations

import ast
import operator
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_SAFE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _safe_eval_condition(expr: str, ctx: dict[str, Any]) -> bool:
    """Safely evaluates simple boolean expressions against context without eval()."""
    expr = expr.strip()
    if not expr:
        return True
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return bool(ctx.get(expr))

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ("True", "true"):
                return True
            if node.id in ("False", "false"):
                return False
            if node.id in ("None", "none", "null"):
                return None
            return ctx.get(node.id)
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                op_type = type(op)
                if op_type not in _SAFE_OPS:
                    raise ValueError(f"Unsupported operator: {op_type}")
                right = _eval(comparator)
                if not _SAFE_OPS[op_type](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(_eval(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(_eval(v) for v in node.values)
        raise ValueError(f"Unsupported AST node: {type(node)}")

    try:
        return bool(_eval(tree))
    except Exception:
        return bool(ctx.get(expr))


@dataclass(slots=True)
class WorkflowNode:
    """Represents an execution step within a WorkflowDAG."""

    id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(slots=True)
class WorkflowEdge:
    """Represents a directed dependency between two WorkflowNodes with optional condition."""

    source: str
    target: str
    condition: str | None = None


class WorkflowDAG:
    """Directed Acyclic Graph orchestrator for multi-agent workflows."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._nodes: dict[str, WorkflowNode] = {}
        self._edges: list[WorkflowEdge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._reverse: dict[str, list[str]] = defaultdict(list)

    @property
    def nodes(self) -> dict[str, WorkflowNode]:
        """Returns registered nodes keyed by ID."""
        return dict(self._nodes)

    @property
    def edges(self) -> list[WorkflowEdge]:
        """Returns registered directed edges."""
        return list(self._edges)

    def add_node(self, node: WorkflowNode) -> None:
        """Adds a node to the workflow DAG."""
        if node.id in self._nodes:
            raise ValueError(f"Duplicate node id: {node.id}")
        self._nodes[node.id] = node

    def add_edge(self, edge: WorkflowEdge) -> None:
        """Adds a directed dependency edge between existing nodes."""
        if edge.source not in self._nodes:
            raise ValueError(f"Source node '{edge.source}' not found")
        if edge.target not in self._nodes:
            raise ValueError(f"Target node '{edge.target}' not found")
        self._edges.append(edge)
        self._adjacency[edge.source].append(edge.target)
        self._reverse[edge.target].append(edge.source)

    def get_node(self, node_id: str) -> WorkflowNode | None:
        """Retrieves a node by its identifier."""
        return self._nodes.get(node_id)

    def validate(self) -> tuple[bool, str]:
        """Validates the DAG structure and detects cycles using DFS."""
        visited: set[str] = set()
        in_stack: set[str] = set()

        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            in_stack.add(node_id)
            for neighbor in self._adjacency.get(node_id, []):
                if neighbor in in_stack:
                    return True  # Cycle detected
                if neighbor not in visited and _dfs(neighbor):
                    return True
            in_stack.discard(node_id)
            return False

        for node_id in self._nodes:
            if node_id not in visited and _dfs(node_id):
                return False, f"Cycle detected involving node '{node_id}'"

        return True, ""

    def topological_sort(self) -> list[str]:
        """Returns node IDs in topological order using Kahn's algorithm."""
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for edge in self._edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = deque(sorted(nid for nid, deg in in_degree.items() if deg == 0))
        order: list[str] = []

        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for neighbor in sorted(self._adjacency.get(node_id, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            raise ValueError("Graph contains a cycle; topological sort is impossible")
        return order

    def execution_stages(self) -> list[list[str]]:
        """Groups nodes into parallel-ready execution stages whose dependencies are satisfied."""
        valid, msg = self.validate()
        if not valid:
            raise ValueError(f"Graph contains a cycle; execution stages impossible: {msg}")

        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for edge in self._edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        stages: list[list[str]] = []
        ready = sorted(nid for nid, deg in in_degree.items() if deg == 0)

        while ready:
            stages.append(ready)
            next_ready: list[str] = []
            for node_id in ready:
                for neighbor in self._adjacency.get(node_id, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_ready.append(neighbor)
            ready = sorted(next_ready)

        return stages

    def execute(self, executor_fn: Callable[[WorkflowNode, dict[str, Any]], Any]) -> dict[str, Any]:
        """Executes the DAG stage by stage, propagating context and intermediate variables."""
        valid, msg = self.validate()
        if not valid:
            raise ValueError(f"Invalid workflow DAG: {msg}")

        context: dict[str, Any] = {}
        stages = self.execution_stages()

        for stage in stages:
            for node_id in stage:
                # Evaluate incoming edge conditions
                incoming_edges = [e for e in self._edges if e.target == node_id]
                should_execute = True

                for edge in incoming_edges:
                    if edge.condition is not None and not _safe_eval_condition(edge.condition, context):
                        should_execute = False
                        break

                if not should_execute:
                    continue

                node = self._nodes[node_id]
                result = executor_fn(node, context)
                context[node_id] = result

        return context


__all__ = ["WorkflowDAG", "WorkflowEdge", "WorkflowNode"]
