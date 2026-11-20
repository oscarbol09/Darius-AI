<p align="center">
  🇺🇸 <b>English</b> &nbsp;|&nbsp; 🇪🇸 <a href="SECURITY.es.md"><b>Español</b></a>
</p>

# Security Policy

## Supported Versions

| Version | Support Status |
| :--- | :--- |
| **8.5.x** | ✅ Active development and security patches |
| **7.x** | ⚠️ Critical security fixes only |
| **< 7.0** | ❌ End of life / unsupported |

---

## Reporting a Vulnerability

Darius AI is a local-first Windows desktop assistant. If you discover a vulnerability in sandboxing, credential storage, subprocess dispatch, or dependencies:

1. **Please do not disclose exploit details in public GitHub issues.**
2. Open a private GitHub Security Advisory on the repository or contact `@Oscarbol09` directly.
3. Maintainers will triage the report and issue a patch promptly.

---

## Implemented Security Controls

- **DPAPI-Protected BYOK Credentials (`config_loader.py`):** Sensitive API keys (`gemini_api_key`, `openai_api_key`, `openrouter_api_key`, `nvidia_api_key`, `groq_api_key`, `elevenlabs_api_key`, `antigravity_api_key`) are encrypted at rest on Windows using native **DPAPI (`CryptProtectData` / `CryptUnprotectData`)** bound to the active Windows user profile (`dpapi:` prefix in `%APPDATA%\DariusAI\config.json` / `.darius_data/config.json`). In `byok_settings.py`, keys stay masked unless explicitly revealed by user interaction.
- **Local-First Obsidian Vault:** Daily notes, persistent memories, and configuration stay on local disk with zero telemetry or unauthorized background uploads.
- **Command Injection Defense (`windows_commands.py`):** All OS subcommands execute with `shell=False`, validated argument vectors, and explicit `%SystemRoot%\System32` binary paths.
- **Anti-SSRF & Prompt Injection Guard (`security_guard.py`):**
  - Blocks loopback, link-local, RFC 1918 private subnets, cloud metadata endpoints (`169.254.169.254`), and disguised IP encodings (hex/octal/IPv6-mapped IPv4).
  - Multi-tier `InjectionScanner` and context-aware `CredentialStripper` sanitize untrusted web content and console output without corrupting legitimate MD5 hashes or UUIDs.
- **AST-Validated Code Sandbox (`safe_code_interpreter.py`):** Parses code statically before execution, forbids private/dunder attributes, unsafe builtins, and dunder introspection inside `str.format()` strings, and enforces hard timeouts.
- **Process Isolation:** Native Win32 named Mutex prevents concurrent instances from racing on audio hardware or configuration files.
- **Automated CI Audits:** Every push and PR runs static secret scanning (**Gitleaks**) and Python dependency vulnerability scanning (**pip-audit**).
