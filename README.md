# Darius AI

Asistente de escritorio por voz y automatización nativa para Windows con arquitectura BYOK (*Bring Your Own Key*), cerebro de memoria en Obsidian y renderizado visual a 60 FPS.

---

## ¿Por qué existe Darius AI?

La mayoría de asistentes virtuales dependen exclusivamente de servicios en la nube cerrados para cualquier tarea elemental, lo que genera latencia innecesaria, consumo constante de cuota y fallos al perder conexión.

Darius AI se basa en dos pilares de ingeniería:

1. **Localidad primero:** Los comandos del sistema operativo (abrir aplicaciones, ajustar volumen, consultar diagnósticos de red, escribir notas diarias o buscar en tu historial) se resuelven **100% en local** en milisegundos a través de las APIs de Windows, PowerShell y tu bóveda de **Obsidian**, sin enviar tráfico a internet.
2. **Libertad de modelo (BYOK):** Para consultas abiertas y razonamiento en lenguaje natural, puedes conectar el proveedor de IA que prefieras (Google Gemini, OpenAI / ChatGPT, OpenRouter, NVIDIA NIM, Groq o instancias locales de **Ollama** sin costo alguno ni salida a internet).

---

- **Disparador Acústico por Doble Aplauso:**
  - Detección en tiempo real de picos acústicos transitorios (aplausos) sobre streaming PCM con `sounddevice` y `numpy`.
  - Piso de ruido adaptativo exponencial que ajusta el umbral automáticamente al entorno sonoro.
  - Auto-sondeo inteligente de micrófonos (`probe_best_input_device`): detecta si el micro predeterminado está mudo (RMS < 0.001) y conmuta al dispositivo activo óptimo.
- **Gestión Multi-Monitor Win32 y Rutinas de Espacio de Trabajo:**
  - Descubrimiento nativo de pantallas vía `EnumDisplayMonitors` y `GetMonitorInfoW`.
  - Colocación y ajuste de navegadores y ventanas en monitores específicos (`snap_window_to_monitor`).
  - Enfoque nativo de IDEs (`Cursor.exe`, `Code.exe`) mediante `AttachThreadInput` y `SetForegroundWindow` para evitar procesos duplicados.
  - Rutinas automatizadas: **"Protocolo Darius"** (preparación y bienvenida completa), **"Modo Desarrollo"** (IDE monitor 1 + Docs monitor 2) y **"Modo Trading"** (TradingView + Finviz/Binance).
- **Motor TTS ElevenLabs y Configuración Gráfica Total:**
  - Síntesis neural de alta fidelidad con streaming PCM 24kHz y fallback a REST.
  - Almacenamiento local en disco (`audio_cache/`) indexado por hash SHA-256: las frases de estado y saludos recurrentes se reproducen al instante (0 ms de latencia) y con 0 consumo de cuota de API.
  - Despachador multi-motor dinámico: ElevenLabs > Edge-TTS > SAPI5 local (SAPI5 funciona offline sin configuración previa).
- **Modal Gráfico Dual de Configuración (`⚙ Configuración`):**
  - **Pestaña 1 (Modelo de IA - BYOK):** Soporte para 7 motores (Gemini, OpenAI, Groq, NVIDIA NIM, OpenRouter, Ollama, Personalizado) con ping de latencia en vivo.
  - **Pestaña 2 (Voz y Síntesis - TTS):** Selección de motor (SAPI5, Edge-TTS, ElevenLabs), campo de API Key enmascarado con alternador `👁`, catálogo de voces (Adam, Rachel, Antoni, etc.), modelo neural, alternador de caché local y botón de prueba auditiva en vivo (`🔊 PROBAR VOZ`).
  - Cero necesidad de editar archivos `.env` o JSON manualmente: todo se gestiona y persiste desde la interfaz visual.
- **Empaquetado Nativo `.EXE` para Usuarios Finales:**
  - Compilación nativa en C con **Nuitka** (0 dependencias de Python para el usuario final, 0 falsos positivos de antivirus).
  - Instalador ligero con **Inno Setup** que instala en el perfil del usuario (`%LOCALAPPDATA%`) sin requerir permisos de administrador.
  - Separación de datos: toda la persistencia mutable (`config.json`, logs, cachés) se aísla automáticamente en `%APPDATA%\DariusAI`.
