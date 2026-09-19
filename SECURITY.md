# Política de Seguridad

## Versiones Compatibles

| Versión | Estado de Soporte |
| :--- | :--- |
| 6.x | ✅ Desarrollo activo y soporte |
| < 6.0 | ❌ Sin soporte |

---

## Reporte de Vulnerabilidades

Darius AI es un asistente de escritorio de uso personal y local. Si descubres alguna vulnerabilidad de seguridad en el código o en sus dependencias, por favor abre un issue en el repositorio o contacta directamente al mantenedor.

**Por favor, no publiques información sensible (claves de API, tokens o rutas personales) en issues públicos.**

---

## Buenas Prácticas de Seguridad Implementadas

- **Gestión segura de secretos:** Las claves de API se cargan desde variables de entorno locales (`.env`), el cual se encuentra estrictamente excluido en `.gitignore`.
- **Arquitectura local-first:** Las notas, configuraciones y registros viven localmente en disco (bóveda de Obsidian y archivos JSON locales), sin transmisión involuntaria de datos a servidores de terceros.
- **Prevención de inyecciones de comandos:** Todas las llamadas a subprocesos (`subprocess.run`) se ejecutan con listas de argumentos validadas y `shell=False`.
- **Auditoría continua:** Se auditan vulnerabilidades de dependencias (`pip-audit`) y detección de secretos (`gitleaks`) en cada pipeline de CI.
