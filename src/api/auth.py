"""Authentification : clé monitoring + JWT Supabase Auth.

Deux niveaux :
  - check_monitoring_key  : clé secrète pour le dashboard admin
  - get_current_user      : JWT Supabase obligatoire (endpoints utilisateur)
"""
import os
import logging
import threading
import time
from collections import OrderedDict
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
_MONITORING_KEY = os.getenv("MONITORING_KEY", "")
_JWT_CACHE_TTL_SECONDS = int(os.getenv("JWT_CACHE_TTL_SECONDS", "60"))
_JWT_CACHE_MAX_SIZE = int(os.getenv("JWT_CACHE_MAX_SIZE", "512"))
_APP_ENV = os.getenv("APP_ENV", "development").lower()
_ALLOW_LOCAL_GUEST_HEADER = os.getenv("ALLOW_LOCAL_GUEST_HEADER", "true").lower() == "true"
# ALLOW_GUEST_MODE=true permet aux invités de fonctionner en production.
# Mettre à false pour désactiver totalement le mode invité.
_ALLOW_GUEST_MODE = os.getenv("ALLOW_GUEST_MODE", "true").lower() == "true"
_security = HTTPBearer(auto_error=False)
_jwt_cache: OrderedDict[str, tuple[float, Optional[str]]] = OrderedDict()
_jwt_cache_lock = threading.Lock()


# ── Clé monitoring (dashboard) ────────────────────────────────────────────────

def check_monitoring_key(request: Request) -> bool:
    if not _MONITORING_KEY:
        return False

    header_key = request.headers.get("x-monitoring-key", "").strip()
    if header_key:
        return header_key == _MONITORING_KEY

    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() == _MONITORING_KEY

    return False

def require_monitoring(request: Request):
    if not check_monitoring_key(request):
        raise HTTPException(status_code=403, detail="Accès refusé")


# ── JWT Supabase Auth ─────────────────────────────────────────────────────────

def _verify_supabase_jwt(token: str) -> Optional[str]:
    """Vérifie le JWT via l'API Supabase et retourne le user_id (UUID)."""
    now = time.time()
    with _jwt_cache_lock:
        cached = _jwt_cache.get(token)
        if cached:
            cached_at, cached_user_id = cached
            if now - cached_at < _JWT_CACHE_TTL_SECONDS:
                _jwt_cache.move_to_end(token)
                return cached_user_id
            del _jwt_cache[token]

    try:
        from src.monitoring.tracker import _get_client
        supa = _get_client()
        if not supa:
            return None
        user_resp = supa.auth.get_user(token)
        user_id = str(user_resp.user.id) if user_resp.user else None
        with _jwt_cache_lock:
            _jwt_cache[token] = (now, user_id)
            _jwt_cache.move_to_end(token)
            while len(_jwt_cache) > _JWT_CACHE_MAX_SIZE:
                _jwt_cache.popitem(last=False)
        return user_id
    except Exception as e:
        logger.debug(f"JWT invalide : {e}")
        with _jwt_cache_lock:
            _jwt_cache[token] = (now, None)
            _jwt_cache.move_to_end(token)
            while len(_jwt_cache) > _JWT_CACHE_MAX_SIZE:
                _jwt_cache.popitem(last=False)
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """Dépendance FastAPI : retourne le user_id depuis le JWT Supabase.
    Lève 401 si le token est absent ou invalide.
    """
    if not credentials:
        # Mode invité : accepté si ALLOW_GUEST_MODE=true (dev + prod).
        # En dev, ALLOW_LOCAL_GUEST_HEADER suffit (rétrocompat).
        guest_allowed = _ALLOW_GUEST_MODE or (_APP_ENV != "production" and _ALLOW_LOCAL_GUEST_HEADER)
        if guest_allowed:
            guest_id = (request.headers.get("x-local-guest-id") or "").strip()
            if guest_id.startswith("guest_"):
                return guest_id
        raise HTTPException(status_code=401, detail="Token d'authentification manquant. Connectez-vous d'abord.")
    user_id = _verify_supabase_jwt(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    return user_id
