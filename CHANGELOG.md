# Changelog

## [8.5.0] - 2026-10-13 — Situational Intelligence, Orbital Radar & ADS-B Edition

### Agregado
- **Radar Orbital y Rastreo de la ISS (`orbital_radar.py`):**
  - Rastreo cinemático en tiempo real de la Estación Espacial Internacional (ISS) consumiendo la API abierta Open-Notify con degradación graciosa y telemetría Kepleriana simulada en offline.
  - Validación perimetral Anti-SSRF obligatoria mediante `AntiSSRFValidator.is_safe_url()`.
  - Cálculo de distancia geodésica esférica (fórmula de Haversine) y marcación azimutal respecto a las coordenadas del usuario/observador.
  - Caché en memoria con TTL de 5 segundos para prevenir saturación de peticiones.
  - Alocución vocal táctica de Darius (*"Señor, la Estación Espacial Internacional se encuentra actualmente sobrevolando [lat, lon] a 420 km de altitud desplazándose a 27,600 km/h..."*).
  - Cobertura de pruebas unitarias al 95% (`tests/test_orbital_radar.py`, 20 pruebas).
- **Centinela de Tráfico Aéreo y Transpondedores ADS-B (`air_traffic_sentinel.py`):**
  - Radar aéreo multi-proveedor con integración primaria a OpenSky Network REST API (`/api/states/all`) con bounding box geográfico y conmutación automática de respaldo a adsb.lol radius point API (`/v2/lat/{}/lon/{}/dist/{}`).
  - Extracción y normalización de contactos aéreos: indicativo (*callsign*), país de origen, altitud barométrica, velocidad horizontal, rumbo y velocidad vertical.
  - Cálculo de distancia en kilómetros desde el observador, filtrado por radio táctico (`radius_km`) y ordenación de proximidad (aeronave más cercana primero).
  - Caché en memoria con TTL de 10 segundos contra rate-limiting.
  - Alocución vocal ejecutiva de Darius (*"Señor, el sensor ADS-B reporta N aeronaves en un radio táctico sobre su posición. La más próxima es el vuelo [callsign] a [dist] km..."*).
  - Cobertura de pruebas unitarias al 94% (`tests/test_air_traffic_sentinel.py`, 14 pruebas).
- **Sensor Sísmico y Tectónico Global (`seismic_sensor.py`):**
  - Monitor sísmico en tiempo real consumiendo los GeoJSON feeds oficiales del Servicio Geológico de Estados Unidos (USGS).
  - Filtrado por umbral de magnitud ($M \ge 4.5$ por defecto) y ordenación por recencia cronológica.
  - Detección automática y prioritaria de alertas activas de tsunami (`properties.tsunami == 1`).
  - Caché en memoria con TTL de 5 minutos (300 s).
  - Alocución vocal de alerta mayordomo (*"Reporte sísmico global, señor. En las últimas 24 horas se registraron N movimientos telúricos..."*).
  - Cobertura de pruebas unitarias al 93% (`tests/test_seismic_sensor.py`, 16 pruebas).
- **Oráculo de Clima Espacial y Tormentas Solares (`space_weather_oracle.py`):**
  - Monitor de índice Kp planetario y actividad geomagnética consumiendo los feeds en vivo del Centro de Predicción del Clima Espacial de NOAA (SWPC).
  - Clasificación determinista de escalas NOAA: G0 (Tranquilo/Nominal), G1 (Tormenta Menor), G2 (Tormenta Moderada), G3 (Tormenta Fuerte), G4 (Tormenta Severa) y G5 (Tormenta Extrema).
  - Evaluación de riesgo operativo sobre satélites orbitales y comunicaciones por radio.
  - Caché en memoria con TTL de 15 minutos (900 s) y fallback simulado para contingencia offline.
  - Cobertura de pruebas unitarias al 92% (`tests/test_space_weather_oracle.py`, 25 pruebas).
- **Telemetría Acústica Earcon y Sonar Ping (`sound_effects.py`):**
  - Incorporación del pulso acústico discreto Earcon de doble tono (880 Hz -> 1320 Hz) para telemetría sutil en segundo plano de Darius AI.
  - Generador procedural de Sonar Ping cibernético a 480 Hz con armónico a 960 Hz y decaimiento exponencial para barridos de radar táctico.
- **Integración en el Núcleo:**
  - `windows_commands.py`: 5 nuevas acciones de sistema registradas (`posicion_estacion_espacial`, `trafico_aereo_sobrevuelo`, `alerta_sismica_global`, `clima_espacial_solar`, `protocolo_ojo_de_dios`), alcanzando **71 acciones del SO**.
  - `agent_planner.py` y `agentic_bridge.py`: Herramientas 31 a 34 integradas (`track_orbital_iss`, `scan_overhead_air_traffic`, `check_seismic_activity`, `query_space_weather`).
  - `self_test.py`: Nueva suite de certificación hermética 12 `[PASS] SITUATIONAL INTELLIGENCE` validada en `python main.py --self-test`.
- **Métricas de la Suite de Pruebas:**
  - Suite de pruebas expandida a **884 pruebas pasando al 100%** (168 subpruebas, 9 omitidas, 0 fallos). Cobertura combinada en nuevos módulos al **94%**. Linter Ruff con **0 errores y 0 advertencias**.

