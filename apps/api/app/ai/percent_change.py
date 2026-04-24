from __future__ import annotations

import re

_PERCENT_CHANGE_PATTERNS = (
    r"\bв\s+процент\w*",
    r"\bна\s+сколько\s+процент\w*",
    r"\bпроцент\w*",
    r"\bрост\b",
    r"\bпаден\w*",
    r"\bизменен\w*",
    r"\bподнял\w*",
    r"\bопуст\w*",
    r"\bвырос\w*",
    r"\bсниз\w*",
    r"\bпросе\w*",
    r"\bотносительно\s+прошл\w+",
    r"\bк\s+прошл\w+",
)


def is_percent_change_request(text: str) -> bool:
    normalized = text.lower().replace("ё", "е")
    return any(re.search(pattern, normalized) for pattern in _PERCENT_CHANGE_PATTERNS)
