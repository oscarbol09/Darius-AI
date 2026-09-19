# Darius AI

Asistente de escritorio por voz y automatización nativa para Windows con arquitectura BYOK (*Bring Your Own Key*), cerebro de memoria en Obsidian y renderizado visual a 60 FPS.

---

## ¿Por qué existe Darius AI?

La mayoría de asistentes virtuales dependen exclusivamente de servicios en la nube cerrados para cualquier tarea elemental, lo que genera latencia innecesaria, consumo constante de cuota y fallos al perder conexión.

Darius AI se basa en dos pilares de ingeniería:

1. **Localidad primero:** Los comandos del sistema operativo (abrir aplicaciones, ajustar volumen, consultar diagnósticos de red, escribir notas diarias o buscar en tu historial) se resuelven **100% en local** en milisegundos a través de las APIs de Windows, PowerShell y tu bóveda de **Obsidian**, sin enviar tráfico a internet.
2. **Libertad de modelo (BYOK):** Para consultas abiertas y razonamiento en lenguaje natural, puedes conectar el proveedor de IA que prefieras (Google Gemini, OpenAI / ChatGPT, OpenRouter, NVIDIA NIM, Groq o instancias locales de **Ollama** sin costo alguno ni salida a internet).

---

## Características Principales

- **Arquitectura BYOK Multi-Proveedor:**
  - Soporte nativo y compatible para 7 motores: **Google Gemini**, **OpenAI / ChatGPT**, **OpenRouter**, **NVIDIA NIM**, **Groq Cloud**, **Ollama** (ejecución local en `http://localhost:11434/v1`) y cualquier endpoint compatible con el protocolo OpenAI.
  - Modal gráfico de configuración (`⚙`) con selector de modelo, edición de URL base, campo de clave de API enmascarada y prueba de conexión en tiempo real con medición de latencia en milisegundos.
  - Resolución jerárquica de credenciales: Configuración en GUI (`config.json`) > Variables de entorno (`.env`) > Valores por defecto.
- **Cerebro y Memoria en Bóveda de Obsidian:**
  - **Diario Personal:** Comandos de voz directos (*"Anota en mi diario que..."*) que registran entradas con marca de tiempo en la nota diaria (`Diario/YYYY-MM-DD.md`).
  - **Memorias Permanentes:** Almacena hechos, preferencias y datos de contexto (*"Recuerda que..."*) en archivos Markdown estructurados con frontmatter YAML (`Darius/Memorias/`).
  - **Inyección de Contexto:** El motor de IA recupera automáticamente fragmentos relevantes de tu bóveda para enriquecer las respuestas conversacionales.
- **Visualizador Vectorial a 60 FPS:**
  - Onda sinusoidal armónica de 3 capas calculada matemáticamente con **NumPy** y proyectada sobre `tkinter.Canvas`.
  - Actualización atómica de coordenadas sin llamadas a `delete("all")`, eliminando parpadeos (*flicker*) y pausas por recolección de basura.
  - Transición fluida entre estado inactivo (*breathing animation*) y modulación reactiva durante el habla.
- **Control por Voz y Modos de Activación:**
  - **Push-to-Talk (PTT):** Mantén presionada una tecla (`Right Ctrl` por defecto) para hablar sin falsos positivos de captura.
  - **Modo Nombre:** Escucha continua en segundo plano que se activa al detectar el nombre ("Darius" mediante coincidencia fonética difusa).
  - **Modo Auto:** Procesa de forma inmediata cualquier frase capturada.
  - **Síntesis de Voz Desacoplada (TTS):** Motor SAPI de Windows ejecutado en un worker COM dedicado con cola de mensajes para no bloquear la interfaz gráfica, con soporte alternativo para `edge-tts`.
- **Automatización del Sistema Operativo Windows:**
  - Enrutamiento seguro de comandos a paneles de configuración (`ms-settings:`), utilidades de administración (`mmc.exe`, `control.exe`) y scripts de PowerShell/CMD.
  - Control de hardware (volumen vía PyCAW Core Audio API, comprobaciones de conectividad, procesos).
  - Base de datos local de aplicaciones instaladas (`apps_cache.json`) con resolución difusa por nombre.
