"""Masquage PII avant envoi au LLM.

Approche regex uniquement (pas de NLP) — notre app traite du lore fictif,
les données personnelles sensibles ne devraient pas y figurer.
Couvre : email, téléphone, IP, numéro de carte bancaire.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

import time
from collections import deque

_pii_history: deque = deque(maxlen=50)

def get_pii_history() -> list:
    return list(_pii_history)

# Patterns PII réels à masquer
# WHY: L'ordre compte — la carte bancaire (16 chiffres) doit être évaluée AVANT le
# téléphone pour éviter qu'un groupe de 4 chiffres soit capturé comme numéro de tél.
_PII_PATTERNS: list[tuple[str, str, str]] = [
    ("email",      r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",       "[EMAIL]"),
    ("carte",      r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",                              "[CARTE]"),
    ("ip",         r"\b(?:\d{1,3}\.){3}\d{1,3}\b",                              "[IP]"),
    ("telephone",  r"(?<!\d)(\+?[\d\s\-\(\)]{7,15})(?!\d)",                     "[TEL]"),
]

_COMPILED_PII = [
    (label, re.compile(pattern, re.IGNORECASE), replacement)
    for label, pattern, replacement in _PII_PATTERNS
]


def masquer(texte: str) -> str:
    """Remplace les PII par des tokens neutres. Retourne le texte original si aucun PII trouvé."""
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
        # Stocke le texte masqué (pas le PII original) pour le monitoring
        _pii_history.append({
            "time": time.strftime("%H:%M:%S"),
            "types": found_types,
            "masked_text": modified[:200],  # texte avec [EMAIL] etc., pas le vrai PII
        })
        _log_anonymisation(found_types)

    return modified


def _log_anonymisation(pii_types: list[str]) -> None:
    """Log les types de PII masqués dans Langfuse. Fail-silent si Langfuse down."""
    try:
        from src.monitoring.tracker import track
        track("pii_masked", detail=f"types={','.join(pii_types)}")
    except Exception:
        pass
    logger.info(f"[PII] Masqué : {', '.join(pii_types)}")