## [8.4.0] - 2026-10-13 — Synapses, Tactical Timer, LIFO Dialogue & WOL Lockdown Edition

### Agregado
- **Motor de Temporizadores Tácticos Darius (`darius_timer.py`):**
  - Gestor multihilo de cuentas regresivas y alarmas con resolución milimétrica (<0.05s) en hilo daemon.
  - Creación, cancelación, consulta de tiempo restante y parada total (`create_timer`, `cancel_timer`, `get_remaining_seconds`, `stop_all`).
  - Alerta acústica procedural sincronizada al expirar (`play_target_lock` o tono de alerta) y alocución vocal estilizada de Darius (*"Disculpe la interrupción, señor. El temporizador de {label} ha concluido."*).
  - Cobertura de pruebas unitarias al 92% (`tests/test_darius_timer.py`, 19 pruebas).
- **Pila de Sub-Diálogos LIFO Darius (`dialogue_stack.py`):**
  - Autómata de pila pushdown (LIFO) para gestionar flujos interactivos multi-turno y solicitudes de confirmación sin romper el contexto principal.
  - Normalización fonético-textual estricta (remoción de diacríticos y tildes, limpieza de puntuación).
  - Fast-path nativo para pares afirmativos (`si`, `sí`, `claro`, `confirmo`, `adelante`, `procede`) y negativos (`no`, `cancela`, `espera`, `aborta`), tolerando lenguaje natural coloquial.
  - Expiración temporal automática por inactividad (`timeout_seconds`), desapilando marcos caducados y evitando diálogos congelados.
  - Cobertura de pruebas unitarias al 96% (`tests/test_dialogue_stack.py`, 18 pruebas).
- **Despachador Wake-on-LAN Multi-NIC (`wol_dispatcher.py`):**
  - Generador conforme a RFC del Magic Packet binario de 102 bytes exactos (`6x 0xFF + 16x MAC`).
  - Validación y normalización estricta de direcciones físicas MAC EUI-48, rechazando direcciones nulas, de difusión o multicast.
  - Descubrimiento de direcciones directed broadcast en todas las interfaces IPv4 activas de Windows (`psutil.net_if_addrs()` + `ipaddress.IPv4Interface`), resolviendo el problema de redes multi-NIC (Ethernet + Wi-Fi + Hyper-V).
  - Perfiles preconfigurados (`gaming_rig`, `nas`, `homelab`, `server`) y soporte para MAC directa.
  - Sincronización con efectos acústicos de Darius (`play_target_lock` -> `play_success_chime`) y alocución vocal de confirmación.
  - Cobertura de pruebas unitarias al 98% (`tests/test_wol_dispatcher.py`, 26 pruebas).
- **Protocolo de Silencio Táctico y Bloqueo de Emergencia Darius (`darius_lockdown.py`):**
  - Protocolo de seguridad bifásico:
    * **Nivel 1 (Silencio Táctico Inmediato, <15 ms)**: Purgado de cola `TTSWorker`, detención multimedia instantánea (`VK_MEDIA_STOP`) y silenciamiento del mezclador maestro (`VK_VOLUME_MUTE`).
    * **Nivel 2 (Protocolo Código Rojo / Lockdown Integral)**: Silencio táctico + checkpoints explícitos de bitácoras SQLite WAL (`PRAGMA wal_checkpoint(TRUNCATE)`) en `scheduler.db` y `approvals.db` + bloqueo nativo de sesión en Windows vía `user32.LockWorkStation()`.
  - Cobertura de pruebas unitarias al 100% (`tests/test_darius_lockdown.py`, 25 pruebas).
- **Integración en el Núcleo:**
  - `windows_commands.py`: 6 nuevas acciones de sistema registradas (`iniciar_temporizador`, `cancelar_temporizador`, `consultar_temporizador`, `encender_equipo_remoto`, `silencio_tactico`, `protocolo_codigo_rojo`), alcanzando **66 acciones del SO**.
  - `agent_planner.py` y `agentic_bridge.py`: Herramientas 27 a 30 integradas (`darius_timer`, `dialogue_stack`, `wake_on_lan`, `darius_lockdown`).
  - `self_test.py`: Nueva certificación hermética `[PASS] SYNAPSE & LOCKDOWN` validada en `python main.py --self-test`.
- **Métricas de la Suite de Pruebas:**
  - Suite de pruebas expandida a **802 pruebas pasando al 100%** (153 subpruebas, 9 omitidas, 0 fallos). Cobertura combinada en nuevos módulos al **97%**.

## [8.3.0] - 2026-10-13 — Multimodal, Biometric & Lexical Intelligence Edition

### Agregado
- **Centinela de Inteligencia de Noticias (`news_sentinel.py`):**
  - Motor asíncrono y resiliente de titulares con cascada de proveedores de degradación graciosa (NewsAPI -> feeds RSS sindicados -> DuckDuckGo News).
  - Filtrado categorial (`technology`, `science`, `business`, `world`, `general`).
  - Validación Anti-SSRF obligatoria mediante `AntiSSRFValidator` antes de cursar peticiones externas.
  - Caché en memoria con TTL de 15 minutos para prevenir saturación de ancho de banda y rate-limiting.
  - Generador de alocución vocal ejecutiva para mayordomo Darius (*"Señor, los principales titulares de tecnología son..."*).
  - Integración nativa con `DailyDigestEngine` para briefings matutinos.
  - Cobertura de pruebas unitarias al 85% (`tests/test_news_sentinel.py`, 16 pruebas).
