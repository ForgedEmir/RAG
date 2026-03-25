"""
Enregistre les événements de l'application dans Supabase pour le monitoring.
Fail-silent : si Supabase est indisponible, l'application continue normalement.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY")
_client = None


def _get_client():
    global _client
    if _client is None and _SUPABASE_URL and _SUPABASE_KEY:
        from supabase import create_client
        _client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    return _client


def track(event_type: str, detail: str = "", latency_ms: Optional[int] = None) -> None:
    """
    Enregistre un événement dans Supabase.

    Types :
        question         — question posée à l'Oracle
        injection_regex  — injection bloquée par les règles
        injection_lakera — injection bloquée par Lakera Guard
        rate_limit       — limite de débit atteinte
        error            — erreur serveur
    """
    client = _get_client()
    if not client:
        return
    try:
        data: dict = {"type": event_type, "detail": detail[:500]}
        if latency_ms is not None:
            data["latency_ms"] = latency_ms
        client.table("events").insert(data).execute()

        if event_type in ("injection_regex", "injection_lakera"):
            _check_injection_spike(client)

    except Exception as e:
        logger.warning(f"[MONITORING] Erreur Supabase : {e}")


def _check_injection_spike(client) -> None:
    """Alerte Sentry si plus de 10 injections détectées en 5 minutes."""
    try:
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = (
            client.table("events")
            .select("id", count="exact")
            .in_("type", ["injection_regex", "injection_lakera"])
            .gte("created_at", five_min_ago)
            .execute()
        )
        if (result.count or 0) >= 10:
            logger.warning("[MONITORING] Spike d'injections : >10 tentatives en 5 minutes.")
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    "Spike d'injections : >10 tentatives en 5 minutes", level="warning"
                )
            except ImportError:
                pass
    except Exception:
        pass


def get_history(session_id: str) -> list:
    """Récupère les 5 derniers échanges d'une session depuis Supabase."""
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        r = (
            client.table("conversations")
            .select("question, answer")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        return list(reversed(r.data))
    except Exception as e:
        logger.warning(f"[MEMORY] Erreur lecture historique : {e}")
        return []


def save_exchange(session_id: str, question: str, answer: str) -> None:
    """Persiste un échange question/réponse dans Supabase."""
    client = _get_client()
    if not client or not session_id:
        return
    try:
        client.table("conversations").insert({
            "session_id": session_id,
            "question": question,
            "answer": answer,
        }).execute()
    except Exception as e:
        logger.warning(f"[MEMORY] Erreur sauvegarde échange : {e}")


def get_conversation(session_id: str) -> list:
    """Retourne tous les échanges d'une session dans l'ordre chronologique."""
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        r = (
            client.table("conversations")
            .select("question, answer, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        return r.data
    except Exception as e:
        logger.warning(f"[MEMORY] Erreur chargement conversation : {e}")
        return []


def delete_conversation(session_id: str) -> None:
    """Supprime tous les échanges d'une session dans Supabase."""
    client = _get_client()
    if not client or not session_id:
        return
    try:
        client.table("conversations").delete().eq("session_id", session_id).execute()
    except Exception as e:
        logger.warning(f"[MEMORY] Erreur suppression conversation : {e}")


def get_stats() -> dict:
    """Retourne les statistiques agrégées pour le dashboard de monitoring."""
    client = _get_client()
    if not client:
        return {"error": "Supabase non configuré", "counts": {}, "events": []}

    try:
        # Compteurs par type
        types = ["question", "injection_regex", "injection_lakera", "rate_limit", "error",
                 "voice", "tts", "upload", "upload_blocked", "reindex", "fallback"]
        counts = {}
        for t in types:
            r = client.table("events").select("id", count="exact").eq("type", t).execute()
            counts[t] = r.count or 0

        # Latence moyenne (100 dernières questions)
        latency_r = (
            client.table("events")
            .select("latency_ms")
            .eq("type", "question")
            .not_.is_("latency_ms", "null")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        latencies = [row["latency_ms"] for row in latency_r.data if row.get("latency_ms")]
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

        # Derniers 50 événements
        recent = (
            client.table("events")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

        # Détection de spike (5 dernières minutes)
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        spike_r = (
            client.table("events")
            .select("id", count="exact")
            .in_("type", ["injection_regex", "injection_lakera"])
            .gte("created_at", five_min_ago)
            .execute()
        )

        return {
            "counts": counts,
            "avg_latency_ms": avg_latency,
            "injection_spike": (spike_r.count or 0) >= 10,
            "events": recent.data,
        }

    except Exception as e:
        logger.error(f"[MONITORING] Erreur get_stats : {e}")
        return {"error": str(e), "counts": {}, "events": []}
