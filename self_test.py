"""
self_test.py — Suite de Auto-Certificación y Diagnóstico Hermético para DARIUS AI
================================================================================
Ejecuta una auditoría completa de capacidades, subsistemas y contratos sin efectos
secundarios ni mutaciones destructivas en el sistema del usuario.

Uso:
    python self_test.py
    python main.py --self-test
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_client import resolve_provider_key
from config_loader import cfg
from obsidian_brain import brain
from screen_vision import vision_engine
from workspace_manager import get_monitor_count, get_monitor_rects


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS", "WARN", "FAIL"
    detail: str


def check_audio_subsystem() -> CheckResult:
    """Verifica dispositivos de audio de entrada y salida sin grabar audio real."""
    input_count = 0
    output_count = 0
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_count = sum(1 for d in devices if d.get("max_input_channels", 0) > 0)
        output_count = sum(1 for d in devices if d.get("max_output_channels", 0) > 0)
    except Exception as e:
        return CheckResult("AUDIO SUBSYSTEM", "WARN", f"sounddevice no pudo enumerar dispositivos: {e}")

    if input_count > 0 and output_count > 0:
        return CheckResult(
            "AUDIO SUBSYSTEM",
            "PASS",
            f"Micrófonos detectados: {input_count} | Salidas de audio: {output_count}",
        )
    return CheckResult(
        "AUDIO SUBSYSTEM",
        "WARN",
        f"Dispositivos incompletos (In: {input_count}, Out: {output_count})",
    )


def check_win32_topology() -> CheckResult:
    """Verifica la detección de pantallas y geometría multi-monitor en Windows."""
    try:
        monitors = get_monitor_rects()
        count = get_monitor_count()
        if count > 0:
            details = ", ".join(f"M{i+1}: {r[2]-r[0]}x{r[3]-r[1]}" for i, r in enumerate(monitors))
            return CheckResult("WIN32 TOPOLOGY", "PASS", f"{count} monitor(es) detectado(s) [{details}]")
        return CheckResult("WIN32 TOPOLOGY", "WARN", "No se detectaron monitores Win32")
    except Exception as e:
        return CheckResult("WIN32 TOPOLOGY", "FAIL", f"Error en Win32 EnumDisplayMonitors: {e}")


def check_obsidian_vault() -> CheckResult:
    """Verifica la conectividad y lectura de la bóveda de Obsidian."""
    try:
        vault = brain.vault_path
        if vault.exists():
            return CheckResult("OBSIDIAN VAULT", "PASS", f"Bóveda activa y accesible en: {vault}")
        return CheckResult("OBSIDIAN VAULT", "WARN", f"Bóveda configurada pero no existe: {vault}")
    except Exception as e:
        return CheckResult("OBSIDIAN VAULT", "FAIL", f"Error accediendo a Obsidian: {e}")


def check_byok_providers() -> CheckResult:
    """Verifica el estado de las credenciales de los proveedores de IA configurados."""
    providers = ["gemini", "openai", "openrouter", "groq", "nvidia", "custom"]
    active = cfg.active_provider
    available = []
    for p in providers:
        if resolve_provider_key(p):
            available.append(p)

    active_ready = bool(resolve_provider_key(active) or active == "ollama")
    status = "PASS" if active_ready else "WARN"
    detail = f"Activo: '{active}' ({'Listo' if active_ready else 'Sin clave'}) | Proveedores con clave: {available or 'Ninguno'}"  # noqa: E501
    return CheckResult("BYOK LLM ENGINE", status, detail)


def check_vision_pipeline() -> CheckResult:
    """Verifica la captura de pantalla en memoria con compresión JPEG."""
    try:
        b64, meta = vision_engine.capture_screen_base64(monitor_index=1)
        if b64 and meta.get("size_bytes", 0) > 0:
            return CheckResult(
                "VISION & OCR",
                "PASS",
                f"Captura atómica OK: {meta['width']}x{meta['height']} ({meta['size_bytes']/1024:.1f} KB en memoria)",
            )
        return CheckResult("VISION & OCR", "WARN", "Captura devolvió buffer vacío")
    except Exception as e:
        return CheckResult("VISION & OCR", "WARN", f"Captura no disponible en este entorno: {e}")


def check_tool_contracts() -> CheckResult:
    """Verifica los catálogos de comandos y herramientas registradas."""
    try:
        from windows_commands import SYSTEM_ACTIONS
        actions_count = len(SYSTEM_ACTIONS)

        try:
            from main import _CMD_PATTERNS
            patterns_count = len(_CMD_PATTERNS)
            patterns_msg = f"{patterns_count} patrones regex de voz"
        except Exception:
            patterns_msg = "patrones de voz activos"

        return CheckResult(
            "TOOL CONTRACTS",
            "PASS",
            f"{actions_count} acciones del SO registradas | {patterns_msg}",
        )
    except Exception as e:
        return CheckResult("TOOL CONTRACTS", "FAIL", f"Error validando contratos de herramientas: {e}")


def run_self_test() -> list[CheckResult]:
    """Ejecuta la suite completa de certificación hermética y devuelve los resultados."""
    checks = [
        check_audio_subsystem(),
        check_win32_topology(),
        check_obsidian_vault(),
        check_byok_providers(),
        check_vision_pipeline(),
        check_tool_contracts(),
    ]
    return checks


def print_self_test_report(results: list[CheckResult]) -> int:
    """Imprime el reporte en terminal con formato visual estructurado."""
    print("\n" + "=" * 75, flush=True)
    print("  DARIUS AI — SUITE DE AUTO-CERTIFICACIÓN Y DIAGNÓSTICO HERMÉTICO", flush=True)
    print("=" * 75, flush=True)

    has_fail = False
    use_color = os.name != "nt" or "WT_SESSION" in os.environ
    for res in results:
        badge = f"[{res.status}]"
        if res.status == "PASS":
            status_str = f"\033[92m{badge:<6}\033[0m" if use_color else f"{badge:<6}"
        elif res.status == "WARN":
            status_str = f"\033[93m{badge:<6}\033[0m" if use_color else f"{badge:<6}"
        else:
            status_str = f"\033[91m{badge:<6}\033[0m" if use_color else f"{badge:<6}"
            has_fail = True

        print(f"  {status_str} {res.name:<22} : {res.detail}", flush=True)

    print("-" * 75, flush=True)
    if has_fail:
        print("  [!] RESULTADO: Se encontraron fallos críticos en uno o más subsistemas.\n", flush=True)
        return 1
    print("  [OK] RESULTADO: Todos los contratos y subsistemas operan correctamente.\n", flush=True)
    return 0


def main():
    results = run_self_test()
    code = print_self_test_report(results)
    sys.exit(code)


if __name__ == "__main__":
    main()
