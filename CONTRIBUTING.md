# Contribución a Darius AI

Guía rápida para colaborar en el desarrollo de Darius AI.

---

## Requisitos de Entorno

- **Sistema Operativo:** Windows 10 / Windows 11
- **Python:** 3.11+
- **Git**

---

## Configuración del Entorno de Desarrollo

```powershell
git clone https://github.com/oscarbol09/Darius-AI.git
cd Darius-AI

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## Pruebas y Validación de Código

Antes de enviar un Pull Request o hacer un commit, asegúrate de que todas las pruebas pasen y que no haya errores de formato:

```powershell
# Ejecución de pruebas unitarias
pytest tests/ -v -m "not live"

# Validación con linter Ruff (debe dar 0 errores)
ruff check .
```

---

## Estándares de Código

- **Seguridad en subprocesos:** No uses `shell=True` en llamadas a `subprocess`. Pasa siempre los argumentos como listas.
- **Manejo de errores:** Captura excepciones específicas y registra los errores con `logging` (`log.warning` / `log.error`). No uses `except: pass` silencioso.
- **Tipado:** Agrega anotaciones de tipo (`type hints`) en funciones nuevas o modificadas.
- **Commits:** Sigue el estándar de [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
