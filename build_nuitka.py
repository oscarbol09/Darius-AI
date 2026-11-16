"""
build_nuitka.py — Compilador Nativo Standalone con Nuitka para DARIUS AI
========================================================================
Compila todo el proyecto de Darius AI a código máquina C/C++ nativo de Windows,
generando una distribución standalone ultra-rápida y sin falsos positivos en antivirus.

Uso:
    python build_nuitka.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path


def _load_project_version(root_dir: Path) -> str:
    """Lee la versión canónica desde pyproject.toml."""
    pyproject = root_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            ver = str(data.get("project", {}).get("version", "")).strip()
            if ver:
                return ver
        except Exception as exc:
            print(f"[WARN] No se pudo leer pyproject.toml ({exc}); usando fallback.")
    return "8.5.0"


def _resolve_windows_version(root_dir: Path) -> tuple[str, str]:
    """
    Resuelve la versión semántica y el formato Windows de 4 componentes (X.Y.Z.0).
    Ignora nombres de rama no numéricos (ej. 'main' durante workflow_dispatch).
    """
    fallback_ver = _load_project_version(root_dir)
    candidate = os.environ.get("DARIUS_RELEASE_VERSION") or os.environ.get("GITHUB_REF_NAME", "")
    cleaned = candidate.strip().lstrip("v")
    match = re.match(r"^(\d+(?:\.\d+){1,3})", cleaned)
    semver = match.group(1) if match else fallback_ver

    parts = semver.split(".")
    while len(parts) < 4:
        parts.append("0")
    return semver, ".".join(parts[:4])


def main():
    root_dir = Path(__file__).resolve().parent
    os.chdir(root_dir)
    semver, win_version = _resolve_windows_version(root_dir)

    print("=" * 70)
    print(f"  DARIUS AI — COMPILACIÓN NATIVA STANDALONE CON NUITKA (v{semver})")
    print("=" * 70)

    # 1. Asegurar icono
    icon_script = root_dir / "assets" / "generate_icon.py"
    icon_path = root_dir / "assets" / "darius.ico"
    if not icon_path.exists() and icon_script.exists():
        print("\n[*] Generando icono de la aplicación...")
        subprocess.run([sys.executable, str(icon_script)], check=True)  # noqa: S603

    # 2. Verificar plantilla de configuración para empaquetado
    template_path = root_dir / "config.template.json"
    if not template_path.exists():
        raise FileNotFoundError("Falta config.template.json requerido para empaquetar Darius AI.")

    # 3. Verificar dependencias de build
    print("\n[*] Verificando herramientas de compilación...")
    try:
        import nuitka  # noqa: F401
    except ImportError:
        print("[*] Instalando Nuitka y aceleradores (zstandard, ordered-set)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "nuitka>=2.4.0", "zstandard", "ordered-set"], check=True
        )

    # 4. Construir comando Nuitka
    output_dir = root_dir / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--low-memory",
        "--lto=no",
        "--jobs=2",
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        "--enable-plugin=anti-bloat",
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--nofollow-import-to=tests,pytest,unittest",
        "--include-package=src",
        "--include-package=customtkinter",
        "--include-package-data=customtkinter",
        "--include-package=speech_recognition",
        "--include-package-data=speech_recognition",
        "--include-data-files=config.template.json=config.json",
        "--include-data-files=assets/darius.ico=assets/darius.ico",
        f"--windows-icon-from-ico={icon_path}",
        "--company-name=Oscarbol09",
        "--product-name=Darius AI",
        f"--file-version={win_version}",
        f"--product-version={win_version}",
        "--file-description=Darius AI - Asistente de Escritorio y Automatizacion por Voz",
        "--copyright=Copyright (C) 2026 Oscarbol09 (https://github.com/oscarbol09/Darius-AI)",
        "--output-dir=dist",
        "--output-filename=DariusAI.exe",
        "--assume-yes-for-downloads",
        "--remove-output",
        "main.py",
    ]

    print("\n[*] Ejecutando Nuitka...")
    print(f"    Comando: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)  # noqa: S603

    if result.returncode == 0:
        print("\n" + "=" * 70)
        print("  [OK] COMPILACION EXITOSA CON NUITKA")
        print("=" * 70)
        print(f"Distribución generada en: {output_dir / 'main.dist'}")
        print("Para probar la app, ejecuta: dist\\main.dist\\DariusAI.exe (o main.exe)")
    else:
        print(f"\n[!] Error durante la compilación. Código de salida: {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
