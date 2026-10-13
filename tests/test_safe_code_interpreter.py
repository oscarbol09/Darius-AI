"""Unit tests for Safe Code Interpreter (AST validation and sandboxed execution)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Ensure src is on sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from darius_ai.core.safe_code_interpreter import (
        ASTValidator,
        CodeExecutionResult,
        SafeCodeInterpreter,
        UnsafeCodeError,
    )
except ImportError:
    from src.darius_ai.core.safe_code_interpreter import (
        ASTValidator,
        CodeExecutionResult,
        SafeCodeInterpreter,
        UnsafeCodeError,
    )


# ============================================================================
# ASTValidator Tests
# ============================================================================


def test_ast_validator_allows_safe_code():
    """Verify standard arithmetic, functions, loops, and data structures pass validation."""
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

total = sum([factorial(i) for i in range(1, 5)])
data = {"total": total, "valid": True}
"""
    ASTValidator.validate(code)


def test_ast_validator_allows_whitelisted_imports():
    """Verify all 9 whitelisted standard modules are permitted."""
    allowed_imports = [
        "import math",
        "import json",
        "import datetime",
        "import re",
        "import statistics",
        "import random",
        "import collections",
        "import itertools",
        "import decimal",
        "from math import sqrt, pi",
        "from collections import defaultdict, Counter",
        "from datetime import datetime, timezone",
        "from decimal import Decimal",
    ]
    for statement in allowed_imports:
        ASTValidator.validate(statement)


def test_ast_validator_rejects_unwhitelisted_imports():
    """Verify non-whitelisted modules are rejected with UnsafeCodeError."""
    forbidden_imports = [
        "import os",
        "import sys",
        "import subprocess",
        "import socket",
        "import urllib",
        "import requests",
        "import shutil",
        "import ctypes",
        "import pickle",
        "from os import path",
        "from sys import modules",
        "from subprocess import Popen",
        "import os.path",
    ]
    for statement in forbidden_imports:
        with pytest.raises(UnsafeCodeError) as exc_info:
            ASTValidator.validate(statement)
        assert "not allowed" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_ast_validator_rejects_forbidden_names_and_calls():
    """Verify dangerous runtime introspection and IO functions are rejected."""
    forbidden_snippets = [
        "eval('2 + 2')",
        "exec('x = 10')",
        "compile('x = 1', '<string>', 'exec')",
        "__import__('os')",
        "open('/etc/passwd', 'r')",
        "input('Enter key: ')",
        "breakpoint()",
        "g = globals()",
        "l = locals()",
        "v = vars()",
        "getattr(math, 'sin')",
        "setattr(obj, 'val', 123)",
        "delattr(obj, 'val')",
        "foo = eval",  # assignment without call
        "bar = open",
    ]
    for snippet in forbidden_snippets:
        with pytest.raises(UnsafeCodeError) as exc_info:
            ASTValidator.validate(snippet)
        assert (
            "not allowed" in str(exc_info.value).lower()
            or "forbidden" in str(exc_info.value).lower()
            or "blocked" in str(exc_info.value).lower()
        )


def test_ast_validator_rejects_private_and_dunder_attributes():
    """Verify attribute walks, dunders, and private attributes are blocked."""
    dunder_snippets = [
        "().__class__.__base__",
        "x.__dict__",
        "f.__code__",
        "m.__builtins__",
        "x.__subclasses__()",
        "obj._private_method()",
        "data._internal_cache",
    ]
    for snippet in dunder_snippets:
        with pytest.raises(UnsafeCodeError) as exc_info:
            ASTValidator.validate(snippet)
        assert (
            "private" in str(exc_info.value).lower()
            or "dunder" in str(exc_info.value).lower()
            or "blocked" in str(exc_info.value).lower()
        )


def test_ast_validator_rejects_syntax_errors():
    """Verify invalid Python syntax raises UnsafeCodeError."""
    with pytest.raises(UnsafeCodeError):
        ASTValidator.validate("def broken_syntax(")


# ============================================================================
# SafeCodeInterpreter Tests
# ============================================================================


def test_interpreter_executes_simple_code():
    """Verify basic code execution captures stdout and returns success."""
    interpreter = SafeCodeInterpreter()
    result = interpreter.run("print('Hello from Darius!')")
    assert isinstance(result, CodeExecutionResult)
    assert result.success is True
    assert "Hello from Darius!" in result.output
    assert result.error is None
    assert result.duration_ms >= 0.0


