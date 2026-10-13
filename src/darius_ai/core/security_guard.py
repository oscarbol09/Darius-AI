"""Security Guard — SSRF protection, credential redaction, and prompt injection defense."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar
from urllib.parse import urlsplit

# ============================================================================
# SSRF Defense
# ============================================================================

_BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "169.254.169.254",  # AWS/Azure/GCP metadata
        "metadata.google.internal",
        "metadata.google.com",
        "100.100.100.200",  # Alibaba Cloud metadata
    }
)

_BLOCKED_CIDRS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def _extract_embedded_ipv4(addr: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """Extract embedded IPv4 address from mapped or compatible IPv6 addresses."""
    mapped = addr.ipv4_mapped
    if mapped is not None:
        return mapped

    # IPv4-compatible (RFC 4291 §2.5.5.1): first 96 bits zero, embedded in last 32 bits.
    packed = addr.packed
    if packed[:12] == b"\x00" * 12 and addr != ipaddress.IPv6Address("::") and addr != ipaddress.IPv6Address("::1"):
        return ipaddress.IPv4Address(packed[12:])
    return None


def _detect_disguised_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """Detect and convert disguised IPv4 encodings (hex, octal, decimal, short-dotted)."""
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    addr = ipaddress.IPv4Address(packed)
    if str(addr) == host:
        return None
    return addr


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address string belongs to a private, reserved, or loopback network."""
    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False

    if isinstance(addr, ipaddress.IPv6Address):
        embedded = _extract_embedded_ipv4(addr)
        if embedded is not None:
            addr = embedded

    return any(addr in network for network in _BLOCKED_CIDRS)


def is_safe_url(url: str, allow_dns_lookup: bool = False) -> tuple[bool, str]:
    """Validate a URL against SSRF vulnerabilities, cloud metadata, and loopback attacks."""
    if not url or not isinstance(url, str):
        return False, "Invalid URL: empty or missing string"

    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        return False, f"Invalid URL structure: {exc}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported URL scheme: '{parsed.scheme}'. Only HTTP and HTTPS are permitted"

    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid URL: missing hostname"

    norm_host = hostname.strip().lower()

    if norm_host in ("localhost", "localhost.localdomain") or norm_host.endswith(".localhost"):
        return False, f"Blocked host: '{hostname}' (localhost loopback prohibited)"

    if norm_host in _BLOCKED_HOSTS or norm_host.endswith(".metadata.google.internal"):
        return False, f"Blocked host: '{hostname}' (cloud metadata endpoint prohibited)"

    clean_host = norm_host.strip("[]")

    try:
        literal = ipaddress.ip_address(clean_host)
    except ValueError:
        literal = None

    if literal is not None:
        if isinstance(literal, ipaddress.IPv6Address):
            embedded = _extract_embedded_ipv4(literal)
            if embedded is not None and str(embedded) in _BLOCKED_HOSTS:
                return False, f"Blocked host: '{embedded}' (cloud metadata endpoint prohibited)"
        if is_private_ip(clean_host):
            return False, f"Blocked private IP address: '{clean_host}'"
        return True, ""

    disguised = _detect_disguised_ipv4(clean_host)
    if disguised is not None:
        disguised_str = str(disguised)
        if disguised_str in _BLOCKED_HOSTS:
            return False, f"Blocked disguised metadata host: '{clean_host}' ({disguised_str})"
        if is_private_ip(disguised_str):
            return False, f"Blocked disguised private IP address: '{clean_host}' ({disguised_str})"

    if allow_dns_lookup:
        try:
            resolved_info = socket.getaddrinfo(
                clean_host,
                None,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            )
        except OSError as exc:
            return False, f"Could not resolve host (fail-closed security policy): '{clean_host}' ({exc})"

        for _fam, _stype, _proto, _canon, sockaddr in resolved_info:
            resolved_ip = str(sockaddr[0])
            if resolved_ip in _BLOCKED_HOSTS:
                return False, f"URL resolves to cloud metadata endpoint: '{resolved_ip}'"
            if is_private_ip(resolved_ip):
                return False, f"URL resolves to private IP: '{resolved_ip}'"

    return True, ""


class AntiSSRFValidator:
    """Anti-SSRF validator with support for static and instance calls."""

    @staticmethod
    def is_private_ip(ip_str: str) -> bool:
        return is_private_ip(ip_str)

    @staticmethod
    def is_safe_url(url: str, allow_dns_lookup: bool = False) -> tuple[bool, str]:
        return is_safe_url(url, allow_dns_lookup=allow_dns_lookup)


# ============================================================================
# Credential Stripper
# ============================================================================

_CREDENTIAL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]+\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b")),
    (
        "url_credentials",
        re.compile(r"(https?://)([^:\s/@]+):([^@\s/]+)@"),
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
]


class CredentialStripper:
    """Scans and redacts sensitive credentials and authentication tokens."""

    patterns: ClassVar[list[tuple[str, re.Pattern[str]]]] = _CREDENTIAL_RULES

    @classmethod
    def strip(cls, text: str) -> str:
        """Replace all detected credentials in text with redacted tokens."""
        if not text:
            return text

        result = text
        for label, pattern in cls.patterns:
            if label == "url_credentials":
                result = pattern.sub(r"\1[REDACTED:credentials]@", result)
            else:
                result = pattern.sub(f"[REDACTED:{label}]", result)
        return result

    @classmethod
    def has_credentials(cls, text: str) -> bool:
        """Check whether any sensitive credentials or secret tokens exist in text."""
        if not text:
            return False
        return any(pattern.search(text) is not None for _, pattern in cls.patterns)


