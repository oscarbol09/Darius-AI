"""Safe Code Interpreter — AST validation and sandboxed Python execution for Darius AI."""

from __future__ import annotations

import ast
import builtins
import io
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

# Whitelisted standard library modules permitted for import
_ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "math",
        "json",
        "datetime",
        "re",
        "statistics",
        "random",
        "collections",
        "itertools",
        "decimal",
    }
)

# Names and call targets strictly forbidden inside the interpreter sandbox
_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "memoryview",
        "help",
        "exit",
        "quit",
    }
)


class UnsafeCodeError(ValueError):
    """Raised when submitted code violates safety invariants or AST constraints."""


class ASTValidator:
    """Static AST analyzer that verifies code safety before execution."""

    @classmethod
    def validate(cls, code: str) -> None:
        """Parse code into an AST and verify all statements adhere to sandbox rules.

        Raises:
            UnsafeCodeError: If imports, names, attributes, or syntax violate rules.
        """
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise UnsafeCodeError(f"Syntax error in code: {exc}") from exc

        for node in ast.walk(tree):
            cls._check_node(node)

    @classmethod
    def _check_node(cls, node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_pkg = alias.name.split(".")[0]
                if top_pkg not in _ALLOWED_IMPORTS:
                    raise UnsafeCodeError(f"Import of module '{alias.name}' is not allowed")

        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or not node.module:
                raise UnsafeCodeError("Relative imports are not allowed")
            top_pkg = node.module.split(".")[0]
            if top_pkg not in _ALLOWED_IMPORTS:
                raise UnsafeCodeError(f"Import from module '{node.module}' is not allowed")
            for alias in node.names:
                if alias.name == "*":
                    raise UnsafeCodeError("Wildcard imports ('*') are not allowed")

        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES:
                raise UnsafeCodeError(f"Use of name '{node.id}' is not allowed")
            if node.id.startswith("__") and node.id.endswith("__"):
                raise UnsafeCodeError(f"Dunder name '{node.id}' is blocked")

        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise UnsafeCodeError(f"Access to private/dunder attribute '{node.attr}' is blocked")

        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_NAMES
        ):
            raise UnsafeCodeError(f"Call to '{node.func.id}' is not allowed")


def _build_safe_builtins() -> dict[str, Any]:
    """Construct a restricted __builtins__ dictionary with dangerous functions removed."""
    safe: dict[str, Any] = {}
    for name, obj in vars(builtins).items():
        if name in _FORBIDDEN_NAMES or name.startswith("_"):
            continue
        safe[name] = obj

    # Provide safe __import__ that respects the whitelist
    def _safe_import(
        name: str,
        globals_dict: dict[str, Any] | None = None,
        locals_dict: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level != 0:
            raise UnsafeCodeError("Relative imports are not allowed")
        top_pkg = name.split(".")[0]
        if top_pkg not in _ALLOWED_IMPORTS:
            raise UnsafeCodeError(f"Import of module '{name}' is not allowed")
        return builtins.__import__(name, globals_dict, locals_dict, fromlist, level)

    safe["__import__"] = _safe_import
    return safe


@dataclass
class CodeExecutionResult:
    """Encapsulates the result of a sandboxed code execution."""

    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0


class SafeCodeInterpreter:
    """Safe in-process Python interpreter with AST validation and persistent state."""

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self.reset_state()

    @property
    def state(self) -> dict[str, Any]:
        """Expose current execution state dictionary."""
        return self._state

    def reset_state(self) -> None:
        """Clear local variable state and reset to clean restricted environment."""
        self._state = {"__builtins__": _build_safe_builtins()}

    def validate(self, code: str) -> None:
        """Validate code safety via ASTValidator."""
        ASTValidator.validate(code)

    def run(self, code: str, timeout_seconds: float = 3.0) -> CodeExecutionResult:
        """Execute Python code in the sandbox with timeout and stdout capture.

        Args:
            code: The Python code to run.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            CodeExecutionResult containing status, captured stdout/stderr, and duration.
        """
        start_time = time.perf_counter()

        if not code or not code.strip():
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CodeExecutionResult(
                success=True,
                output="",
                error=None,
                duration_ms=round(elapsed_ms, 2),
            )

        # 1. AST Validation
        try:
            self.validate(code)
        except UnsafeCodeError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"UnsafeCodeError: {exc}",
                duration_ms=round(elapsed_ms, 2),
            )

        # 2. Execution in a daemon thread with timeout
        result_holder: dict[str, Any] = {"output": "", "error": None, "success": True}

        def _worker() -> None:
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            try:
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    compiled = compile(code, "<sandbox>", "exec")
                    exec(compiled, self._state)  # noqa: S102
            except BaseException as exc:  # noqa: BLE001
                result_holder["success"] = False
                result_holder["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                out = stdout_buf.getvalue()
                err = stderr_buf.getvalue()
                if err:
                    out = f"{out}\n{err}" if out else err
                result_holder["output"] = out

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if thread.is_alive():
            if thread.ident is not None:
                try:
                    import ctypes

                    ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_ulong(thread.ident),
                        ctypes.py_object(SystemExit),
                    )
                except Exception:  # noqa: BLE001, S110
                    pass
            return CodeExecutionResult(
                success=False,
                output=result_holder.get("output", ""),
                error=f"Execution timed out after {timeout_seconds} seconds.",
                duration_ms=round(elapsed_ms, 2),
            )

        return CodeExecutionResult(
            success=result_holder["success"],
            output=result_holder["output"],
            error=result_holder["error"],
            duration_ms=round(elapsed_ms, 2),
        )


__all__ = [
    "ASTValidator",
    "CodeExecutionResult",
    "SafeCodeInterpreter",
    "UnsafeCodeError",
]
