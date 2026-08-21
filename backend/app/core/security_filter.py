"""
Security Guard & Prompt Injection Defense
Sanitizes user code, strips enterprise credentials/tokens before LLM ingestion, and detects prompt injection attempts.
"""

import re

from app.core.logging import get_logger

logger = get_logger("codemigration.security.filter")

# Secret detection patterns (Regex matching API keys, tokens, private keys)
SECRET_PATTERNS = [
    (re.compile(r"(?i)aws_access_key_id\s*=\s*['\"][A-Z0-9]{20}['\"]"), "AWS_ACCESS_KEY_REDACTED"),
    (re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]"), "AWS_SECRET_KEY_REDACTED"),
    (re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"), "GITHUB_PAT_REDACTED"),
    (re.compile(r"(?i)sk-[a-zA-Z0-9]{48}"), "OPENAI_API_KEY_REDACTED"),
    (re.compile(r"(?i)sk-ant-api03-[a-zA-Z0-9\-_]{80,}"), "ANTHROPIC_API_KEY_REDACTED"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----[\s\S]+?-----END \1 KEY-----"), "PRIVATE_KEY_REDACTED"),
    (re.compile(r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]"), "PASSWORD_REDACTED"),
]

# Prompt injection attempt signatures
INJECTION_SIGNATURES = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s+prompt\s+override"),
    re.compile(r"(?i)disregard\s+all\s+(prior|previous)\s+prompts"),
    re.compile(r"(?i)you\s+are\s+now\s+in\s+developer\s+mode"),
    re.compile(r"(?i)DAN\s+mode"),
    re.compile(r"(?i)output\s+all\s+internal\s+prompts"),
]


class SecurityFilter:
    @staticmethod
    def redact_secrets(code: str) -> tuple[str, int]:
        """Redact sensitive tokens and credentials from source code before LLM dispatch."""
        redacted_code = code
        total_redactions = 0
        for pattern, replacement in SECRET_PATTERNS:
            matches = pattern.findall(redacted_code)
            if matches:
                total_redactions += len(matches)
                redacted_code = pattern.sub(f"/* {replacement} */", redacted_code)

        if total_redactions > 0:
            logger.info("Redacted secrets from code payload", count=total_redactions)
        return redacted_code, total_redactions

    @staticmethod
    def detect_prompt_injection(prompt: str) -> bool:
        """Analyze input prompt to detect potential adversarial injection or jailbreaks."""
        for signature in INJECTION_SIGNATURES:
            if signature.search(prompt):
                logger.warning("Prompt injection signature detected", match=signature.pattern)
                return True
        return False


security_filter = SecurityFilter()