- **Oráculo Léxico y Diccionario Bilingüe (`lexicon_oracle.py`):**
  - Motor de consulta terminológica y definiciones con arquitectura híbrida (local + nube).
  - Diccionario local curado bilingüe (español/inglés) enfocado en computación, IA, física y ciberseguridad.
  - Compatibilidad e ingestión opcional de corpus léxico masivo (`data.json`) en memoria.
  - Búsqueda difusa (*fuzzy matching*) con `difflib.get_close_matches` para tolerar errores fonéticos o tipográficos.
  - Conexión online de respaldo con validación Anti-SSRF para fonética IPA, sinónimos y antónimos.
  - Cobertura de pruebas unitarias al 95% (`tests/test_lexicon_oracle.py`, 28 pruebas).
- **Biometría Facial y Autenticación Sentry Darius (`face_biometrics.py`):**
  - `FaceBiometricsEngine`: Subsistema de verificación biométrica con tolerancia a entornos sin cámara (*soft-dependency*).
  - Corrección de la métrica de distancia de características LBPH, calibrando la confianza normalizada $[0.0, 1.0]$ y superando el bug histórico de porcentajes invertidos.
  - Arquitectura de 3 niveles (*3-Tier Fallback*):
    * Nivel 1: Verificación biométrica óptica desde stream de cámara web.
    * Nivel 2: Desafío vocal / PIN de contingencia en condiciones de baja luz o rostro desconocido.
    * Nivel 3: Modo pasivo / headless seguro sin bloqueos ni excepciones.
  - Alocución de bienvenida de Darius por reconocimiento de identidad (*"Identidad biométrica confirmada: señor. Protocolos de mando autorizados."*).
  - Integración con `webcam_sentinel.py` mediante verificación asíncrona no bloqueante al detectar llegada del usuario.
  - Cobertura de pruebas unitarias al 94% (`tests/test_face_biometrics.py`, 22 pruebas).
- **Extracción Visual OCR e Inteligencia de Pantalla (`visual_intel_ocr.py`):**
  - Pipeline de preprocesamiento de imagen: escala de grises, contraste adaptativo (CLAHE / autocontrast) y binarización con umbralización de Otsu.
  - Descubrimiento dinámico de motor OCR en cascada:
    * Nivel 1: Windows Native WinRT OCR (`Windows.Media.Ocr`).
    * Nivel 2: Tesseract OCR local auto-descubierto en `PATH` y directorios estándar de Windows.
    * Nivel 3: Fallback semántico multimodal LLM vía `ScreenVisionEngine`.
  - Soporte de captura para imágenes en archivo, regiones de pantalla específicas y portapapeles de Windows.
  - Extractor semántico de trazas de error (*stacktraces*), código fuente y URLs.
  - Cobertura de pruebas unitarias al 97% (`tests/test_visual_intel_ocr.py`, 49 pruebas).
- **Director Multimedia y Búsqueda en YouTube (`media_controller.py`):**
  - `clean_youtube_query`: Limpieza y extracción semántica de lenguaje natural en comandos de búsqueda musical.
  - `search_and_play_youtube`: Construcción segura de URLs con Anti-SSRF, apertura delegada en el navegador predeterminado del sistema (respetando la preferencia del usuario) y comando de auto-reproducción.
  - Cobertura de pruebas unitarias al 94% (`tests/test_media_controller.py`, 48 pruebas).
- **Integración en el Núcleo y Contratos del Sistema:**
  - `windows_commands.py`: 5 nuevas acciones de sistema registradas (`news_headlines`, `lexicon_lookup`, `youtube_search`, `ocr_screen`, `biometric_auth`), alcanzando 60 acciones totales.
  - `agent_planner.py` y `agentic_bridge.py`: Herramientas 22-26 integradas en la matriz de planificación y ejecución agéntica autónoma.
  - `daily_digest.py`: Métrica `top_headlines` agregada a `DigestMetrics`, alocución oral matutina y notas de Obsidian.
  - `self_test.py`: Nueva certificación hermética `[PASS] MULTIMODAL & BIOMETRIC` agregada y validada.
- **Métricas de la Suite de Pruebas:**
  - Suite de pruebas expandida a **713 pruebas pasando al 100%** (147 subpruebas, 0 fallos). Cobertura combinada en nuevos módulos superando el **92%**.

## [8.2.0] - 2026-10-13 — Darius Persona, Media Control, Science Oracle & Cyber Core HUD Edition

### Agregado
- **Personalidad Canónica Darius y Motor de Agudeza Británica (`darius_persona.py`):**
  - Personalidad de mayordomo técnico británico: cortesía inalterable, trato de honorífico *"señor"*, rigor técnico absoluto y tolerancia cero al cliché / *AI slop*.
  - `build_darius_system_prompt`: Generador de directivas de sistema tácticas inyectado en todos los proveedores de IA.
  - `get_witty_retort`: Motor de réplicas ingeniosas y secas (*dry British wit*) para chistes, existencialismo, identidad y bromas con latencia <1 ms.
  - `get_tactical_acknowledgment`: Confirmaciones operativas contextuales (*"A sus órdenes, señor"*, *"Protocolos en línea, señor"*, *"Telemetría estabilizada"*).
  - `format_butler_response`: Limpiador de *AI slop*, emojis y fórmulas serviles de chatbot genérico, adaptando las respuestas con cadencia digna para TTS.
  - Cobertura de pruebas unitarias al 89% (`tests/test_darius_persona.py`, 35 pruebas).