# ============================================================================
# Injection Scanner
# ============================================================================


class ThreatLevel(StrEnum):
    """Severity classification for prompt injection findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ThreatLevel):
            return NotImplemented
        order = (ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        return order.index(self) < order.index(other)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ThreatLevel):
            return NotImplemented
        order = (ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        return order.index(self) <= order.index(other)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ThreatLevel):
            return NotImplemented
        order = (ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        return order.index(self) > order.index(other)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ThreatLevel):
            return NotImplemented
        order = (ThreatLevel.LOW, ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        return order.index(self) >= order.index(other)


@dataclass(slots=True)
class ScanFinding:
    """A single security finding identified during prompt scanning."""

    threat_level: ThreatLevel
    pattern_name: str
    matched_text: str
    description: str
    start: int = 0
    end: int = 0


_INJECTION_RULES: list[tuple[re.Pattern[str], str, ThreatLevel, str]] = [
    # System prompt overrides
    (
        re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)\b"),
        "prompt_override",
        ThreatLevel.HIGH,
        "Attempt to override or ignore system instructions",
    ),
    (
        re.compile(r"(?i)\bdisregard\s+(?:all\s+)?(?:previous|prior|your)\s+(?:instructions?|programming|rules?)\b"),
        "prompt_override",
        ThreatLevel.HIGH,
        "Attempt to disregard system programming or instructions",
    ),
    (
        re.compile(r"(?i)\bignore\s+(?:all\s+)?rules\b"),
        "rule_override",
        ThreatLevel.HIGH,
        "Attempt to ignore system rules",
    ),
    (
        re.compile(r"(?i)\bdisregard\s+(?:all\s+)?rules\b"),
        "rule_override",
        ThreatLevel.HIGH,
        "Attempt to disregard all rules",
    ),
    # Identity takeover / jailbreak
    (
        re.compile(r"(?i)\byou\s+are\s+now\s+(?:a\s+)?(?:different|new|my|in\s+developer|DAN\b)"),
        "identity_takeover",
        ThreatLevel.HIGH,
        "Attempt to hijack or alter assistant identity or role",
    ),
    (
        re.compile(
            r"(?i)\bpretend\s+(?:you\s+)?(?:have\s+|to\s+have\s+)?no\s+(?:restrictions?|limitations?|limits?|rules?|filters?)"
        ),
        "restriction_bypass",
        ThreatLevel.HIGH,
        "Attempt to simulate an unconstrained or unrestricted state",
    ),
    (
        re.compile(r"(?i)\b(?:DAN|do\s+anything\s+now)\s+(?:mode|prompt|jailbreak)\b"),
        "jailbreak_dan",
        ThreatLevel.HIGH,
        "DAN jailbreak mode attempt",
    ),
    # Delimiter breakout
    (
        re.compile(r"</(?:im_start|im_end|system|assistant)>|<\|(?:im_start|im_end|system|assistant)\|>"),
        "delimiter_breakout",
        ThreatLevel.HIGH,
        "Special token or delimiter injection attempt",
    ),
    (
        re.compile(r"```(?:system|assistant)\b"),
        "markdown_role_injection",
        ThreatLevel.HIGH,
        "Markdown role delimiter injection attempt",
    ),
    # Code execution attempts in prompt
    (
        re.compile(r"(?i)\b(?:execute|run|eval|exec)\s*\(\s*['\"]"),
        "code_execution",
        ThreatLevel.HIGH,
        "Direct code execution invocation in prompt",
    ),
    (
        re.compile(r"(?:;|\||&&)\s*(?:rm|curl|wget|nc|ncat|bash|sh|python|perl)\b"),
        "shell_execution",
        ThreatLevel.HIGH,
        "Shell command chaining execution in prompt",
    ),
    # Data exfiltration
    (
        re.compile(
            r"(?i)\b(?:send|post|upload|exfiltrate|transmit)\s+(?:(?:to|data|all|everything)\s+)*(?:to\s+)?(?:https?://|my\s+server)"
        ),
        "data_exfiltration",
        ThreatLevel.HIGH,
        "Data exfiltration command attempt",
    ),
]


class InjectionScanner:
    """Scanner for detecting prompt injection, delimiter breakout, and execution payloads."""

    rules: ClassVar[list[tuple[re.Pattern[str], str, ThreatLevel, str]]] = _INJECTION_RULES

    @classmethod
    def scan(cls, text: str) -> list[ScanFinding]:
        """Scan input text for known injection and adversarial patterns."""
        if not text:
            return []

        findings: list[ScanFinding] = []
        for regex, name, level, description in cls.rules:
            for match in regex.finditer(text):
                findings.append(
                    ScanFinding(
                        threat_level=level,
                        pattern_name=name,
                        matched_text=match.group(0)[:100],
                        description=description,
                        start=match.start(),
                        end=match.end(),
                    )
                )
        return findings

    @classmethod
    def is_safe(cls, text: str, max_allowed_threat: ThreatLevel = ThreatLevel.MEDIUM) -> bool:
        """Determine if input text is safe given a maximum acceptable threat level."""
        findings = cls.scan(text)
        if not findings:
            return True
        return all(f.threat_level <= max_allowed_threat for f in findings)


__all__ = [
    "AntiSSRFValidator",
    "CredentialStripper",
    "InjectionScanner",
    "ScanFinding",
    "ThreatLevel",
    "is_private_ip",
    "is_safe_url",
]
