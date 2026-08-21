"""
Agent Safety Boundary
Defends against prompt injection, malicious instructions, tool abuse, 
and secret exfiltration from repository content.
"""

import re

from app.core.logging import get_logger

logger = get_logger("codemigration.safety")

# A set of extremely suspicious terms that might indicate prompt injection attacks
# or attempts to override system policies.
PROMPT_INJECTION_HEURISTICS = [
    r"ignore previous instructions",
    r"you are no longer",
    r"override system policy",
    r"system prompt bypass",
    r"drop database",
    r"extract secrets",
    r"print environment variables",
    r"os\.environ",
    r"cat /etc/shadow"
]


class SecurityViolation(Exception):
    """Raised when repository content violates system safety policies."""
    pass


class AgentSafetyFilter:
    """
    Validates repository content and LLM outputs to prevent malicious execution.
    """

    @staticmethod
    def sanitize_repository_content(content: str) -> str:
        """
        Scans raw repository files (e.g. README, comments) before they enter the LLM context.
        If malicious instructions are found, they are aggressively redacted.
        """
        sanitized = content
        for pattern in PROMPT_INJECTION_HEURISTICS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Malicious content pattern detected and redacted: {pattern}")
                # Aggressively redact the entire malicious block
                sanitized = re.sub(pattern, "[REDACTED_BY_SYSTEM_SECURITY]", sanitized, flags=re.IGNORECASE)

        return sanitized

    @staticmethod
    def validate_sandbox_command(command: str) -> None:
        """
        Defends against command injection. Validates commands sent to the Docker Sandbox.
        """
        # Block reverse shells and unauthorized networking
        blocked_commands = [
            "nc -e", "netcat", "curl", "wget", "bash -i", "/dev/tcp", "nmap"
        ]

        for blocked in blocked_commands:
            if blocked in command.lower():
                logger.error(f"Unsafe sandbox execution blocked: {blocked}")
                raise SecurityViolation(f"Command injection attempt blocked: use of '{blocked}' is prohibited.")

    @staticmethod
    def validate_llm_output(output: str) -> None:
        """
        Scans LLM outputs to prevent secret exfiltration or malicious tool abuse 
        before it is executed or displayed to the user.
        """
        # Block potential secret exfiltration
        if "BEGIN RSA PRIVATE KEY" in output or "aws_access_key_id" in output.lower():
            logger.error("LLM generated output resembling secret exfiltration.")
            raise SecurityViolation("Agent output blocked due to potential secret exposure.")

    @staticmethod
    def enforce_system_policy(system_prompt: str, user_content: str) -> str:
        """
        Uses structural prompt delimiters to mathematically separate system policies from user content.
        This prevents the LLM from confusing malicious code comments as system instructions.
        """
        # Standardize the boundary
        boundary = "--- END OF SYSTEM POLICY. BEGIN UNTRUSTED REPOSITORY CONTENT ---"

        sanitized_user_content = AgentSafetyFilter.sanitize_repository_content(user_content)

        safe_prompt = f"{system_prompt}\n\n{boundary}\n\n{sanitized_user_content}"
        return safe_prompt

agent_safety_filter = AgentSafetyFilter()