- **Oráculo Científico y Lookup Enciclopédico Rápido (`science_oracle.py`):**
  - `get_entity_summary`: Consulta de resúmenes enciclopédicos con latencia reducida vía Wikimedia REST API (<200 ms).
  - `get_constant_or_conversion`: Catálogo de 15 constantes físicas fundamentales (velocidad de la luz $c$, constante de Planck $h$, gravitacional $G$, masa del electrón, número de Avogadro, etc.) y 10 conversiones técnicas (Mach a km/h, eV a Joules, años luz, PSI a bar, nudos).
  - Síntesis de respuestas orales concisas (<2 oraciones) con tono sobrio de mayordomo.
  - Cobertura de pruebas unitarias al 100% (`tests/test_science_oracle.py`, 33 pruebas).
- **Control Multimedia Global Win32 (`media_controller.py`):**
  - `MediaController`: Despachador de Virtual Keys (VK) mediante `ctypes.windll.user32.keybd_event` para Spotify, YouTube, VLC y reproductores del sistema sin requerir foco de ventana (`play_pause`, `next_track`, `prev_track`, `stop`, `volume_up`, `volume_down`, `toggle_mute`).
  - Control de volumen maestro porcentual (0 a 100%) mediante pycaw con fallback robusto a PowerShell.
  - Extractor y limpiador de lenguaje natural `clean_media_query` para aislar artistas y títulos de canciones en comandos de voz.
  - Cobertura de pruebas unitarias al 93% (`tests/test_media_controller.py`, 34 pruebas).
- **Protocolo de Diagnóstico Integral Darius (`darius_protocol.py`):**
  - `DariusProtocolEngine`: Auditoría integral de hardware del sistema (CPU, RAM disponible, almacenamiento, batería / AC, enlace de red con latencia, geometría de monitores, dispositivos de audio y sincronización de Obsidian Vault).
  - Secuencia de audio procedural sincronizada (`play_scan_pulse`, `play_target_lock`, `play_success_chime`).
  - Generador de alocución vocal en español para síntesis TTS (*"Protocolo de Diagnóstico Integral Darius ejecutado con éxito, señor. Diagnóstico de sistemas al 100%..."*).
  - Cobertura de pruebas unitarias al 99% (`tests/test_darius_protocol.py`, 13 pruebas).
- **HUD Visualizador Cyber Core (`cyber_core_visualizer.py`):**
  - `CyberCoreVisualizer`: Renderizador vectorial de 60 FPS sobre `tk.Canvas` con geometría polar precomputada en NumPy.
  - Anillo exterior segmentado de 12 arcos en rotación horaria, escala táctica intermedia de 36 marcas en contrarrotación y núcleo central pulsante modulado por la energía acústica RMS.
  - Paleta cromática Cyber Core: Core Cyan (`#00F0FF`), Core Amber (`#E6AA38`), Core Crimson (`#C42B3B`) y Core Emerald (`#00FF88`).
  - Cobertura de pruebas unitarias al 100% (`tests/test_cyber_core_visualizer.py`, 14 pruebas).
- **Integración y Cableado en el Núcleo:**
  - `ai_client.py`: Inyección de `DariusPersona` en system prompt, fast-path para réplicas de humor con `get_witty_retort(fallback=False)` y saneamiento butler de respuestas del LLM.
  - `windows_commands.py`: Acciones de sistema registradas para reproducción, saltos de pista, volumen, protocolo Darius y réplicas de humor de Darius.
  - `agent_planner.py` y `agentic_bridge.py`: Herramientas de planificación y ejecución agéntica `media_action` / `media_control`, `science_oracle` y `darius_protocol`.
  - `self_test.py`: Nueva batería de verificación hermética `[PASS] DARIUS CORE & HUD` validada en `python main.py --self-test`.
- **Suite de Pruebas Unitarias:**
  - Suite de pruebas ampliada a **574 pruebas pasando al 100%** (142 subpruebas, 0 fallos). Cobertura total de los nuevos módulos al **97%**.

## [8.1.0] - 2026-10-13 — Full Agentic Perimeter, AST Sandbox, DAG & Deep Research Edition

### Agregado
- **Seguridad Perimetral y Anti-SSRF (`security_guard.py`):**
  - `AntiSSRFValidator`: Bloqueo determinista de subredes privadas RFC 1918, link-local, loopback, multicast, metadatos de nube (`169.254.169.254`, `metadata.google.internal`) y resolución DNS en política *fail-closed*. Normalización de direcciones IPv4 mapeadas y compatibles en IPv6.
  - `CredentialStripper`: Filtro y redactor de credenciales sensibles (claves de OpenAI, AWS, GitHub PATs, tokens de Slack, Bearer tokens, credenciales en URLs y bloques PEM de claves privadas RSA/EC).
  - `InjectionScanner`: Detección en 4 niveles de severidad (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) de intentos de override de instrucciones de sistema, secuestro de identidad (*jailbreak* / DAN), delimitadores maliciosos (`</im_start>`) e inyecciones de comandos en prompts.
  - Cobertura de pruebas unitarias al 100% (`tests/test_security_guard.py`).
