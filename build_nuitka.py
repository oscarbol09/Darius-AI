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
import subprocess
import sys
from pathlib import Path


def main():
    root_dir = Path(__file__).resolve().parent
    os.chdir(root_dir)

    print("=" * 70)
    print("  DARIUS AI — COMPILACIÓN NATIVA STANDALONE CON NUITKA (v7.0.0)")
    print("=" * 70)

    # 1. Asegurar icono
    icon_script = root_dir / "assets" / "generate_icon.py"
    icon_path = root_dir / "assets" / "darius.ico"
    if not icon_path.exists() and icon_script.exists():
        print("\n[*] Generando icono de la aplicación...")
        subprocess.run([sys.executable, str(icon_script)], check=True)  # noqa: S603

    # 2. Verificar dependencias de build
    print("\n[*] Verificando herramientas de compilación...")
    try:
        import nuitka  # noqa: F401
    except ImportError:
        print("[*] Instalando Nuitka y aceleradores (zstandard, ordered-set)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "nuitka>=2.4.0", "zstandard", "ordered-set"],
            check=True  # noqa: S603
        )

    # 3. Construir comando Nuitka
    output_dir = root_dir / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        "--include-package=customtkinter",
        "--include-package-data=customtkinter",
        "--include-package=speech_recognition",
        "--include-package-data=speech_recognition",
        "--include-data-files=config.json=config.json",
        "--include-data-files=assets/darius.ico=assets/darius.ico",
        f"--windows-icon-from-ico={icon_path}",
        "--windows-company-name=Oscar Bolano",
        "--windows-product-name=Darius AI",
        "--windows-file-version=7.0.0.0",
        "--windows-product-version=7.0.0.0",
        "--windows-file-description=Darius AI - Asistente de Escritorio y Automatizacion por Voz",
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
