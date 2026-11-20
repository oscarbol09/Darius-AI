<p align="center">
  🇺🇸 <b>English</b> &nbsp;|&nbsp; 🇪🇸 <a href="CONTRIBUTING.es.md"><b>Español</b></a>
</p>

# Contributing to Darius AI

Thank you for your interest in contributing to **Darius AI**. This guide covers environment setup, testing gates, and the engineering standards enforced across the repository.

---

## Environment Requirements

- **Operating System:** Windows 10 (build 19041+) or Windows 11.
- **Python:** 3.11 or 3.12 (3.12 recommended).
- **Git** and **uv** or `pip`.

---

## Development Setup

```powershell
git clone https://github.com/oscarbol09/Darius-AI.git
cd Darius-AI

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## Testing & Verification Gates

Before opening a Pull Request or committing changes, ensure every automated gate passes locally:

```powershell
# Run the full hermetic unit & integration suite (no live network/API calls)
pytest tests/ -v -m "not live"

# Enforce code quality & lint rules with Ruff (must exit with 0 errors)
ruff check .
ruff format --check .

# Enforce strict static typing against the win32 runtime target
mypy src/
```

New features or bug fixes must maintain at least **80% line coverage** (`--cov=src/darius_ai --cov-fail-under=80`) and must include regression tests using mocks/fixtures so CI remains offline-safe and deterministic.

---

## Engineering & Architecture Standards

- **Zero `shell=True` Subprocesses:** Never pass `shell=True` to `subprocess`. Route OS commands through validated argument lists and explicit `%SystemRoot%\System32` paths (`src/darius_ai/system/windows_commands.py`).
- **60 FPS Canvas Hygiene:** In `CyberCoreVisualizer`, `FloatingVoiceCapsule`, and `ContextMeshVisualizer`, never call `canvas.delete("all")` inside animation loops. Pre-allocate items and update geometry with `canvas.coords()` to prevent Tcl memory churn and visual flicker.
- **Dual-Language i18n (EN / ES):** All new UI strings, system statuses, voice prompts, and command aliases must register keys in both `"en"` and `"es"` dictionaries inside `src/darius_ai/core/i18n.py` and keep English as the default fallback.
- **BYOK HTTP Architecture:** When extending LLM providers in `src/darius_ai/core/ai_client.py`, prefer lightweight OpenAI-compatible REST transport via `urllib` to keep runtime dependencies portable.
- **Structured Error Handling:** Catch explicit exceptions and log diagnostic context via `log.warning` or `log.error`. Never suppress failures silently with bare `except: pass`.
- **Static Type Annotations:** Add PEP 484 / `from __future__ import annotations` type hints to all new functions and classes.
- **Commit Convention:** Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`, `chore:`) explaining **why** the change was made in the commit body.
