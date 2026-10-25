"""Threat detection: prompt injection, encoding tricks, and optional ML classifier."""
import base64
import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from app.core.config import get_settings

settings = get_settings()


@dataclass
class ThreatResult:
    """Result of threat detection."""
    detected: bool
    threat_type: Optional[str]
    confidence: float
    details: dict


class PromptInjectionDetector:
    """Multi-layered prompt injection detector."""

    # Heuristic patterns for direct prompt injection
    DIRECT_INJECTION_PATTERNS = [
        r"(?i)ignore\s+(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)",
        r"(?i)disregard\s+(?:previous|prior|above|earlier|\w+\s+prior)\s+(?:instructions?|prompts?|rules?)",
        r"(?i)forget\s+(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)",
        r"(?i)new\s+(?:instructions?|prompt|task|goal)",
        r"(?i)system\s*:\s*",
        r"(?i)assistant\s*:\s*",
        r"(?i)human\s*:\s*",
        r"(?i)user\s*:\s*",
        r"(?i)<\|?\s*system\s*\|?>",
        r"(?i)<\|?\s*user\s*\|?>",
        r"(?i)<\|?\s*assistant\s*\|?>",
        r"(?i)###\s*(?:instruction|system|prompt)",
        r"(?i)```\s*(?:system|instruction)",
        r"(?i)execute\s+(?:code|command|script)",
        r"(?i)run\s+(?:code|command|script)",
        r"(?i)eval\s*\(",
        r"(?i)exec\s*\(",
        r"(?i)subprocess",
        r"(?i)os\.system",
        r"(?i)__import__",
        r"(?i)getattr\s*\(",
        r"(?i)setattr\s*\(",
        r"(?i)delattr\s*\(",
        r"(?i)globals\s*\(",
        r"(?i)locals\s*\(",
        r"(?i)vars\s*\(",
        r"(?i)breakpoint\s*\(",
        r"(?i)act\s+as\s+\w+",
        r"(?i)you\s+are\s+(?:now\s+)?(?:dan|unrestricted|unfiltered)",
    ]

    # Indirect injection patterns (data exfiltration, tool smuggling)
    INDIRECT_INJECTION_PATTERNS = [
        r"(?i)exfiltrat",
        r"(?i)leak\s+(?:data|info|secret|key|password|token|the\s+api\s+key)",
        r"(?i)send\s+(?:data|info|secret|key|password|token|user\s+data|all\s+user\s+data)\s+(?:to|outside|external)",
        r"(?i)upload\s+(?:data|file|secret)",
        r"(?i)post\s+(?:data|secret|key)",
        r"(?i)curl\s+",
        r"(?i)wget\s+",
        r"(?i)fetch\s*\(",
        r"(?i)axios\s*\.",
        r"(?i)requests\.\w+",
        r"(?i)http\.request",
        r"(?i)net\.http",
        r"(?i)XMLHttpRequest",
        r"(?i)webhook",
        r"(?i)callback\s*(?:url|uri)?",
        r"(?i)redirect\s+(?:to|url)",
    ]

    # Encoding detection patterns
    ENCODING_PATTERNS = [
        (r"[A-Za-z0-9+/]{20,}={0,2}", "base64"),
        (r"%[0-9A-Fa-f]{2}", "url_encoding"),
        (r"\\u[0-9A-Fa-f]{4}", "unicode_escape"),
        (r"&#x?[0-9A-Fa-f]+;", "html_entity"),
        (r"\\x[0-9A-Fa-f]{2}", "hex_escape"),
        (r"\\[0-7]{3}", "octal_escape"),
    ]

    # Role escalation patterns
    ROLE_ESCALATION_PATTERNS = [
        r"(?i)admin",
        r"(?i)root",
        r"(?i)superuser",
        r"(?i)sudo",
        r"(?i)privilege\s+escalat",
        r"(?i)elevat(?:e|ion)",
        r"(?i)bypass\s+(?:auth|security|permission)",
        r"(?i)impersonat",
        r"(?i)assume\s+role",
    ]

    def __init__(self):
        self._compiled_direct = [re.compile(p) for p in self.DIRECT_INJECTION_PATTERNS]
        self._compiled_indirect = [re.compile(p) for p in self.INDIRECT_INJECTION_PATTERNS]
        self._compiled_role = [re.compile(p) for p in self.ROLE_ESCALATION_PATTERNS]
        self._ml_classifier = None
        self._load_ml_classifier()

    def _load_ml_classifier(self) -> None:
        """Load ML classifier if enabled and available."""
        if not settings.enable_ml_classifier:
            return
        try:
            # Placeholder for ML model loading
            # In production, load a trained model (e.g., from transformers)
            pass
        except Exception:
            pass  # Fall back to heuristic-only

    def detect(self, text: str, context: str = "input") -> ThreatResult:
        """Run all detection layers on the input text."""
        if not text or not isinstance(text, str):
            return ThreatResult(detected=False, threat_type=None, confidence=0.0, details={})

        details = {}
        max_confidence = 0.0
        threat_type = None

        # Layer 1: Heuristic pattern matching
        direct_result = self._check_patterns(text, self._compiled_direct, "direct_injection")
        if direct_result.detected:
            details["direct_injection"] = direct_result.details
            if direct_result.confidence > max_confidence:
                max_confidence = direct_result.confidence
                threat_type = "direct_injection"

        indirect_result = self._check_patterns(text, self._compiled_indirect, "indirect_injection")
        if indirect_result.detected:
            details["indirect_injection"] = indirect_result.details
            if indirect_result.confidence > max_confidence:
                max_confidence = indirect_result.confidence
                threat_type = "indirect_injection"

        role_result = self._check_patterns(text, self._compiled_role, "role_escalation")
        if role_result.detected:
            details["role_escalation"] = role_result.details
            if role_result.confidence > max_confidence:
                max_confidence = role_result.confidence
                threat_type = "role_escalation"

        # Layer 2: Encoding detection
        encoding_result = self._detect_encoding_tricks(text)
        if encoding_result.detected:
            details["encoding_tricks"] = encoding_result.details
            if encoding_result.confidence > max_confidence:
                max_confidence = encoding_result.confidence
                threat_type = threat_type or "encoding_tricks"

        # Layer 3: ML classifier (optional)
        if self._ml_classifier:
            ml_result = self._ml_classifier.predict(text)
            if ml_result.detected:
                details["ml_classifier"] = ml_result.details
                if ml_result.confidence > max_confidence:
                    max_confidence = ml_result.confidence
                    threat_type = threat_type or "ml_classifier"

        detected = max_confidence > 0.4
        return ThreatResult(
            detected=detected,
            threat_type=threat_type if detected else None,
            confidence=max_confidence,
            details=details,
        )

    def _check_patterns(self, text: str, patterns: list[re.Pattern], category: str) -> ThreatResult:
        """Check text against a list of compiled regex patterns."""
        matches = []
        for pattern in patterns:
            for match in pattern.finditer(text):
                matches.append({
                    "pattern": pattern.pattern,
                    "match": match.group(),
                    "position": match.span(),
                })

        if matches:
            # Confidence based on number of matches
            confidence = min(0.4 + (len(matches) * 0.2), 0.95)
            return ThreatResult(
                detected=True,
                threat_type=category,
                confidence=confidence,
                details={"matches": matches[:10]},  # Limit to 10 matches
            )
        return ThreatResult(detected=False, threat_type=None, confidence=0.0, details={})

    def _detect_encoding_tricks(self, text: str) -> ThreatResult:
        """Detect various encoding tricks used to hide malicious content."""
        findings = []

        # Check for base64 encoded content that might decode to suspicious patterns
        base64_matches = re.findall(r"[A-Za-z0-9+/]{20,}={0,2}", text)
        for match in base64_matches[:5]:  # Limit checks
            try:
                decoded = base64.b64decode(match).decode("utf-8", errors="ignore")
                if len(decoded) > 10:
                    # Recursively check decoded content
                    sub_result = self.detect(decoded, context="decoded")
                    if sub_result.detected:
                        findings.append({
                            "type": "base64",
                            "encoded": match[:50],
                            "decoded_preview": decoded[:100],
                            "threats": sub_result.details,
                        })
            except Exception:
                pass

        # Check for URL encoding
        url_encoded_matches = re.findall(r"(?:%[0-9A-Fa-f]{2}){5,}", text)
        for match in url_encoded_matches[:5]:
            try:
                decoded = urllib.parse.unquote(match)
                sub_result = self.detect(decoded, context="decoded")
                if sub_result.detected:
                    findings.append({
                        "type": "url_encoding",
                        "encoded": match[:50],
                        "decoded_preview": decoded[:100],
                        "threats": sub_result.details,
                    })
            except Exception:
                pass

        # Check for Unicode escapes
        unicode_matches = re.findall(r"(?:\\u[0-9A-Fa-f]{4}){3,}", text)
        for match in unicode_matches[:5]:
            try:
                decoded = match.encode().decode("unicode_escape")
                sub_result = self.detect(decoded, context="decoded")
                # Also flag if decoded contains suspicious keywords
                suspicious_keywords = ["ignore", "disregard", "forget", "system", "admin", "password", "secret", "key", "token", "exfiltrat", "leak", "send", "upload", "curl", "wget", "eval", "exec", "subprocess", "admin", "root", "sudo"]
                has_suspicious = any(kw in decoded.lower() for kw in suspicious_keywords)
                if sub_result.detected or has_suspicious:
                    findings.append({
                        "type": "unicode_escape",
                        "encoded": match[:50],
                        "decoded_preview": decoded[:100],
                        "threats": sub_result.details,
                    })
            except Exception:
                pass

        # Check for HTML entities
        html_entity_matches = re.findall(r"(?:&#x?[0-9A-Fa-f]+;){5,}", text)
        for match in html_entity_matches[:5]:
            try:
                decoded = html.unescape(match)
                sub_result = self.detect(decoded, context="decoded")
                suspicious_keywords = ["ignore", "disregard", "forget", "system", "admin", "password", "secret", "key", "token", "exfiltrat", "leak", "send", "upload", "curl", "wget", "eval", "exec", "subprocess", "admin", "root", "sudo"]
                has_suspicious = any(kw in decoded.lower() for kw in suspicious_keywords)
                if sub_result.detected or has_suspicious:
                    findings.append({
                        "type": "html_entity",
                        "encoded": match[:50],
                        "decoded_preview": decoded[:100],
                        "threats": sub_result.details,
                    })
            except Exception:
                pass

        if findings:
            return ThreatResult(
                detected=True,
                threat_type="encoding_tricks",
                confidence=min(0.4 + len(findings) * 0.1, 0.9),
                details={"findings": findings},
            )

        return ThreatResult(detected=False, threat_type=None, confidence=0.0, details={})


