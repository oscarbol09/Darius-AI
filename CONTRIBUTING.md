# Contribución a Darius AI

Guía para colaborar en el desarrollo y mantenimiento de Darius AI.

---

## Requisitos del Entorno

- **Sistema Operativo:** Windows 10 (compilación 19041+) o Windows 11.
- **Python:** 3.11 o 3.12.
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

Antes de enviar un Pull Request o realizar un commit, asegúrate de que todas las pruebas pasen localmente y que el formateador no detecte inconsistencias:

```powershell
# Ejecutar suite de pruebas unitarias e integración (sin llamadas reales a APIs externas)
pytest tests/ -v -m "not live"

# Validar calidad y reglas de estilo con Ruff (debe retornar 0 errores)
ruff check .
```

---

## Estándares de Ingeniería y Arquitectura

- **Seguridad en Subprocesos:** Prohibido el uso de `shell=True` en `subprocess`. Todas las invocaciones a utilidades del sistema deben pasar listas de argumentos validadas (`windows_commands.py`).
- **Rendimiento Gráfico en GUI:** En el visualizador de audio o componentes de dibujo en Canvas, no uses `canvas.delete("all")` dentro de bucles de animación continua. Actualiza las coordenadas atómicamente con `canvas.coords()` para evitar parpadeos y pausas de recolección de basura.
- **Motor BYOK y Red:** Al añadir o modificar proveedores de IA en `ai_client.py`, utiliza interfaces compatibles con la API estándar de OpenAI basadas en `urllib` para mantener la base de dependencias ligera y portátil.
- **Manejo Estructurado de Errores:** Captura excepciones específicas y registra los diagnósticos con `log.warning` o `log.error`. No silencies errores con bloques `except: pass` vacíos.
- **Anotaciones de Tipo:** Incluye *type hints* en todas las funciones y métodos nuevos.
- **Convención de Commits:** Utiliza [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`) explicando el **porqué** del cambio en el cuerpo del mensaje.
