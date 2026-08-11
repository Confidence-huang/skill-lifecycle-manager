"""Bound and redact diagnostics before lifecycle commands return them.

Verification probes and plugin observation both receive text from external processes. Call
``redact(text, limit=400)`` before placing that text in an exception or evidence document so common
credential shapes never become manager output.
"""

from __future__ import annotations  # Keep annotations stable on Python 3.12.

import re  # Recognize common credential-bearing diagnostic shapes.


SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|cookie|authorization|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)"
)  # Preserve the key name while removing its sensitive value.


# --- Redact one bounded diagnostic ---
def redact(text: str, limit: int = 4000) -> str:
    """Return bounded text with common credential values replaced."""
    bounded = text[:limit]  # Diagnostic evidence is not an unlimited log transport.
    return SECRET_PATTERN.sub(r"\1\2[REDACTED]", bounded)