- **Resiliencia y Seguridad:**
  - Bloqueo por **Mutex Win32 nativo** que impide múltiples instancias simultáneas en memoria.
  - Subprocesos ejecutados exclusivamente con listas de argumentos validadas (`shell=False`), previniendo inyecciones de comandos.
  - Cadena de degradación defensiva (*fallback*) hacia modelos secundarios o gratuitos ante errores de cuota (HTTP 429) o fallos de proveedor.

---

## Requisitos del Sistema

- **Sistema Operativo:** Windows 10 (compilación 19041+) o Windows 11.
- **Python:** 3.11 o 3.12.
- **Audio:** Micrófono y altavoces/auriculares configurados como dispositivos predeterminados en Windows.
- **Obsidian (Opcional):** Si tienes una bóveda de Obsidian, Darius se integra directamente con tu estructura de carpetas.
- **Ollama (Opcional):** Si deseas ejecutar modelos 100% locales sin conexión ni consumo de API externa.

---

## Instalación y Puesta en Marcha

### 1. Clonar el repositorio y preparar el entorno

```powershell
git clone https://github.com/oscarbol09/Darius-AI.git
cd Darius-AI

python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 3. Iniciar el asistente y configurar tu proveedor (BYOK)

```powershell
python main.py
```

Al abrir Darius AI:
1. Haz clic en el botón **⚙ Configuración** en la esquina superior derecha.
2. Selecciona tu proveedor preferido (**Gemini**, **OpenAI**, **Groq**, **NVIDIA NIM**, **OpenRouter**, **Ollama** o **Personalizado**).
3. Introduce tu clave de API (para Ollama no es necesaria) o personaliza la URL base y el modelo.
4. Presiona **Probar Conexión** para verificar el estado y la latencia.
5. Haz clic en **Guardar**.

Alternativamente, puedes configurar tus claves en un archivo `.env`:

```powershell
Copy-Item .env.example .env
```

```env
GEMINI_API_KEY=tu_clave_de_google_ai_studio
OPENAI_API_KEY=tu_clave_de_openai
GROQ_API_KEY=tu_clave_de_groq
NVIDIA_API_KEY=tu_clave_de_nvidia_nim
OPENROUTER_API_KEY=tu_clave_de_openrouter
```

### 4. Configurar la Bóveda de Obsidian (Opcional)

Puedes especificar la ruta de tu bóveda en `config.json`:

```json
"obsidian": {
  "vault_path": "C:\\Ruta\\A\\Tu\\Obsidian Vault",
  "daily_notes_folder": "Diario",
  "memories_folder": "Darius/Memorias",
  "auto_inject_context": true
}
```

> **Nota para el modo PTT:** La captura global de pulsaciones de teclado mediante la librería `keyboard` requiere ejecutar el terminal o script con **privilegios de administrador** en Windows.

---

## Proveedores LLM Compatibles (BYOK)

| Proveedor | Identificador | Modelo Predeterminado | Endpoint Base | Variable de Entorno |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini` | `gemini-2.5-flash` | Google GenAI SDK nativo | `GEMINI_API_KEY` |
| **OpenAI / ChatGPT** | `openai` | `gpt-4o-mini` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| **Groq Cloud** | `groq` | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| **NVIDIA NIM** | `nvidia_nim` | `meta/llama-3.3-70b-instruct` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` |
| **OpenRouter** | `openrouter` | `deepseek/deepseek-r1:free` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| **Ollama (Local)** | `ollama` | `llama3.2` | `http://localhost:11434/v1` | *(No requerida)* |
| **Personalizado** | `custom` | *Configurable* | *Configurable* | *Vía modal o config.json* |

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CAPA DE PRESENTACIÓN (GUI)                            │
│           CustomTkinter · Tema Slate/Zinc · Soporte High-DPI Windows        │
│   ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│   │     HighPerfWaveVisualizer        │  │      BYOKSettingsModal        │  │
│   │  NumPy 60 FPS · Canvas Atómico    │  │  Configuración y Ping en Vivo │  │
│   └───────────────────────────────────┘  └───────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                          NÚCLEO Y ENRUTADOR                                 │
│  ┌──────────────────────┐  ┌───────────────────────┐  ┌──────────────────┐  │
│  │   Motor de Audio     │  │   Enrutador Local     │  │   Motor BYOK     │  │
│  │  (STT + SAPI COM)    │  │   (_CMD_PATTERNS)     │  │  (ai_client.py)  │  │
│  └──────────────────────┘  └───────────────────────┘  └──────────────────┘  │
│        Hilos daemon             Hilo principal             Hilo daemon      │
│   [tts-worker] [stt-worker]   [dispatch de comandos]    [Gemini/OpenAI/Oll] │
├─────────────────────────────────────────────────────────────────────────────┤
│                       CEREBRO Y MEMORIA LOCAL                               │
│                          obsidian_brain.py                                  │
│   ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│   │           Diario Local            │  │      Memorias Permanentes     │  │
│   │       Diario/YYYY-MM-DD.md        │  │      Darius/Memorias/*.md     │  │
│   └───────────────────────────────────┘  └───────────────────────────────┘  │
│              Bóveda local de Obsidian (Markdown + YAML Frontmatter)         │
├─────────────────────────────────────────────────────────────────────────────┤
│                   ABSTRACCIÓN DEL SISTEMA OPERATIVO                         │
│                          windows_commands.py                                │
│   ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│   │      Paneles y URIs Win32         │  │    Subprocesos Controlados    │  │
│   │     ms-settings: · control.exe    │  │     PowerShell / CMD Lists    │  │
│   └───────────────────────────────────┘  └───────────────────────────────┘  │
│            os.startfile · subprocess (shell=False) · PyCAW Audio            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Decisiones de Diseño

- **¿Por qué Canvas + NumPy para la animación en lugar de un WebView?** Un WebView o Electron añadiría cientos de megabytes de sobrecarga en memoria. El visualizador vectorial con NumPy calcula armónicos matemáticos en microsegundos y actualiza las coordenadas de Canvas atómicamente, manteniendo el consumo total de la aplicación por debajo de 90 MB de RAM a 60 FPS constantes.
- **¿Por qué una interfaz compatible con OpenAI en el cliente BYOK?** La especificación de API de OpenAI se ha convertido en el estándar de la industria. Al implementar un llamador universal en `ai_client.py` con `urllib`, Darius puede comunicarse con OpenAI, Groq, NVIDIA NIM, OpenRouter, vLLM, LocalAI y Ollama sin requerir SDKs pesados de terceros.
- **¿Por qué Obsidian en Markdown plano?** Los archivos Markdown son portables, legibles directamente por el usuario, inmunes a bloqueos de proveedores y editables con cualquier herramienta de texto.
- **¿Por qué llamadas a subprocesos sin `shell=True`?** Para evitar vulnerabilidades de inyección de comandos al procesar nombres de archivos o argumentos capturados por voz.

---

## Limitaciones Conocidas y Trade-offs

- **Exclusivo para Windows:** El asistente utiliza enlaces directos a APIs de Windows (`pywin32`, `SAPI.SpVoice`, `win32event.CreateMutex`, `PyCAW`, `ctypes.windll`). No está diseñado para funcionar en Linux ni macOS.
- **Privilegios de Administrador para PTT:** El modo Push-to-Talk utiliza el hook global de bajo nivel de la librería `keyboard`, el cual requiere elevación de permisos en Windows para capturar teclas fuera del foco de la ventana.
- **Requisito de Servicio para Ollama:** Para utilizar modelos locales mediante Ollama, el servicio debe estar en ejecución previamente en el sistema (`ollama serve` o la aplicación de bandeja del sistema).

---

## Desarrollo y Pruebas

Para ejecutar la suite de pruebas automatizadas:

```powershell
pip install -r requirements-dev.txt

# Ejecutar suite de pruebas unitarias e integración (sin llamadas de red externas)
pytest tests/ -v -m "not live"

# Validar estándares y calidad de código con Ruff
ruff check .
```

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [SECURITY.md](SECURITY.md) para más información sobre el tratamiento de claves y políticas de seguridad.
