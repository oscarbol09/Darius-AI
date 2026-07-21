# Contribuyendo a DARIUS AI

## Requisitos

- Python 3.11+
- Windows 10/11 (para el modo escritorio)
- Poetry o pip + venv

## Setup

```bash
git clone <repo>
cd Darius-AI
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Tests

```bash
pytest                          # unit tests
pytest -m windows               # solo tests de Windows
pytest --cov=. --cov-report=term  # con cobertura
```

## Estilo

- Ruff para linting y formato (`ruff check . && ruff format . --check`)
- Type hints en todas las funciones nuevas
- Nombres de variables en inglés (comentarios en español)
- No `shell=True` en subprocess
- Errores con `log.warning`, nunca silenciar excepciones

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: nueva funcionalidad
fix: corrección de bug
refactor: cambio de estructura sin cambio funcional
test: agregar o modificar tests
docs: cambios en documentación
chore: herramienta, CI, dependencias
```

## PRs

1. Branch descriptivo: `feature/nombre`, `fix/nombre`
2. Incluye tests cuando sea posible
3. Todos los tests deben pasar antes del merge
4. Sin regresiones de cobertura