- **Cerebro y Memoria en Bóveda de Obsidian:**
  - **Diario Personal:** Comandos de voz directos (*"Anota en mi diario que..."*) que registran entradas con marca de tiempo en la nota diaria (`Diario/YYYY-MM-DD.md`).
  - **Memorias Permanentes:** Almacena hechos, preferencias y datos de contexto (*"Recuerda que..."*) en archivos Markdown estructurados con frontmatter YAML (`Darius/Memorias/`).
  - **Inyección de Contexto:** El motor de IA recupera automáticamente fragmentos relevantes de tu bóveda para enriquecer las respuestas conversacionales.
- **Visualizador Vectorial a 60 FPS y Telemetría en Vivo:**
  - Onda sinusoidal armónica de 3 capas calculada con **NumPy** y proyectada sobre `tkinter.Canvas` atómico (0 flicker, <90 MB RAM).
  - Indicadores de telemetría en tiempo real: estado del micrófono, monitores detectados, motor TTS y botón de conmutación de aplausos.
- **Control por Voz y Modos de Activación:**
  - **Disparador Acústico:** Da dos aplausos seguidos para despertar al asistente inmediatamente.
  - **Push-to-Talk (PTT):** Mantén presionada una tecla (`Right Ctrl` por defecto) para hablar sin falsos positivos.
  - **Modo Nombre:** Escucha continua en segundo plano que se activa al detectar el nombre ("Darius").
  - **Modo Auto:** Procesa de forma inmediata cualquier frase capturada.

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

### 3. Iniciar el asistente y configurar tu proveedor e IA y Voz
```powershell
python main.py
```

Al abrir Darius AI:
1. Haz clic en el botón **⚙ Configuración** en la esquina superior derecha.
2. **Pestaña 🤖 Modelo de IA (BYOK):**
   - Selecciona tu proveedor preferido (**Gemini**, **OpenAI**, **Groq**, **NVIDIA NIM**, **OpenRouter**, **Ollama** o **Personalizado**).
   - Introduce tu clave de API (no requerida para Ollama) y presiona **Probar Conexión** para medir la latencia.
3. **Pestaña 🔊 Voz y Síntesis (TTS):**
   - Selecciona el motor (**SAPI5 nativo offline**, **Edge-TTS neural**, o **ElevenLabs**).
   - Si eliges ElevenLabs, ingresa tu API Key, selecciona tu voz favorita (Adam, Rachel, Antoni, etc.) y prueba el audio en vivo con **🔊 Probar Voz**.
4. Haz clic en **Guardar** para aplicar los cambios de inmediato.

---

## Compilación y Empaquetado a Binario Standalone (.EXE)

Darius AI cuenta con un sistema de compilación automatizado a C nativo mediante **Nuitka**, lo que permite distribuirlo a usuarios que no tienen Python instalado:

```powershell
# 1. Instalar dependencias de compilación
pip install nuitka zstandard

# 2. Compilar binario nativo standalone
python build_nuitka.py
```

El script genera la carpeta `dist/DariusAI.dist/` que contiene `DariusAI.exe`, sus recursos y librerías DLL empaquetadas.

