"""Authentification : clé monitoring + JWT Supabase Auth.

Deux niveaux :
  - check_monitoring_key  : clé secrète pour le dashboard admin
  - get_current_user      : JWT Supabase obligatoire (endpoints utilisateur)
"""
import os
import logging
import asyncio
import time
import hmac
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
# Le mode invité est désactivé par défaut et ne doit être activé que volontairement.
_ALLOW_GUEST_MODE = os.getenv("ALLOW_GUEST_MODE", "false").lower() == "true"
# Garde-fou explicite pour éviter l'activation accidentelle du mode invité en production.
_ALLOW_GUEST_MODE_IN_PROD = os.getenv("ALLOW_GUEST_MODE_IN_PROD", "false").lower() == "true"
_security = HTTPBearer(auto_error=False)
_jwt_cache: OrderedDict[str, tuple[float, Optional[str]]] = OrderedDict()
_jwt_cache_lock = asyncio.Lock()


# ── Clé monitoring (dashboard) ────────────────────────────────────────────────

def check_monitoring_key(request: Request) -> bool:
    if not _MONITORING_KEY:
        return False

    header_key = request.headers.get("x-monitoring-key", "").strip()
    if header_key:
        return hmac.compare_digest(header_key, _MONITORING_KEY)

    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return hmac.compare_digest(auth[7:].strip(), _MONITORING_KEY)

    return False

def require_monitoring(request: Request):
    if not check_monitoring_key(request):
        raise HTTPException(status_code=403, detail="Accès refusé")


# ── JWT Supabase Auth ─────────────────────────────────────────────────────────

async def _verify_supabase_jwt(token: str) -> Optional[str]:
    """Vérifie le JWT via l'API Supabase et retourne le user_id (UUID)."""
    now = time.time()
    async with _jwt_cache_lock:
        cached = _jwt_cache.get(token)
        if cached:
            cached_at, cached_user_id = cached
            if now - cached_at < _JWT_CACHE_TTL_SECONDS:
                _jwt_cache.move_to_end(token)
                return cached_user_id
            del _jwt_cache[token]

    try:
        from src.monitoring.tracker import _get_client
        supa = await _get_client()
        if not supa:
            return None
        # supabase-py v2 supporte await sur les appels auth
        user_resp = await supa.auth.get_user(token)
        user_id = str(user_resp.user.id) if user_resp.user else None
        async with _jwt_cache_lock:
            _jwt_cache[token] = (now, user_id)
            _jwt_cache.move_to_end(token)
            while len(_jwt_cache) > _JWT_CACHE_MAX_SIZE:
                _jwt_cache.popitem(last=False)
        return user_id
    except Exception as e:
        logger.debug(f"JWT invalide : {e}")
        async with _jwt_cache_lock:
            _jwt_cache[token] = (now, None)
            _jwt_cache.move_to_end(token)
            while len(_jwt_cache) > _JWT_CACHE_MAX_SIZE:
                _jwt_cache.popitem(last=False)
        return None


async def get_tenant_id(user_id: str) -> str:
    """Retourne le tenant_id du user : celui d'un autre si invité, sinon le sien."""
    try:
        from src.monitoring.tracker import _get_client
        supa = await _get_client()
        if supa:
            res = await supa.table("user_roles").select("tenant_id").eq("user_id", user_id).limit(1).execute()
            if res.data and res.data[0]["tenant_id"] != user_id:
                return res.data[0]["tenant_id"]
    except Exception as e:
        logger.debug(f"get_tenant_id fallback: {e}")
    return user_id


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> str:
    """Dépendance FastAPI : retourne le user_id depuis le JWT Supabase.
    Lève 401 si le token est absent ou invalide.
    """
    # Toujours lire dynamiquement les variables d'environnement pour supporter les tests patchés
    app_env = getattr(request, "_test_app_env", os.getenv("APP_ENV", "development")).lower()
    allow_guest_mode = getattr(request, "_test_allow_guest_mode", os.getenv("ALLOW_GUEST_MODE", "false").lower() == "true")
    allow_local_guest_header = getattr(request, "_test_allow_local_guest_header", os.getenv("ALLOW_LOCAL_GUEST_HEADER", "true").lower() == "true")
    allow_guest_mode_in_prod = getattr(request, "_test_allow_guest_mode_in_prod", os.getenv("ALLOW_GUEST_MODE_IN_PROD", "false").lower() == "true")

    if not credentials:
        guest_allowed = allow_guest_mode and allow_local_guest_header and (
            app_env != "production" or allow_guest_mode_in_prod
        )
        if guest_allowed:
            guest_id = (request.headers.get("x-local-guest-id") or "").strip()
            if guest_id.startswith("guest_"):
                return guest_id
        raise HTTPException(status_code=401, detail="Token d'authentification manquant. Connectez-vous d'abord.")
    user_id = await _verify_supabase_jwt(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré.")
    return user_id
