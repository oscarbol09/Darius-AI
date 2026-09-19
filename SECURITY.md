# Política de Seguridad

## Versiones Compatibles

| Versión | Estado de Soporte |
| :--- | :--- |
| **6.x** | ✅ Desarrollo activo y soporte de seguridad |
| **< 6.0** | ❌ Sin soporte |

---

## Reporte de Vulnerabilidades

Darius AI es un asistente de escritorio de ejecución local para Windows. Si descubres alguna vulnerabilidad en el código, en el tratamiento de credenciales o en las dependencias:

1. Por favor, **no publiques detalles sensibles en issues públicos**.
2. Abre un reporte de seguridad privado en GitHub o contacta directamente al mantenedor del repositorio.
3. Se revisará el informe para emitir una corrección a la brevedad.

---

## Medidas y Buenas Prácticas de Seguridad Implementadas

- **Gestión Segura de Credenciales BYOK:** Las claves de API se almacenan localmente en `config.json` o en variables de entorno `.env` (ambos excluidos en `.gitignore`). En la interfaz gráfica (`byok_settings.py`), las claves permanecen enmascaradas con caracteres ocultos (`●`) y solo se revelan mediante interacción explícita del usuario.
- **Arquitectura Local-First y Privacidad:** Las notas del diario, las memorias permanentes y las configuraciones residen íntegramente en disco local (bóveda de Obsidian y archivos de configuración locales), sin telemetría ni transmisión de datos a servidores no solicitados.
- **Prevención de Inyección de Comandos:** Todas las invocaciones al sistema operativo (`windows_commands.py`) se ejecutan con `shell=False` utilizando listas de argumentos validadas y rutas completas a utilidades del sistema (`%SystemRoot%\System32`).
- **Aislamiento de Procesos:** Bloqueo por Mutex Win32 nativo para impedir la ejecución concurrente de múltiples instancias que puedan colisionar en el uso de hardware de audio o archivos de estado.
- **Auditoría Automatizada en CI:** Cada cambio en el repositorio es auditado automáticamente mediante escaneo estático de secretos (**Gitleaks**) y análisis de vulnerabilidades en dependencias (**pip-audit**).