class DataLossPrevention:
    """Data Loss Prevention: detect and redact PII, secrets, API keys."""

    # Regex patterns for secrets and PII
    SECRET_PATTERNS = [
        (r"(?i)(?:api[_-]?key|apikey|api_secret|access_token|auth_token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{8,})['\"]?", "api_key"),
        (r"(?i)(?:secret|password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?", "password"),
        (r"(?i)(?:bearer|token)\s+([a-zA-Z0-9_\-\.]{20,})", "bearer_token"),
        (r"sk-[a-zA-Z0-9_\-]{20,}", "openai_key"),
        (r"gh[pousr]_[a-zA-Z0-9]{36,}", "github_token"),
        (r"xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}", "slack_bot_token"),
        (r"xoxp-[0-9]{11}-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{32}", "slack_user_token"),
        (r"(?i)aws\s+access\s+key\s*[:=]\s*([A-Z0-9]{20})", "aws_access_key"),
        (r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?", "aws_secret_key"),
        (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "private_key"),
        (r"ssh-(?:rsa|ed25519|dsa) [A-Za-z0-9+/]+[=]{0,2}", "ssh_public_key"),
    ]

    PII_PATTERNS = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "ssn"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "credit_card"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
        (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone_us"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "ipv4"),
        (r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", "ipv6"),
    ]

    def __init__(self):
        self._compiled_secrets = [(re.compile(p, re.IGNORECASE), t) for p, t in self.SECRET_PATTERNS]
        self._compiled_pii = [(re.compile(p), t) for p, t in self.PII_PATTERNS]

    def scan(self, text: str) -> tuple[bool, list[dict], str]:
        """Scan text for secrets and PII. Returns (found, findings, redacted_text)."""
        if not text or not isinstance(text, str):
            return False, [], text

        findings = []
        redacted = text

        # Scan for secrets
        for pattern, secret_type in self._compiled_secrets:
            for match in pattern.finditer(text):
                findings.append({
                    "type": "secret",
                    "subtype": secret_type,
                    "match": match.group(),
                    "position": match.span(),
                })
                # Redact the secret value (keep prefix for identification)
                matched = match.group()
                if ":" in matched or "=" in matched:
                    # Key: value format
                    parts = re.split(r"([:=])", matched, 1)
                    if len(parts) >= 3:
                        redacted = redacted.replace(matched, f"{parts[0]}{parts[1]}[REDACTED]")
                    else:
                        redacted = redacted.replace(matched, "[REDACTED]")
                else:
                    redacted = redacted.replace(matched, "[REDACTED]")

        # Scan for PII
        for pattern, pii_type in self._compiled_pii:
            for match in pattern.finditer(text):
                findings.append({
                    "type": "pii",
                    "subtype": pii_type,
                    "match": match.group(),
                    "position": match.span(),
                })
                redacted = redacted.replace(match.group(), f"[{pii_type.upper()}_REDACTED]")

        return len(findings) > 0, findings, redacted

    def scan_dict(self, data: dict) -> tuple[bool, list[dict], dict]:
        """Recursively scan a dictionary for secrets and PII."""
        findings = []
        redacted = {}

        # Key names that suggest the value is a secret
        secret_key_patterns = [
            r"(?i)secret",
            r"(?i)password",
            r"(?i)passwd",
            r"(?i)pwd",
            r"(?i)api[_-]?key",
            r"(?i)access[_-]?token",
            r"(?i)auth[_-]?token",
            r"(?i)token",
            r"(?i)credential",
            r"(?i)private[_-]?key",
        ]

        def _is_secret_key(key: str) -> bool:
            return any(re.search(p, key) for p in secret_key_patterns)

        def _scan_value(key: str, value: Any, path: str = "") -> Any:
            if isinstance(value, str):
                # Check if key suggests this is a secret
                if _is_secret_key(key) and len(value) >= 8:
                    # Treat as potential secret and redact
                    findings.append({
                        "type": "secret",
                        "subtype": "generic_secret",
                        "match": value,
                        "position": (0, len(value)),
                        "path": path or key,
                    })
                    return "[REDACTED]"
                found, value_findings, redacted_value = self.scan(value)
                if found:
                    for f in value_findings:
                        f["path"] = path or key
                    findings.extend(value_findings)
                return redacted_value
            elif isinstance(value, dict):
                result = {}
                for k, v in value.items():
                    result[k] = _scan_value(k, v, f"{path}.{k}" if path else k)
                return result
            elif isinstance(value, list):
                return [_scan_value(f"[{i}]", item, f"{path}[{i}]") for i, item in enumerate(value)]
            return value

        redacted = _scan_value("root", data)
        return len(findings) > 0, findings, redacted


# Global instances
_prompt_detector: Optional[PromptInjectionDetector] = None
_dlp: Optional[DataLossPrevention] = None


def get_prompt_detector() -> PromptInjectionDetector:
    """Get or create the global prompt injection detector."""
    global _prompt_detector
    if _prompt_detector is None:
        _prompt_detector = PromptInjectionDetector()
    return _prompt_detector


def get_dlp() -> DataLossPrevention:
    """Get or create the global DLP scanner."""
    global _dlp
    if _dlp is None:
        _dlp = DataLossPrevention()
    return _dlp
