"""
test_agentic_bridge.py — Tests Unitarios para el Motor Autónomo AgenticBridge
===========================================================================
Valida:
  1. Detección de comandos destructivos vs seguros.
  2. Ejecución hermética y captura de salidas en PowerShell, CMD, Git y GitHub CLI.
  3. Despachador de herramientas (parse_and_execute_tool).
  4. Manejo de timeouts y límites de salida (MAX_OUTPUT_CHARS).
"""

import subprocess
from unittest.mock import MagicMock, patch

from agentic_bridge import (
    MAX_OUTPUT_CHARS,
    AgenticBridge,
    is_destructive,
)


class TestDestructiveActionFilter:
    """Verifica el clasificador de acciones potencialmente destructivas."""

    def test_safe_read_commands(self):
        assert not is_destructive("gh pr list --repo oscarbol09/branchbase")
        assert not is_destructive("git status --short")
        assert not is_destructive("ipconfig /flushdns")
        assert not is_destructive("Get-Process")
        assert not is_destructive("system_summary")

    def test_destructive_keywords_detected(self):
        assert is_destructive("gh pr merge 101 --admin")
        assert is_destructive("git clean -fdx")
        assert is_destructive("git push --force origin main")
        assert is_destructive("Remove-Item -Recurse -Force C:\\temp")
        assert is_destructive("Stop-Process -Name chrome -Force")
        assert is_destructive("shutdown /r /t 0")
        assert is_destructive("Clear-RecycleBin -Force")


class TestAgenticBridgeExecution:
    """Pruebas unitarias de ejecución de comandos aisladas con mock."""

    @patch("subprocess.run")
    def test_execute_powershell_success(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "ProcessName RAM_MB\nMsMpEng 300\n"
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        ok, out = bridge.execute_powershell("Get-Process")

        assert ok is True
        assert "MsMpEng" in out
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_powershell_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="powershell", timeout=5)

        bridge = AgenticBridge()
        ok, out = bridge.execute_powershell("Start-Sleep 10", timeout=5)

        assert ok is False
        assert "Tiempo de espera agotado" in out

    @patch("subprocess.run")
    def test_execute_cmd_success(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "Configuración IP de Windows\nSe vació la caché de resolución de DNS."
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        ok, out = bridge.flush_dns()

        assert ok is True
        assert "Se vació la caché" in out

    @patch("subprocess.run")
    def test_execute_gh_success(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "101 chore(deps): bump pq\n102 chore(deps): bump actions\n"
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        ok, out = bridge.execute_gh("pr list --repo test/repo")

        assert ok is True
        assert "101 chore" in out

    def test_execute_gh_empty_args(self):
        bridge = AgenticBridge()
        ok, out = bridge.execute_gh("")
        assert ok is False
        assert "No se especificaron argumentos" in out

    @patch("subprocess.run")
    def test_execute_git_strips_prefix(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "M main.py"
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        ok, out = bridge.execute_git("git status --short")

        assert ok is True
        assert "M main.py" in out
        # Verify 'git' is not doubled in args
        called_args = mock_run.call_args[0][0]
        assert called_args[1] == "status"

    @patch("subprocess.run")
    def test_output_truncation(self, mock_run):
        huge_text = "A" * (MAX_OUTPUT_CHARS + 500)
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = huge_text
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        ok, out = bridge.execute_powershell("Get-Content big.log")

        assert ok is True
        assert len(out) <= MAX_OUTPUT_CHARS


class TestToolDispatcher:
    """Verifica el enrutamiento y respuestas de parse_and_execute_tool."""

    @patch("subprocess.run")
    def test_dispatch_flush_dns(self, mock_run):
        mock_res = MagicMock(returncode=0, stdout="DNS limpiado.", stderr="")
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        res = bridge.parse_and_execute_tool("flush_dns")

        assert res["success"] is True
        assert res["tool"] == "flush_dns"
        assert res["is_destructive"] is False
        assert "DNS limpiado." in res["output"]

    @patch("subprocess.run")
    def test_dispatch_gh_prs(self, mock_run):
        mock_res = MagicMock(returncode=0, stdout="PRs listados", stderr="")
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        res = bridge.parse_and_execute_tool("execute_gh", "pr list")

        assert res["success"] is True
        assert res["tool"] == "execute_gh"
        assert not res["is_destructive"]

    @patch("subprocess.run")
    def test_dispatch_destructive_flagged(self, mock_run):
        mock_res = MagicMock(returncode=0, stdout="merged", stderr="")
        mock_run.return_value = mock_res

        bridge = AgenticBridge()
        res = bridge.parse_and_execute_tool("execute_gh", "pr merge 101 --admin")

        assert res["is_destructive"] is True

    def test_dispatch_unknown_tool(self):
        bridge = AgenticBridge()
        res = bridge.parse_and_execute_tool("herramienta_fantasma", "param")

        assert res["success"] is False
        assert "desconocida" in res["output"].lower()
