"""Tests unitarios para obsidian_brain.py"""

import datetime
from pathlib import Path

from obsidian_brain import ObsidianBrain, _sanitize_filename


class TestSanitizeFilename:
    def test_removes_invalid_windows_characters(self):
        dirty = 'nota: con "caracteres" <ilegales> / y \\ barras | ? *'
        clean = _sanitize_filename(dirty)
        assert ":" not in clean
        assert '"' not in clean
        assert "<" not in clean
        assert ">" not in clean
        assert "/" not in clean
        assert "\\" not in clean
        assert "|" not in clean
        assert "?" not in clean
        assert "*" not in clean

    def test_handles_empty_string(self):
        clean = _sanitize_filename("")
        assert clean == "nota_sin_titulo"


class TestObsidianBrainOperations:
    def test_save_memory_creates_markdown_file(self, tmp_path: Path):
        brain = ObsidianBrain(vault_path=tmp_path)
        file_path = brain.save_memory(
            title="Proyecto Atlas",
            content="El proyecto principal vive en D:/Proyectos/Atlas.",
            category="proyecto",
            tags=["trabajo", "urgente"],
        )

        assert file_path.exists()
        assert file_path.name == "Proyecto Atlas.md"

        content = file_path.read_text(encoding="utf-8")
        assert "tipo: memoria" in content
        assert "categoria: proyecto" in content
        assert "darius" in content
        assert "trabajo" in content
        assert "# Proyecto Atlas" in content
        assert "El proyecto principal vive en D:/Proyectos/Atlas." in content

    def test_append_daily_note(self, tmp_path: Path):
        brain = ObsidianBrain(vault_path=tmp_path)
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        # Primera entrada crea el archivo con encabezado
        daily_file = brain.append_daily_note("Comencé a trabajar en el módulo de voz.")
        assert daily_file.exists()
        assert daily_file.name == f"{today_str}.md"

        content = daily_file.read_text(encoding="utf-8")
        assert f"# Diario — {today_str}" in content
        assert "Comencé a trabajar en el módulo de voz." in content

        # Segunda entrada agrega otra línea sin sobrescribir
        brain.append_daily_note("Finalicé la integración con Obsidian.")
        updated_content = daily_file.read_text(encoding="utf-8")
        assert "Comencé a trabajar en el módulo de voz." in updated_content
        assert "Finalicé la integración con Obsidian." in updated_content

    def test_search_vault(self, tmp_path: Path):
        brain = ObsidianBrain(vault_path=tmp_path)
        brain.save_memory("Python Tips", "Recuerda usar ruff para linting rápido.", category="desarrollo")
        brain.save_memory("Receta Pizza", "Harina, agua, levadura y tomate.", category="cocina")

        results = brain.search_vault("ruff linting")
        assert len(results) >= 1
        assert results[0]["title"] == "Python Tips"
        assert "ruff" in results[0]["snippet"]

    def test_get_memory_context(self, tmp_path: Path):
        brain = ObsidianBrain(vault_path=tmp_path)
        brain.save_memory("Clave Wifi", "La contraseña del router de casa es Secreta123.", category="red")

        context = brain.get_memory_context("contraseña wifi")
        assert "Clave Wifi" in context
        assert "Secreta123" in context