- **Sandbox AST y Ejecución Segura de Python (`safe_code_interpreter.py`):**
  - `SafeCodeInterpreter`: Validador de Árbol de Sintaxis Abstracta (AST) que rechaza código antes de su ejecución.
  - Lista blanca estricta de módulos (`math`, `json`, `datetime`, `re`, `statistics`, `random`, `collections`, `itertools`, `decimal`).
  - Bloqueo absoluto de primitivas de introspección y escape (`eval`, `exec`, `compile`, `__import__`, `open`, `input`, `globals`, `locals`, `vars`, `getattr`, `setattr`, dunders y atributos privados `_`).
  - Captura aislada de `stdout`/`stderr`, límite de tiempo de ejecución y diccionario de estado persistente entre llamadas.
  - Cobertura de pruebas unitarias al 97% (`tests/test_safe_code_interpreter.py`).
- **Motor de Búsqueda Web Resiliente (`web_search_engine.py`):**
  - `WebSearchEngine`: Búsqueda multi-proveedor con fallback entre API JSON y scraping HTML de DuckDuckGo.
  - Validación anti-SSRF de todas las URLs de resultados antes de ser procesadas o devueltas.
  - Extracción limpia de snippets de texto, eliminación de etiquetas HTML y decodificación de entidades.
  - Caché LRU en memoria con TTL de 15 minutos (900s) y capacidad configurable para mitigar *rate-limiting*.
  - Cobertura de pruebas unitarias al 91% (`tests/test_web_search_engine.py`).
- **Motor de Grafos DAG para Flujos de Trabajo (`workflow_dag.py`):**
  - `WorkflowDAG`: Definición de nodos (`WorkflowNode`) y aristas (`WorkflowEdge`).
  - Detección de ciclos mediante DFS y ordenamiento topológico mediante el algoritmo de Kahn.
  - Cálculo de fases paralelas `execution_stages()` para orquestación óptima de nodos independientes.
  - Ejecución controlada con propagación segura de contexto y evaluación de condiciones de aristas sin `eval()`.
  - Cobertura de pruebas unitarias al 94% (`tests/test_workflow_dag.py`).
- **Agente Autónomo de Investigación Profunda (`deep_research_agent.py`):**
  - `DeepResearchAgent`: Deconstrucción automática de consultas en 2 a 3 subconsultas de búsqueda focalizadas.
  - Ejecución de búsquedas, deduplicación de fuentes por URL y extracción de citas bibliográficas `[1]`, `[2]`.
  - Síntesis de `ResearchBrief` con hallazgos clave, bibliografía y reporte estructurado en Markdown.
  - Cobertura de pruebas unitarias al 100% (`tests/test_deep_research.py`).
- **Gestión Dinámica de Perfil de Usuario y Memoria (`user_profile_engine.py`):**
  - `UserProfileEngine`: Persistencia thread-safe de perfil en formato Markdown (`USER.md` en Obsidian Vault `Darius/User_Profile.md` o ruta local).
  - Secciones canónicas: *Identidad y Rol*, *Preferencias y Estilo*, *Proyectos Activos*, *Stack Tecnológico*, *Restricciones y Hábitos*.
  - Extractor heurístico de hechos a partir del diálogo natural del usuario ("prefiero X", "mi proyecto es Y", "uso Python", "no me gusta Z").
  - Inyector dinámico de contexto compacto para prompts de sistema sin desperdicio de tokens.
  - Cobertura de pruebas unitarias al 100% (`tests/test_user_profile_engine.py`).
- **Integraciones en el Núcleo del Asistente:**
  - `agent_planner.py`: Incorporadas herramientas `safe_python_exec`, `user_profile`, `workflow_run`. Inyección perimetral de perfil de usuario en planes y sanitización automática de credenciales con `CredentialStripper`.
  - `agentic_bridge.py`: Sanitización de salidas con `CredentialStripper`, protección anti-SSRF en scraping y bloqueo de inyecciones de prompt.
  - `windows_commands.py`: Fast-paths de voz añadidos para *"perfil de usuario"* y *"auditoría de seguridad"*.
  - `self_test.py`: Agregado el contrato de diagnóstico `[PASS] AGENTIC & SECURITY`.
- **Suite de Pruebas Unitarias:**
  - Suite de pruebas ampliada de 317 a **442 pruebas pasando al 100%** (+125 pruebas nuevas en v8.1.0).

## [8.0.0] - 2026-10-13 — Proactivity, Safety & Autonomous Architecture Edition

### Agregado
- **Guardián Determinista Anti-Bucles y Compresión de Contexto (`loop_guard.py`):**
  - Detección basada en hash SHA-256 de llamadas a herramientas con límite de repetición configurable.
  - Algoritmo de detección de patrones oscilatorios (ping-pong) para ciclos de período 2 ($A \to B \to A \to B$) y período 3 ($A \to B \to C \to A \to B \to C$).
  - Mecanismo *warn-before-block* y compresión de contexto en 4 fases para proteger el límite de tokens.
  - Cobertura de pruebas unitarias al 96% (`tests/test_loop_guard.py`).
