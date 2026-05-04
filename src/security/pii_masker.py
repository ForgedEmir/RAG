"""PII masking before sending to LLM — regex only.

Covers structured data: email, phone, IP, credit card.
Proper nouns (fictional characters) are intentionally NOT masked
because this RAG handles game lore where proper nouns are business entities.
"""
import logging
import re
import time
import asyncio
from collections import deque

logger = logging.getLogger(__name__)

_pii_history: deque = deque(maxlen=50)

def get_pii_history() -> list:
    return list(_pii_history)

# Real PII patterns to mask.
# WHY order: credit card (16 digits) before phone to avoid
# a group of 4 digits being captured by the phone pattern.
_PII_PATTERNS: list[tuple[str, str, str]] = [
    ("email",
     r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
     "[EMAIL]"),

    ("card",
     r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
     "[CARD]"),

    ("ip",
     r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
     "[IP]"),

    # Phone: must start with + or 0, then have 7–14 additional digits.
    # WHY: avoids false positives on lore numbers ("year 1234567", "level 42").
    # Covers: +33 6 12 34 56 78 | 06 12 34 56 78 | +1-800-555-0199 | 0033612345678
    ("phone",
     r"(?<!\d)(\+\d[\d\s\-\(\)]{6,14}|0\d[\d\s\-\(\)]{6,13})(?!\d)",
     "[PHONE]"),
]

_COMPILED_PII = [
    (label, re.compile(pattern, re.IGNORECASE), replacement)
    for label, pattern, replacement in _PII_PATTERNS
]


def mask(text: str) -> str:
    """Replace structured PII (email, phone, IP, card) with neutral tokens."""
    if not text:
        return text

    modified = text
    found_types: list[str] = []

    for label, pattern, replacement in _COMPILED_PII:
        new_text, count = pattern.subn(replacement, modified)
        if count > 0:
            found_types.append(label)
            modified = new_text

    if found_types:
        logger.debug(f"[PII] Source text (100c): {text[:100]!r}")
        _pii_history.append({
            "time": time.strftime("%H:%M:%S"),
            "types": found_types,
            "masked_text": modified[:200],
        })
        _log_anonymisation(found_types)

    return modified


def _log_anonymisation(pii_types: list[str]) -> None:
    """Log masked PII types to Langfuse. Fail-silent if Langfuse is down."""
    try:
        from src.monitoring.tracker import track
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(track("pii_masked", detail=f"types={','.join(pii_types)}"))
        except RuntimeError:
            pass
    except Exception:
        pass
    logger.info(f"[PII] Masked: {', '.join(pii_types)}")