def test_interpreter_captures_multiple_prints():
    """Verify sequential print outputs are captured accurately."""
    interpreter = SafeCodeInterpreter()
    code = """
for i in range(3):
    print(f"Step {i}")
"""
    result = interpreter.run(code)
    assert result.success is True
    assert "Step 0\nStep 1\nStep 2" in result.output


def test_interpreter_state_persistence_between_runs():
    """Verify variables and state persist across consecutive run calls."""
    interpreter = SafeCodeInterpreter()
    res1 = interpreter.run("accum = 100\nstep = 25")
    assert res1.success is True

    res2 = interpreter.run("accum += step\nprint('Total:', accum)")
    assert res2.success is True
    assert "Total: 125" in res2.output

    res3 = interpreter.run("def mul(x): return x * 2")
    assert res3.success is True

    res4 = interpreter.run("print('Multiplied:', mul(accum))")
    assert res4.success is True
    assert "Multiplied: 250" in res4.output


def test_interpreter_reset_state():
    """Verify reset_state clears previously defined variables and functions."""
    interpreter = SafeCodeInterpreter()
    interpreter.run("cached_var = 999")
    assert "cached_var" in interpreter.state

    interpreter.reset_state()
    assert "cached_var" not in interpreter.state

    res = interpreter.run("print(cached_var)")
    assert res.success is False
    assert res.error is not None
    assert "NameError" in res.error


def test_interpreter_whitelisted_module_execution():
    """Verify whitelisted modules can be imported and executed inside the sandbox."""
    interpreter = SafeCodeInterpreter()
    code = """
import math
import json
import statistics

data = [10, 20, 30, 40]
mean_val = statistics.mean(data)
sqrt_val = math.sqrt(mean_val)
output_payload = json.dumps({"mean": mean_val, "sqrt": round(sqrt_val, 2)})
print(output_payload)
"""
    result = interpreter.run(code)
    assert result.success is True
    assert '"mean": 25' in result.output
    assert '"sqrt": 5.0' in result.output


def test_interpreter_blocks_unsafe_code_execution():
    """Verify attempting to run unsafe code fails validation and does not execute."""
    interpreter = SafeCodeInterpreter()
    unsafe_code = "import os; os.system('echo hacked')"
    result = interpreter.run(unsafe_code)
    assert result.success is False
    assert result.error is not None
    assert "UnsafeCodeError" in result.error or "not allowed" in result.error


def test_interpreter_handles_runtime_exceptions():
    """Verify runtime exceptions like ZeroDivisionError or KeyError are handled safely."""
    interpreter = SafeCodeInterpreter()
    result = interpreter.run("x = 10 / 0")
    assert result.success is False
    assert result.error is not None
    assert "ZeroDivisionError" in result.error


def test_interpreter_enforces_timeout():
    """Verify infinite loops or long executions terminate within timeout_seconds."""
    interpreter = SafeCodeInterpreter()
    start_time = time.time()
    infinite_loop = """
while True:
    pass
"""
    result = interpreter.run(infinite_loop, timeout_seconds=0.5)
    elapsed = time.time() - start_time
    assert result.success is False
    assert result.error is not None
    assert "timed out" in result.error.lower()
    assert elapsed < 3.0  # Must terminate promptly


def test_interpreter_empty_code():
    """Verify empty or whitespace-only code executes gracefully without errors."""
    interpreter = SafeCodeInterpreter()
    result = interpreter.run("   \n\t  ")
    assert result.success is True
    assert result.output == ""
    assert result.error is None


def test_ast_validator_rejects_wildcard_and_relative_imports():
    """Verify wildcard and relative imports are strictly prohibited."""
    with pytest.raises(UnsafeCodeError, match="Wildcard"):
        ASTValidator.validate("from math import *")

    with pytest.raises(UnsafeCodeError, match="Relative"):
        ASTValidator.validate("from .utils import helper")


def test_interpreter_builtins_safe_import():
    """Verify restricted builtins __import__ raises UnsafeCodeError for forbidden modules."""
    interpreter = SafeCodeInterpreter()
    safe_import = interpreter.state["__builtins__"]["__import__"]
    # math is allowed
    mod = safe_import("math")
    assert mod.sqrt(4) == 2.0

    # os is rejected
    with pytest.raises(UnsafeCodeError, match="not allowed"):
        safe_import("os")

    # relative import is rejected
    with pytest.raises(UnsafeCodeError, match="Relative"):
        safe_import("math", level=1)