### Crear el Instalador de Windows (Inno Setup)
Si tienes instalado [Inno Setup 6](https://jrsoftware.org/isdl.php), compila el script para generar el instalador final:

```powershell
iscc installer.iss
```

Esto generará `Output/DariusAI-Setup-v7.0.0.exe`, un instalador ligero que se instala en el directorio de usuario (`%LOCALAPPDATA%\Programs\DariusAI`) sin solicitar permisos de administrador.

### 4. Configurar la Bóveda de Obsidian y Espacio de Trabajo (Opcional)

Puedes personalizar rutas y pantallas en `config.json`:

```json
{
  "obsidian": {
    "vault_path": "C:\\Ruta\\A\\Tu\\Obsidian Vault",
    "daily_notes_folder": "Diario",
    "memories_folder": "Darius/Memorias",
    "auto_inject_context": true
  },
  "tts": {
    "engine": "elevenlabs"
  },
  "elevenlabs": {
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "model_id": "eleven_multilingual_v2"
  },
  "acoustic_trigger": {
    "enabled": true,
    "clap_threshold_multiplier": 2.8
  }
}
```

> **Nota para el modo PTT:** La captura global de pulsaciones de teclado mediante la librería `keyboard` requiere ejecutar el terminal o script con **privilegios de administrador** en Windows.

---

## Proveedores LLM Compatibles (BYOK)

| Proveedor | Identificador | Modelo Predeterminado | Endpoint Base | Variable de Entorno |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini` | `gemini-3.6-flash` | Google GenAI SDK nativo | `GEMINI_API_KEY` |
| **OpenAI / ChatGPT** | `openai` | `gpt-4o-mini` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| **Groq Cloud** | `groq` | `llama-3.3-70b-versatile` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| **NVIDIA NIM** | `nvidia_nim` | `meta/llama-3.3-70b-instruct` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` |
| **OpenRouter** | `openrouter` | `deepseek/deepseek-r1:free` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| **Ollama (Local)** | `ollama` | `llama3.2` | `http://localhost:11434/v1` | *(No requerida)* |
| **Personalizado** | `custom` | *Configurable* | *Configurable* | *Vía modal o config.json* |

---

## Comandos de Voz y Rutinas de Automatización

| Comando de Voz | Acción Ejecutada | Módulo |
| :--- | :--- | :--- |
| **"Protocolo Darius"** / **"Modo Bienvenida"** | Maximiza IDE Cursor/Code en monitor 1, abre herramientas en monitor 2, ajusta audio y reproduce bienvenida | `workspace_manager.py` |
| **"Modo desarrollo"** / **"Modo programar"** | Enfoca Cursor/Code en monitor principal y abre documentación técnica en monitor secundario | `workspace_manager.py` |
| **"Modo trading"** / **"Modo finanzas"** | Abre TradingView y Finviz en monitores 1 y 2 para análisis de mercado | `workspace_manager.py` |
| **"¿Cuántos monitores tengo?"** | Consulta Win32 `EnumDisplayMonitors` y describe dimensiones, posición y monitor primario | `workspace_manager.py` |
| **"Organizar pantallas"** / **"Organizar ventanas"** | Distribuye las ventanas principales en cuadrícula según la topología multi-monitor | `workspace_manager.py` |
| **"Pantalla completa"** / **"F11"** | Envía tecla `F11` a la ventana activa mediante eventos de teclado de Windows | `workspace_manager.py` |
| **"Anota en mi diario que..."** | Inserta entrada con hora en la nota diaria (`Diario/YYYY-MM-DD.md`) de Obsidian | `obsidian_brain.py` |
| **"Recuerda que..."** | Almacena memoria permanente con tags y timestamp en `Darius/Memorias/` | `obsidian_brain.py` |
| **"Subir / Bajar volumen"** | Modifica el nivel de volumen maestro del endpoint de audio con PyCAW | `windows_commands.py` |
| **"Abrir [aplicación]"** | Búsqueda difusa y ejecución aislada (`shell=False`) de software instalado | `windows_commands.py` |

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
│   [Pill: Micro Calibrado]  [Pill: Monitores]  [Pill: TTS]  [Toggle: Clap]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                    DISPARADORES Y ENRUTADOR DE COMANDOS                     │
│  ┌──────────────────────┐  ┌───────────────────────┐  ┌──────────────────┐  │
│  │  Acoustic Trigger    │  │   Enrutador Local     │  │   Motor BYOK     │  │
│  │ (Doble Aplauso RMS)  │  │   (_CMD_PATTERNS)     │  │  (ai_client.py)  │  │
│  └──────────────────────┘  └───────────────────────┘  └──────────────────┘  │
│        Hilo streaming               Hilo principal             Hilo daemon  │
│      [sounddevice audio]       [dispatch de comandos]    [Gemini/OpenAI/Oll]│
├─────────────────────────────────────────────────────────────────────────────┤
│                    GESTIÓN DE ESPACIO DE TRABAJO Y TTS                      │
│   ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│   │    WorkspaceManager (Win32)       │  │   TTSWorker Multi-Motor       │  │
│   │  Multi-Monitor · Snap · Focus IDE │  │ ElevenLabs + DiskCache + SAPI │  │
│   └───────────────────────────────────┘  └───────────────────────────────┘  │
│         EnumDisplayMonitors / User32            audio_cache/ (SHA-256)      │
├─────────────────────────────────────────────────────────────────────────────┤
│                       CEREBRO Y MEMORIA LOCAL                               │
│                          obsidian_brain.py                                  │
│   ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│   │           Diario Local            │  │      Memorias Permanentes     │  │
│   │       Diario/YYYY-MM-DD.md        │  │      Darius/Memorias/*.md     │  │
│   └───────────────────────────────────┘  └───────────────────────────────┘  │
│              Bóveda local de Obsidian (Markdown + YAML Frontmatter)         │
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