- **Almacén SQLite Human-in-the-Loop y Control por Tiers (`approval_store.py`):**
  - Base de datos SQLite en modo WAL (`approvals.db`) para registro de acciones pendientes y memoria de decisiones.
  - Clasificación de riesgo en 4 niveles: `TRIVIAL` (auto-aprobado), `LOW` (pregunta una vez y recuerda), `MEDIUM` (configurable) y `HIGH` (siempre exige confirmación).
  - Parser NLP y de lenguaje vocal (`parse_approval_response`) capaz de procesar respuestas naturales (*"sí"*, *"aprobar"*, *"siempre permitir"*, *"rechazar"*) con asignación de IDs de acción.
  - Cobertura de pruebas unitarias al 95% (`tests/test_approval_store.py`).
- **Enrutador Multidimensional de Complejidad y Presupuesto de Tokens (`complexity_router.py`):**
  - Análisis de consultas en 5 dimensiones ponderadas (longitud, código/dominio, razonamiento, estructura y tono creativo).
  - Asignación determinista a 5 niveles de complejidad (`TRIVIAL`, `SIMPLE`, `MODERATE`, `COMPLEX`, `VERY_COMPLEX`) y enrutamiento hacia modelos locales rápidos o modelos frontera.
  - Margen de presupuesto duplicado para modelos de razonamiento profundo (DeepSeek-R1, OpenAI o-series) para evitar asfixia de la cadena CoT.
  - Cobertura de pruebas unitarias al 87% (`tests/test_complexity_router.py`).
- **Programador Autónomo de Tareas en Segundo Plano (`task_scheduler.py`):**
  - Motor de ejecución de tareas programadas persistente en SQLite con soporte para tipos `ONCE` (marca temporal única), `INTERVAL` (segundos recurrentes) y `CRON`.
  - Hilo daemon ligero con ciclo de sondeo sin consumo apreciable de CPU.
  - Métodos completos de ciclo de vida: pausa, reanudación, cancelación y registro de logs de ejecución.
  - Cobertura de pruebas unitarias al 89% (`tests/test_task_scheduler.py`).
- **Motor de Resumen Ejecutivo Matutino (`daily_digest.py`):**
  - Agregación integral de métricas: telemetría del SO (RAM y disco), tareas pendientes y notas recientes de Obsidian, control de versiones Git y pronóstico del tiempo.
  - Síntesis de alocución vocal ejecutiva menor a 200 palabras, sin marcadores markdown, optimizada para síntesis verbal inmediata (TTS).
  - Guardado automatizado de notas formateadas en la bóveda de Obsidian (`Darius/Briefings/Briefing_YYYY-MM-DD.md`).
  - Activación por voz inmediata mediante *"Darius, resumen del día"* o *"buenos días darius"*.
  - Cobertura de pruebas unitarias al 80% (`tests/test_daily_digest.py`).
- **Registro Dinámico de Habilidades Procedimentales en Markdown (`skill_registry.py`):**
  - Descubrimiento y carga de habilidades tácticas desde archivos Markdown con Frontmatter YAML (compatibles con notas de Obsidian).
  - Inyección de playbooks procedimentales directamente en el planificador agéntico.
  - Cobertura de pruebas unitarias al 92% (`tests/test_skill_registry.py`).
- **Integración en el Planificador Agéntico (`agent_planner.py`):**
  - Nuevas herramientas disponibles en el catálogo agéntico: `daily_digest`, `schedule_task`, `check_complexity`, `execute_skill` y `approval_status`.
  - Protección activa con `LoopGuard` en el ciclo de ejecución de metas de `plan_and_execute`.
- **Certificación Hermética (`self_test.py`):**
  - Nuevo control `PROACTIVITY & SAFETY` en la suite de auto-certificación diagnóstica.
- **Suite de Pruebas Automáticas:**
  - Suite de pruebas unitarias ampliada de 289 a 317 pruebas pasando al 100%.

## [7.1.0] - 2026-10-11 — Tactical Intelligence & Perceptual Sentinel Edition


### Agregado
- **Motor de Efectos de Sonido Procedurales en Memoria (`sound_effects.py`):**
  - Síntesis matemática directa de formas de onda (senoidales, cuadradas, triangulares) con NumPy y envolventes suaves anti-clipping.
  - Catálogo de SFX de interfaz y HUD tácticos: `play_target_lock()`, `play_success_chime()`, `play_scan_pulse()`, `play_alert_tone()` y `play_click_tone()`.
  - Cero consumo de archivos en disco (0 KB), reproducción asíncrona no bloqueante y botón interactivo `🔊 SFX / 🔇 MUTE` en la GUI.
- **Motor de Dossiers de Inteligencia Estructurados (`target_dossier.py`):**
  - Generación automatizada de fichas analíticas sobre personas, empresas, tecnologías o proyectos con resumen ejecutivo, trayectoria, perfiles sociales verificados, *conversation hooks* y señales de riesgo (*risk flags*).
  - Persistencia estructurada en Obsidian Vault (`Darius/Dossiers/`) con Frontmatter YAML y callouts visuales de Markdown.
  - Soporte opcional para búsqueda neuronal con Exa API (`EXA_API_KEY`) y resúmenes concisos adaptados para lectura verbal fluida por TTS.
  - Nueva herramienta agéntica `target_dossier` integrada en el planificador autónomo (`agent_planner.py`).
