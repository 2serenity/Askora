from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|pass|secret|token|api_key|authorization|cookie|email|phone|mobile|telegram|chat_id)",
    re.IGNORECASE,
)


def redact_payload(payload: Any, *, max_text_len: int = 500) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_payload(value, max_text_len=max_text_len)
        return redacted
    if isinstance(payload, list):
        return [redact_payload(item, max_text_len=max_text_len) for item in payload]
    if isinstance(payload, tuple):
        return [redact_payload(item, max_text_len=max_text_len) for item in payload]
    if isinstance(payload, str):
        if len(payload) > max_text_len:
            return f"{payload[:max_text_len]}...[TRUNCATED]"
        if SENSITIVE_KEY_PATTERN.search(payload):
            return "[REDACTED]"
        return payload
    return payload
