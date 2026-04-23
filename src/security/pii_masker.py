"""Masquage PII avant envoi au LLM — regex uniquement.

Couvre les données structurées : email, téléphone, IP, carte bancaire.
Les noms propres (personnages fictifs) ne sont PAS masqués intentionnellement
car ce RAG traite du lore de jeu où les noms propres sont des entités métier.
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

# Patterns PII réels à masquer.
# WHY ordre : carte bancaire (16 chiffres) avant téléphone pour éviter
# qu'un groupe de 4 chiffres soit capturé par le pattern téléphone.
_PII_PATTERNS: list[tuple[str, str, str]] = [
    ("email",
     r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
     "[EMAIL]"),

    ("carte",
     r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
     "[CARTE]"),

    ("ip",
     r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
     "[IP]"),

    # Téléphone : doit commencer par + ou 0, puis avoir 7–14 chiffres supplémentaires.
    # WHY: évite les faux positifs sur les nombres du lore ("l'an 1234567", "niveau 42").
    # Couvre : +33 6 12 34 56 78 | 06 12 34 56 78 | +1-800-555-0199 | 0033612345678
    ("telephone",
     r"(?<!\d)(\+\d[\d\s\-\(\)]{6,14}|0\d[\d\s\-\(\)]{6,13})(?!\d)",
     "[TEL]"),
]

_COMPILED_PII = [
    (label, re.compile(pattern, re.IGNORECASE), replacement)
    for label, pattern, replacement in _PII_PATTERNS
]


def masquer(texte: str) -> str:
    """Remplace les PII structurés (email, téléphone, IP, carte) par des tokens neutres."""
    if not texte:
        return texte

    modified = texte
    found_types: list[str] = []

    for label, pattern, replacement in _COMPILED_PII:
        new_text, count = pattern.subn(replacement, modified)
        if count > 0:
            found_types.append(label)
            modified = new_text

    if found_types:
        logger.debug(f"[PII] Source text (100c): {texte[:100]!r}")
        _pii_history.append({
            "time": time.strftime("%H:%M:%S"),
            "types": found_types,
            "masked_text": modified[:200],
        })
        _log_anonymisation(found_types)

    return modified


def _log_anonymisation(pii_types: list[str]) -> None:
    """Log les types de PII masqués dans Langfuse. Fail-silent si Langfuse down."""
    try:
        from src.monitoring.tracker import track
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(track("pii_masked", detail=f"types={','.join(pii_types)}"))
        except RuntimeError:
            pass
    except Exception:
        pass
    logger.info(f"[PII] Masqué : {', '.join(pii_types)}")