- **Centinela de Presencia Humana y Visión Perceptual (`webcam_sentinel.py`):**
  - Monitoreo pasivo de presencia por webcam en segundo plano con control de FPS y consumo <1% CPU.
  - Detección de eventos: llegada del usuario (`on_user_arrived`), alejamiento prolongado (`on_user_left`) y alerta de hombro / espía (`on_shoulder_surfer`).
  - Máquina de estados con debounce de fotogramas y degradación elegante si no hay webcam o dependencias de OpenCV.
- **Rastreador de Telemetría Agéntica & Barra HUD (`telemetry_tracker.py` & `telemetry_bar.py`):**
  - Emisión de eventos agénticos en tiempo real con tiempos de ejecución en milisegundos (`@trace_step`).
  - Widget `TelemetryBarWidget` montado en el Command Dock de la GUI principal con ticker rotativo automático de actividades.
- **Tokens Tácticos Cyber / War Room en `gui_theme.py`:**
  - Nuevos tokens `ACCENT_TACTICAL_GREEN`, `BG_TACTICAL_DARK`, `BG_TACTICAL_PANEL` y `BORDER_TACTICAL`.
- **Suites de Pruebas Unitarias Robustas:**
  - `tests/test_sound_effects.py` (12 pruebas)
  - `tests/test_target_dossier.py` (7 pruebas)
  - `tests/test_webcam_sentinel.py` (5 pruebas)
  - `tests/test_telemetry_tracker.py` (5 pruebas)
  - `tests/test_telemetry_bar.py` (2 pruebas)
  - `tests/test_agent_planner.py` (4 pruebas actualizadas)
  - Total de pruebas automáticas elevado a 272 pruebas pasando al 100%.

## [7.0.0] - 2026-09-19 — Workspace & Acoustic Automation Edition

### Agregado
- **Detector Acústico de Doble Aplauso (`acoustic_trigger.py`):**
  - Detección en tiempo real de transitorios acústicos rápidos y dobles aplausos con adaptación continua del suelo de ruido (`NOISE_FLOOR_ALPHA=0.992`).
  - Activación automática de rutinas de trabajo compuestas o despertar del asistente sin interactuar con el teclado.
  - Sondeo y auto-selección inteligente de micrófonos para evitar bloqueos por dispositivos mudos o desconectados.
- **Gestión Avanzada de Workspaces y Multi-Monitor Win32 (`workspace_manager.py`):**
  - Detección y ordenación de monitores físicos conectados (`EnumDisplayMonitors`).
  - Snap automático y apertura dirigida de navegadores y dashboards a pantallas secundarias específicas.
  - Enfoque nativo de instancias activas de Cursor IDE y VS Code (`QueryFullProcessImageNameW` + `AttachThreadInput`), evitando la duplicación de procesos y con alternancia a pantalla completa (F11).
  - Orquestación de rutinas automáticas: *Protocolo Darius*, *Modo Desarrollo*, *Modo Trading* y *Modo Concentración*.
- **Modal Gráfico Dual de Configuración de IA y Voz (`byok_settings.py`):**
  - Interfaz organizada por pestañas: `🤖 MODELO DE IA (BYOK)` y `🔊 VOZ Y SÍNTESIS (TTS)`.
  - Integración completa de parámetros de ElevenLabs en GUI (API Key enmascarada con botón `👁`, Voice ID con presets populares, Model ID, alternador de caché en disco y botón de prueba auditiva en vivo `🔊 PROBAR VOZ`).
  - Persistencia atómica y unificada en `config.json` sin requerir que los usuarios editen archivos `.env` manualmente.
- **Empaquetado Nativo `.EXE` y Distribución Standalone (`build_nuitka.py` & `installer.iss`):**
  - Compilación a binario nativo en C mediante **Nuitka**, eliminando falsos positivos en antivirus (Windows Defender) y reduciendo el tiempo de arranque.
  - Script de instalación para **Inno Setup** que instala en `{localappdata}\Programs\DariusAI` sin requerir permisos de administrador.
  - Soporte de adaptación para cualquier equipo: resolución automática de datos de usuario (`config.json`, logs, cachés) en `%APPDATA%\DariusAI` en modo congelado (`sys.frozen`).
  - Generador de icono de aplicación multi-resolución en `assets/darius.ico`.
- **Suites de Pruebas Unitarias:**
  - `tests/test_acoustic_trigger.py`: Pruebas de RMS, resolución de dispositivos y ciclo de vida.
  - `tests/test_workspace_manager.py`: Pruebas de detección de monitores, snapping y rutinas compuestas.
  - `tests/test_tts_cache.py`: Pruebas de hashing SHA-256 determinista y guardado/reproducción WAV.
  - `tests/test_settings_tts.py`: Pruebas de persistencia de TTS/ElevenLabs y resolución de directorios `%APPDATA%`.

## [6.6.0] - 2026-09-19

### Agregado
- **Motor BYOK (*Bring Your Own Key*) Multi-Proveedor (`ai_client.py`):**
  - Soporte para 7 proveedores de IA: Google Gemini, OpenAI / ChatGPT, OpenRouter, NVIDIA NIM, Groq Cloud, Ollama (ejecución local en `http://localhost:11434/v1`) y endpoints compatibles con OpenAI.
  - Llamador universal `_call_openai_compatible()` implementado sobre la biblioteca estándar `urllib`, sin dependencias externas pesadas.
  - Función de diagnóstico `test_provider_connection()` con prueba de latencia en vivo y verificación de estado.
  - Resolución jerárquica de claves y parámetros: `config.json` (ajustes de usuario) > `.env` (variables de entorno) > defaults.
