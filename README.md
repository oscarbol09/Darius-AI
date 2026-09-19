# Darius AI

Asistente virtual de escritorio nativo para Windows con control por voz, ejecución local de comandos del sistema y razonamiento conversacional con Google Gemini.

---

## ¿Por qué existe Darius AI?

La mayoría de asistentes virtuales dependen por completo de APIs en la nube para cualquier interacción, lo que introduce latencia innecesaria, consumo constante de cuota y fallos cuando no hay conexión.

Darius AI se diseñó con una premisa clara: **localidad primero**. 
- Si pides abrir una aplicación, cambiar el volumen, verificar la red o apagar la pantalla, se ejecuta **100% en local** en milisegundos mediante APIs de Windows, PowerShell y subprocesos controlados, sin tocar internet.
- Si haces una pregunta abierta o requieres razonamiento en lenguaje natural, la consulta se envía a **Google Gemini 2.5 Flash** (con fallback automático a **OpenRouter** si hay límites de cuota).

---

## Características

- **Control por voz nativo:** Reconocimiento de voz (STT) con calibración automática de ruido y síntesis de voz (TTS) mediante SAPI de Windows y soporte para Edge-TTS.
- **Modos de activación flexibles:**
  - **Push-to-Talk (PTT):** Mantén presionada una tecla (`Right Ctrl` por defecto) para grabar y procesar sin falsos positivos.
  - **Modo Nombre:** Escucha continua en segundo plano que se activa al detectar el nombre ("Darius" con fuzzy matching fonético).
  - **Modo Auto:** Procesa cada frase detectada de forma inmediata.
- **Automatización de Windows:** Catálogo extensible de comandos (`windows_commands.py`) para lanzar paneles de configuración (`ms-settings:`), ejecutar scripts de PowerShell/CMD y gestionar hardware (volumen vía PyCAW, diagnósticos de red, etc.).
- **Degradación elegante:** Si la API de Gemini devuelve error 429 o no hay internet, el asistente mantiene todas sus capacidades locales activas y proporciona retroalimentación verbal clara.
- **Instancia única garantizada:** Bloqueo por Mutex Win32 nativo para evitar múltiples procesos simultáneos.
- **Interfaz ligera y moderna:** Construida en **CustomTkinter** con tema oscuro nativo, visualizador de onda por Canvas e indicador de estado en tiempo real.
- **Sincronización opcional:** Integración con Supabase para respaldo de historial de chat y configuración en la nube (funciona 100% offline si no está configurado).

---

## Requisitos del Sistema

- **Sistema Operativo:** Windows 10 (compilación 19041+) o Windows 11.
- **Python:** 3.11 o superior.
- **Micrófono:** Cualquier dispositivo de entrada de audio reconocido por Windows.
- **Conectividad:** Requerida únicamente para reconocimiento de voz (Google STT) y consultas a Gemini/OpenRouter.

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

### 3. Configurar variables de entorno

Copia el archivo de ejemplo y agrega tus credenciales:

```powershell
Copy-Item .env.example .env
```

Edita `.env` con tus claves de API:

```env
GEMINI_API_KEY=tu_api_key_de_google_ai_studio
OPENROUTER_API_KEY=tu_api_key_opcional_de_openrouter
SUPABASE_URL=tu_url_opcional_de_supabase
SUPABASE_KEY=tu_anon_key_opcional_de_supabase
```

### 4. Iniciar el asistente

```powershell
python main.py
```

> **Nota para modo PTT:** La captura global de teclado con la librería `keyboard` requiere ejecutar el terminal o script con **privilegios de administrador** en Windows.

---

## Arquitectura y Decisiones de Diseño

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN (UI)                    │
│          CustomTkinter · Canvas · Indicador de Estado           │
│   DariusFinal(ctk.CTk) — hilo principal del event loop de Tk    │
├─────────────────────────────────────────────────────────────────┤
│                    NÚCLEO DE APLICACIÓN                         │
│  ┌───────────────────┐   ┌──────────────────┐   ┌───────────┐  │
│  │   Speech Engine   │   │  Command Router  │   │  Gemini   │  │
│  │  (STT + SAPI TTS) │   │  (_CMD_PATTERNS) │   │  Client   │  │
│  └───────────────────┘   └──────────────────┘   └───────────┘  │
│       Hilos daemon            Hilo principal          Hilo      │
│  [tts-worker] [audio-monitor] [main/ptt/wake-word]  [gemini]    │
├─────────────────────────────────────────────────────────────────┤
│             CAPA DE ABSTRACCIÓN DEL SISTEMA OPERATIVO           │
│                      windows_commands.py                        │
│   ┌────────────────────────┐   ┌──────────────────────────┐     │
│   │  WINDOWS_COMMANDS      │   │  SYSTEM_ACTIONS          │     │
│   │  Tipo A — URIs/Paneles │   │  Tipo B — Subprocesos    │     │
│   └────────────────────────┘   └──────────────────────────┘     │
│           os.startfile · subprocess · PowerShell · CMD          │
└─────────────────────────────────────────────────────────────────┘
```

- **¿Por qué CustomTkinter y no Electron?** Se buscaba una aplicación con consumo mínimo de RAM (<100MB frente a los 300MB+ de Electron), arranque instantáneo y dependencias puras en Python.
- **¿Por qué SAPI / pywin32 para TTS?** Proporciona síntesis de voz sin latencia de red utilizando las voces del sistema operativo, con un worker desacoplado en cola de subproceso para no congelar la UI.
- **Seguridad en subprocesos:** No se utiliza `shell=True` en la ejecución de comandos para evitar vulnerabilidades de inyección; todos los subprocesos pasan por listas de argumentos validadas.

---

## Limitaciones Conocidas y Trade-offs

- **Plataforma exclusiva:** El asistente está estrechamente acoplado a las APIs de Windows (Win32 API, SAPI, registro de Windows, Core Audio API); no es compatible con Linux ni macOS.
- **Permisos elevados para PTT:** La interceptación de eventos globales de teclado requiere elevación de permisos en Windows. Si no se ejecuta como administrador, el modo PTT notificará la restricción.
- **Calidad de voces SAPI:** La naturalidad de la voz local depende de los paquetes de idioma instalados en Windows. Para voces neurales de mayor fidelidad se incluye el módulo `edge_tts_engine.py`.

---

## Desarrollo y Pruebas

Para ejecutar la suite de pruebas automatizadas:

```powershell
pip install -r requirements-dev.txt

# Ejecutar suite de pruebas completa
pytest tests/ -v -m "not live"

# Validar formato y calidad de código
ruff check .
```

---

## Licencia

Este proyecto está disponible bajo la licencia MIT. Consulta el archivo [SECURITY.md](SECURITY.md) para más detalles sobre políticas de seguridad.
