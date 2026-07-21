# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 6.x     | ✅ Active development |
| < 6.0   | ❌ No longer supported |

## Reporting a Vulnerability

This project is a personal desktop assistant. If you find a security
vulnerability, please open an issue or contact the maintainer directly.

**Do not** post sensitive information (API keys, tokens) in public issues.

## Security Best Practices

- API keys and secrets are loaded from `.env` (not committed to repo)
- Supabase credentials are optional — the app runs in local-only mode if absent
- All subprocess calls use argument lists (not `shell=True`) to prevent injection
- Dependencies are audited via `pip-audit` in CI
- Secrets scanned via `gitleaks` in CI
