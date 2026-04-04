"""
Validation des entrées utilisateur avant envoi au LLM.

Deux couches de protection :
  1. Regex (instantané) — bloque les patterns connus
  2. Lakera Guard (<50ms) — classifieur spécialisé pour les injections subtiles

Config .env :
  SECURITY_VALIDATOR = true | rules | false
  LAKERA_API_KEY     = clé API Lakera
  LAKERA_PROJECT_ID  = projet Lakera (optionnel)
"""
import os
import logging
import re
import requests
from typing import TypedDict

logger = logging.getLogger(__name__)

_MODE = os.getenv("SECURITY_VALIDATOR", "rules").lower()
_LAKERA_API_KEY  = os.getenv("LAKERA_API_KEY")
_LAKERA_URL      = "https://api.lakera.ai/v2/guard"
_LAKERA_PROJECT  = os.getenv("LAKERA_PROJECT_ID")
_HTTP_SESSION = requests.Session()


class ValidationResult(TypedDict):
    valid: bool
    type: str     # "ok" | "prompt_injection" | "jailbreak"
    reason: str


# ── Patterns regex ───────────────────────────────────────────────────────────

_INJECTION_PATTERNS: list[str] = [
    # Hijacking de rôle
    r"you\s+are\s+now\s+",
    r"tu\s+es\s+maintenant\s+",
    r"act\s+as\s+(if\s+you\s+are|a\s+)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"agis?\s+comme\s+(si\s+tu\s+(es|étais)|un?e?\s+)",
    r"fais\s+semblant\s+d[''e]",
    r"do\s+anything\s+now",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"mode\s+sans\s+filtre",

    # Override d'instructions
    r"ignore\s+.*instructions?",
    r"oublie\s+.*instructions?",
    r"ignore\s+ce\s+qui\s+précède",
    r"forget\s+(your|all|previous)\s+instructions?",
    r"bypass\s+the\s+(system|filter|rules|instructions)",
    r"tes\s+nouvelles?\s+instructions?\s+sont",
    r"désormais\s+tu\s+(dois|es|vas)",
    r"constraints?\s+disabled",

    # Extraction de prompt système
    r"system\s+prompt",
    r"prompt\s+injection",
    r"(reveal|print|show)\s+your\s+(prompt|instructions|system)",
    r"what\s+are\s+your\s+(instructions|constraints|rules)",
    r"révèle?\s+(ton\s+|le\s+|ta\s+)?(system\s+)?prompt",
    r"montre\s+(-moi\s+)?(ton\s+|le\s+)?(system\s+)?prompt",
    r"quelles?\s+sont\s+tes\s+(instructions?|contraintes?|règles?)",

    # Tokens de contrôle / marqueurs de template
    r"(###|---)\s*system",
    r"\b(SYSTEM|ASSISTANT|USER)\s*:",
    r"\[system\]",
    r"\[inst\]",
    r"<\|system\|>",
    r"<\|im_start\|>",
    r"INIT\s+OVERRIDE",
    r"OVERRIDE_PROCEDURE",
    r"PRIMARY_DIRECTIVE",
    r"REVERSE_ENGINEER",
    r"#!>",
    r"--MODE=",
    r"\[REMOVED\]",

    # Injections techniques obfusquées
    r"overwrite\s+.{0,40}(filter|check|instruction|memory|opcode)",
    r"disable\s+all\s+(checks?|filters?|rules?|guards?)",
    r"\bNOP\s+opcode\b",
    r"\bhex\s+dump\b",
    r"\[0x[0-9a-fA-F]{4,}\]",
    r"execution\s+via\s+",
    r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){3,}",

    # Commandes shell
    r"/bin/(sh|bash|zsh|cmd)",
    r"\bsubprocess\b",
    r"\bchmod\s+[0-9]+",
    r"\bexec\s+/",
    r"sys_call",
    r"root\s+access",
    r"/dev/(mem|null|zero|urandom)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


# ── Interface publique ───────────────────────────────────────────────────────

def valider_entree(texte: str) -> ValidationResult:
    """Point d'entrée principal : valide un texte avant de l'envoyer au LLM."""
    if _MODE in ("false", "0", "no", "disabled"):
        return {"valid": True, "type": "ok", "reason": "Validation désactivée"}

    if not texte or not texte.strip():
        return {"valid": False, "type": "prompt_injection", "reason": "Entrée vide"}

    result = check_patterns(texte)
    if not result["valid"]:
        logger.warning(f"[REGEX] Injection détectée : {result['reason']}")
        return result

    if _MODE in ("rules", "rules_only"):
        return {"valid": True, "type": "ok", "reason": "Validation par règles OK"}

    return _valider_lakera(texte)


def check_patterns(texte: str) -> ValidationResult:
    """Couche 1 — Regex uniquement, zéro dépendance externe."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(texte):
            return {"valid": False, "type": "prompt_injection", "reason": "Motif suspect détecté"}
    return {"valid": True, "type": "ok", "reason": "Aucun pattern suspect"}


# ── Lakera Guard (couche 2) ──────────────────────────────────────────────────

def _valider_lakera(texte: str) -> ValidationResult:
    """Couche 2 — classifieur Lakera Guard pour les injections subtiles.
    Fail-open si l'API est indisponible.
    """
    if not _LAKERA_API_KEY:
        logger.warning("[LAKERA] Clé manquante — fail-open.")
        return {"valid": True, "type": "ok", "reason": "Lakera Guard non configuré"}

    try:
        payload: dict = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a game lore assistant. Only answer questions about "
                        "characters, places, artifacts, and events in the game world."
                    ),
                },
                {"role": "user", "content": texte[:2000]},
            ],
            "breakdown": True,
        }
        if _LAKERA_PROJECT:
            payload["project_id"] = _LAKERA_PROJECT

        response = _HTTP_SESSION.post(
            _LAKERA_URL,
            headers={"Authorization": f"Bearer {_LAKERA_API_KEY}"},
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("flagged"):
            breakdown = data.get("breakdown", [])
            is_jailbreak = any(
                item.get("detector_type") == "jailbreak" and item.get("detected", False)
                for item in breakdown
            )
            threat_type = "jailbreak" if is_jailbreak else "prompt_injection"
            logger.warning(f"[LAKERA] {threat_type} détecté.")
            return {"valid": False, "type": threat_type, "reason": f"Détecté par Lakera Guard ({threat_type})"}

        return {"valid": True, "type": "ok", "reason": "Aucune menace détectée"}

    except Exception as e:
        logger.warning(f"[LAKERA] Indisponible, fail-open : {e}")
        return {"valid": True, "type": "ok", "reason": "Lakera Guard indisponible"}
