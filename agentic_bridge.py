"""
agentic_bridge.py — Motor de Automatización Autónoma y CLI Bridge para DARIUS AI
===============================================================================
Permite a Darius interactuar directamente con herramientas del sistema operativo Windows
y utilidades de desarrollo (PowerShell, GitHub CLI 'gh', Git, diagnósticos de red).

Soporta:
  1. Ejecución hermética y segura de comandos con timeouts y limitación de salida.
  2. Detección y clasificación de acciones seguras (diagnósticos/lectura) vs. destructivas.
  3. Formateo y sintetización de salidas de consola para respuestas auditivas naturales.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

log = logging.getLogger("DARIUS.AgenticBridge")

# Límite máximo de salida de texto para evitar saturar el contexto de la IA o el TTS
MAX_OUTPUT_CHARS = 3000

# Palabras clave y comandos clasificados como destructivos o modificadores
DESTRUCTIVE_KEYWORDS = {
    "merge", "delete", "remove", "drop", "destroy", "format", "reboot",
    "shutdown", "kill", "stop-process", "clear-recyclebin", "push --force",
    "reset --hard", "clean -fdx", "branch -d", "branch -D", "pr merge",
    "pr close", "rmdir /s", "del /f", "del /s", "rm -rf"
}


def is_destructive(action_text: str) -> bool:
    """Evalúa si una acción o comando propuesto es potencialmente destructivo."""
    norm = action_text.lower().strip()
    return any(k in norm for k in DESTRUCTIVE_KEYWORDS)


class AgenticBridge:
    """Puente de ejecución para herramientas locales y CLIs activos."""

    def __init__(self):
        self._windir = os.environ.get("SYSTEMROOT", "C:\\Windows")
        self._powershell = os.path.join(self._windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        self._cmd = os.path.join(self._windir, "System32", "cmd.exe")
        self._gh_path = shutil.which("gh") or shutil.which("gh.exe")
        self._git_path = shutil.which("git") or shutil.which("git.exe")

    def execute_powershell(self, command: str, timeout: int = 8) -> tuple[bool, str]:
        """
        Ejecuta un script o comando en PowerShell de forma no interactiva y segura.
        Retorna (éxito: bool, salida_o_error: str).
        """
        if not os.path.exists(self._powershell):
            return False, "PowerShell no está disponible en la ruta estándar del sistema."

        try:
            res = subprocess.run(  # noqa: S603
                [self._powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                output = stdout or "Comando ejecutado sin salida."
                return True, output[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Código de salida: {res.returncode}")[:MAX_OUTPUT_CHARS]
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al ejecutar comando PowerShell."
        except Exception as exc:
            log.error(f"Error al ejecutar PowerShell: {exc}")
            return False, str(exc)

    def execute_cmd(self, command: str, timeout: int = 8) -> tuple[bool, str]:
        """Ejecuta un comando en CMD de Windows."""
        try:
            res = subprocess.run(  # noqa: S603
                f"{self._cmd} /c {command}",
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                return True, (stdout or "Comando ejecutado con éxito.")[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error {res.returncode}")[:MAX_OUTPUT_CHARS]
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s)."
        except Exception as exc:
            return False, str(exc)

    def execute_gh(self, args: str | list[str], timeout: int = 10) -> tuple[bool, str]:
        """
        Ejecuta GitHub CLI ('gh').
        Ejemplos de args:
          - 'pr list --repo oscarbol09/branchbase'
          - 'repo view oscarbol09/Darius-AI'
          - 'issue list'
        """
        gh_bin = self._gh_path or "gh"
        args_list = [a.strip() for a in args.split() if a.strip()] if isinstance(args, str) else list(args)

        # Prevenir ejecución vacía
        if not args_list:
            return False, "No se especificaron argumentos para GitHub CLI."

        try:
            res = subprocess.run(  # noqa: S603
                [gh_bin, *args_list],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                output = stdout or "Consulta de GitHub completada (sin resultados o vacía)."
                return True, output[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error gh code {res.returncode}")[:MAX_OUTPUT_CHARS]
        except FileNotFoundError:
            return False, "GitHub CLI (gh) no está instalado o no se encuentra en el PATH."
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al consultar GitHub CLI."
        except Exception as exc:
            log.error(f"Error en gh cli: {exc}")
            return False, str(exc)

    def execute_git(self, command: str | list[str], repo_path: str = "", timeout: int = 8) -> tuple[bool, str]:
        """Ejecuta un comando de Git localmente."""
        git_bin = self._git_path or "git"
        if isinstance(command, str):
            cmd_list = [c.strip() for c in command.split() if c.strip()]
            if cmd_list and cmd_list[0] == "git":
                cmd_list = cmd_list[1:]
        else:
            cmd_list = list(command)

        cwd = repo_path if repo_path and os.path.isdir(repo_path) else os.getcwd()

        try:
            res = subprocess.run(  # noqa: S603
                [git_bin, *cmd_list],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                return True, (stdout or "Git ejecutado con éxito.")[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error git code {res.returncode}")[:MAX_OUTPUT_CHARS]
        except FileNotFoundError:
            return False, "Git no está instalado o no se encuentra en el PATH."
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al ejecutar Git."
        except Exception as exc:
            return False, str(exc)

    def flush_dns(self) -> tuple[bool, str]:
        """Limpia y vacía la caché de resolución DNS de Windows."""
        return self.execute_cmd("ipconfig /flushdns")

    def get_top_processes(self, count: int = 5) -> tuple[bool, str]:
        """Consulta los procesos que más memoria RAM están consumiendo en Windows."""
        ps_cmd = (
            f"Get-Process | Sort-Object WorkingSet64 -Descending | "
            f"Select-Object -First {count} ProcessName, @{{N='RAM_MB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}} | "
            f"Format-Table -AutoSize | Out-String"
        )
        return self.execute_powershell(ps_cmd)

    def get_system_summary(self) -> tuple[bool, str]:
        """Obtiene un diagnóstico rápido de CPU, RAM libre y espacio en disco."""
        ps_cmd = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$freeRam = [math]::Round($os.FreePhysicalMemory / 1024, 1); "
            "$totalRam = [math]::Round($os.TotalVisibleMemorySize / 1024, 1); "
            "$disk = Get-PSDrive C; "
            "$freeDisk = [math]::Round($disk.Free / 1GB, 1); "
            "Write-Output \"RAM: $freeRam MB libres de $totalRam MB | Disco C: $freeDisk GB libres\""
        )
        return self.execute_powershell(ps_cmd)

    def parse_and_execute_tool(self, tool_name: str, args_str: str = "") -> dict[str, Any]:
        """
        Despachador central de llamadas a herramientas autónomas.
        Retorna:
          {
            "success": bool,
            "tool": str,
            "output": str,
            "is_destructive": bool
          }
        """
        tool_clean = tool_name.strip().lower()
        args_clean = args_str.strip()
        destructive = is_destructive(f"{tool_clean} {args_clean}")

        if tool_clean in ("flush_dns", "limpiar_dns", "ipconfig_flushdns"):
            ok, out = self.flush_dns()
        elif tool_clean in ("top_processes", "procesos_ram", "ver_procesos"):
            ok, out = self.get_top_processes()
        elif tool_clean in ("system_summary", "diagnostico_sistema", "estado_recursos"):
            ok, out = self.get_system_summary()
        elif tool_clean in ("execute_gh", "gh", "github_cli"):
            ok, out = self.execute_gh(args_clean)
        elif tool_clean in ("execute_git", "git"):
            ok, out = self.execute_git(args_clean)
        elif tool_clean in ("execute_powershell", "powershell", "ps"):
            ok, out = self.execute_powershell(args_clean)
        elif tool_clean in ("execute_cmd", "cmd"):
            ok, out = self.execute_cmd(args_clean)
        else:
            ok = False
            out = f"Herramienta desconocida: '{tool_name}'."

        return {
            "success": ok,
            "tool": tool_name,
            "output": out,
            "is_destructive": destructive,
        }


# Instancia singleton accesible globalmente
bridge = AgenticBridge()