- **Modal Gráfico de Configuración BYOK (`byok_settings.py`):**
  - Ventana interactiva `BYOKSettingsModal` (`ctk.CTkToplevel`) accesible desde el botón `⚙ Configuración` de la barra superior.
  - Selector de proveedor activo, catálogo de modelos recomendados con entrada libre, configuración de URL base y campo de clave de API enmascarada con alternador de visibilidad.
  - Herramienta de prueba de conexión en tiempo real con indicador visual y reporte de latencia en milisegundos.
- **Visualizador Vectorial de Audio a 60 FPS (`HighPerfWaveVisualizer` en `main.py`):**
  - Generación de 3 capas de ondas sinusoidales armónicas con desfase continuo aceleradas con **NumPy** sobre `tkinter.Canvas`.
  - Actualización atómica de coordenadas mediante `canvas.coords()` que prescinde de `delete("all")`, eliminando el parpadeo de pantalla y las pausas por recolección de basura.
  - Habilitación de escalado High-DPI en Windows (`enable_dpi_awareness`).
- **Suite de Pruebas del Motor BYOK (`tests/test_byok_providers.py`):**
  - 16 pruebas unitarias e integración que cubren la resolución de credenciales, emulación de llamadas compatibles con OpenAI, clasificación de errores y pruebas de conexión simuladas.

### Mejorado
- Rediseño de la interfaz gráfica aplicando la paleta Slate/Zinc (`#09090b`, `#27272a`, `#3b82f6`) con mayor contraste y legibilidad.
- Inyección de contexto de la bóveda de Obsidian estandarizada para todos los proveedores de IA.
- Sincronización completa de la documentación técnica y especificaciones de arquitectura.

## [6.5.0] - 2026-09-19

### Agregado
- Módulo `obsidian_brain.py` para integración directa de memoria y notas en Obsidian Vault (Markdown + YAML frontmatter).
- Comandos por voz para inserción en diario personal (`Diario/YYYY-MM-DD.md`) y guardado de memorias persistentes.
- Inyección contextual de notas de Obsidian en el prompt del sistema de Google Gemini.
- Suite de pruebas unitarias para el motor de Obsidian (`test_obsidian_brain.py`).

### Eliminado
- Eliminación total de dependencias y código de Supabase (`supabase_client.py`, `test_supabase_client.py`).
- Persistencia de configuración y caché 100% local en disco.

## [6.4.0] - 2026-09-19

### Cambios
- Transición a arquitectura 100% nativa de escritorio para Windows.
- Eliminación de dependencias y componentes web/Linux (`app.py`, `Dockerfile`, Railway).
- Consolidación de dependencias en un único `requirements.txt` optimizado para Windows.
- Actualización de metadatos del proyecto y documentación técnica.

## [6.3.0] - 2026-07-21

### Corregido
- Rotación automática de `chat_history.txt` (máx 10.000 líneas, poda al 80% del límite).
- TTL de `apps_cache.json` ahora usa UTC consistente en toda la app.
- Race condition en `_pending_action` protegida con `threading.RLock()`.
- `GEMINI_MAX_TOKENS` sincronizado entre `config_loader.py` (default 800) y tests.

### Agregado
- Indicador de progreso en escaneo de aplicaciones (`rglob("*.exe")`).
- `Dockerfile` multi-etapa para Railway.
- Tests unitarios para `config_loader.py`.
- Test de verificación de patrones `_CMD_PATTERNS` vs `test_commands_v6.py`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.

### Mejorado
- CI/CD: Ruff + pytest + coverage + gitleaks + pip-audit.

## [6.2.0] - 2026-06

### Corregido
- Subprocess `shell=True` reemplazado por listas de args (5 ocurrencias).
- `os.system()` reemplazado por `subprocess.run()`.
- Defaults duplicados entre `app.py` y `config_loader.py` eliminados.

### Agregado
- `pyproject.toml` con Ruff, pytest, y pytest-cov.
- `requirements-dev.txt`.
- Validación de tipos en schema de `config.json`.
- Tests organizados en `tests/` con `conftest.py` + markers de plataforma.

### Refactorizado
- `main.py` → extraídos `ai_client.py` + `tts_worker.py` (210 líneas menos).

## [6.1.0] - 2026-05

### Corregido
- BUG 1: cutoff fuzzy subido (0.52→0.75) en `windows_commands.py`.
- BUG 2: `execute_command` limpia nombre antes de evaluar patrones.
- BUG 3: regex de apagar/reiniciar ampliados.
- BUG 4: `_cmd_accion` ya no captura preguntas genéricas.

## [6.0.0] - 2026-04

### Agregado
- Modos de activación PTT / NOMBRE / AUTO.
- Selector de modo en UI + indicador visual.
- `windows_commands.py` con fuzzy matching semántico.

### Cambios
- UI migrada de Tkinter a CustomTkinter.
- TTS worker en hilo separado.
- Single-instance mutex con win32event.
