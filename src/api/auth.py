"""Authentification : clé monitoring + JWT Supabase Auth.

Deux niveaux :
  - check_monitoring_key  : clé secrète pour le dashboard admin
  - get_current_user      : JWT Supabase obligatoire (endpoints utilisateur)
  - get_optional_user     : JWT optionnel, fallback sur user_id du body (compat)
"""
import os
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
_MONITORING_KEY = os.getenv("MONITORING_KEY", "")
_security = HTTPBearer(auto_error=False)


# ── Clé monitoring (dashboard) ────────────────────────────────────────────────

def check_monitoring_key(request: Request) -> bool:
    return request.query_params.get("key", "") == _MONITORING_KEY and _MONITORING_KEY != ""

def require_monitoring(request: Request):
    if not check_monitoring_key(request):
        raise HTTPException(status_code=403, detail="Accès refusé")


# ── JWT Supabase Auth ─────────────────────────────────────────────────────────

def _verify_supabase_jwt(token: str) -> Optional[str]:
    """Vérifie le JWT via l'API Supabase et retourne le user_id (UUID)."""
    try:
        from src.monitoring.tracker import _get_client
        supa = _get_client()
        if not supa:
            return None
        user_resp = supa.auth.get_user(token)
        return str(user_resp.user.id) if user_resp.user else None
    except Exception as e:
        logger.debug(f"JWT invalide : {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """Dépendance FastAPI : retourne le user_id depuis le JWT Supabase.
    Lève 401 si le token est absent ou invalide.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Token d'authentification manquant. Connectez-vous d'abord.")
    user_id = _verify_supabase_jwt(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    return user_id


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """Dépendance FastAPI : JWT si présent, sinon user_id du body (compat ancien frontend).
    Ne lève jamais d'erreur — l'endpoint valide lui-même si user_id est requis.
    """
    if credentials:
        user_id = _verify_supabase_jwt(credentials.credentials)
        if user_id:
            return user_id
    # Fallback : user_id dans le body JSON
    try:
        body = await request.json()
        return body.get("user_id", "")
    except Exception:
        return ""
