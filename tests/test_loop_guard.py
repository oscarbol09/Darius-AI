"""
test_loop_guard.py — Tests unitarios para LoopGuard (prevención de bucles y gestión de contexto)
"""

from __future__ import annotations

from src.darius_ai.core.loop_guard import LoopGuard, LoopStatus


def test_loop_guard_allows_initial_calls():
    guard = LoopGuard(max_identical_calls=3)
    status, msg = guard.record_call("web_search", {"query": "python 3.12"})
    assert status == LoopStatus.OK
    assert guard.call_count == 1


def test_loop_guard_detects_identical_calls():
    guard = LoopGuard(max_identical_calls=3)
    # Llamadas 1 y 2 permitidas
    assert guard.record_call("git_status", {})[0] == LoopStatus.OK
    assert guard.record_call("git_status", {})[0] == LoopStatus.OK
    # Llamada 3 emite advertencia (warn before block)
    status3, msg3 = guard.record_call("git_status", {})
    assert status3 == LoopStatus.WARN
    assert "repetida" in msg3.lower()

    # Llamada 4 se bloquea
    status4, msg4 = guard.record_call("git_status", {})
    assert status4 == LoopStatus.BLOCK
    assert "bloqueada" in msg4.lower()


def test_loop_guard_detects_ping_pong_period_2():
    guard = LoopGuard(max_identical_calls=5, ping_pong_window=4)
    # Secuencia A -> B -> A -> B
    guard.record_call("tool_a", {"param": 1})
    guard.record_call("tool_b", {"param": 2})
    guard.record_call("tool_a", {"param": 1})
    status, msg = guard.record_call("tool_b", {"param": 2})
    assert status in (LoopStatus.WARN, LoopStatus.BLOCK)
    assert "ping-pong" in msg.lower() or "oscilación" in msg.lower()


def test_loop_guard_detects_ping_pong_period_3():
    guard = LoopGuard(max_identical_calls=5, ping_pong_window=6)
    # Secuencia A -> B -> C -> A -> B -> C
    guard.record_call("tool_a", {})
    guard.record_call("tool_b", {})
    guard.record_call("tool_c", {})
    guard.record_call("tool_a", {})
    guard.record_call("tool_b", {})
    status, msg = guard.record_call("tool_c", {})
    assert status in (LoopStatus.WARN, LoopStatus.BLOCK)
    assert "ciclo" in msg.lower() or "oscilación" in msg.lower() or "ping-pong" in msg.lower()


def test_loop_guard_reset():
    guard = LoopGuard(max_identical_calls=2)
    guard.record_call("tool_a", {})
    guard.record_call("tool_a", {})
    guard.reset()
    assert guard.call_count == 0
    status, _ = guard.record_call("tool_a", {})
    assert status == LoopStatus.OK


def test_compress_context_stages():
    guard = LoopGuard()
    messages = [
        {"role": "system", "content": "Eres Darius AI."},
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Ejecuto comando", "tool_calls": [{"name": "cmd", "args": {}}]},
        {"role": "tool", "content": "x" * 3000},
        {"role": "assistant", "content": "Resultado"},
        {"role": "user", "content": "¿Qué sigue?"},
    ]

    compressed = guard.compress_context(messages, max_tool_output_chars=200)
    # El contenido de la herramienta debe haberse truncado en etapa 1
    tool_msg = [m for m in compressed if m.get("role") == "tool"][0]
    assert len(tool_msg["content"]) <= 300
    assert "[Truncado" in tool_msg["content"]
