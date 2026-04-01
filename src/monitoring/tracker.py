"""Monitoring Supabase : événements, historique de conversation, résumé utilisateur.
Fail-silent : si Supabase est indisponible, l'app continue normalement.

Schéma :
  conversations (id, session_id, user_id, created_at)
  messages      (id, conversation_id, user_id, role, content, created_at)
  user_memory   (user_id PK, summary, updated_at)
  events        (id, type, detail, latency_ms, created_at)
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


# ── Événements ────────────────────────────────────────────────────────────────

def track(event_type: str, detail: str = "", latency_ms: Optional[int] = None) -> None:
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
        logger.warning(f"[MONITORING] Supabase : {e}")


def _check_injection_spike(client) -> None:
    try:
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        r = (client.table("events").select("id", count="exact")
             .in_("type", ["injection_regex", "injection_lakera"])
             .gte("created_at", since).execute())
        if (r.count or 0) >= 10:
            logger.warning("[MONITORING] Spike d'injections : >10 en 5 minutes.")
            try:
                import sentry_sdk
                sentry_sdk.capture_message("Spike d'injections : >10 en 5 minutes", level="warning")
            except ImportError:
                pass
    except Exception:
        pass


# ── Conversations ─────────────────────────────────────────────────────────────

def _get_or_create_conversation(client, session_id: str, user_id: str) -> Optional[int]:
    try:
        r = client.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
        if r.data:
            return r.data[0]["id"]
        inserted = client.table("conversations").insert({"session_id": session_id, "user_id": user_id}).execute()
        return inserted.data[0]["id"] if inserted.data else None
    except Exception as e:
        logger.warning(f"[MEMORY] get_or_create_conversation : {e}")
        return None


def _messages_to_history(messages: list) -> list:
    # Supabase peut renvoyer un ordre non déterministe quand created_at est identique.
    # On stabilise localement (created_at -> id -> role) si ces champs sont présents.
    has_order_fields = any((m.get("created_at") is not None) or (m.get("id") is not None) for m in messages)
    normalized = messages
    if has_order_fields:
        normalized = sorted(
            messages,
            key=lambda m: (
                str(m.get("created_at", "")),
                int(m.get("id", 0) or 0),
                0 if m.get("role") == "user" else 1,
            ),
        )

    pairs: list = []
    pending_question: str = ""
    for msg in normalized:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            pending_question = content
        elif role == "assistant" and pending_question:
            pairs.append({"question": pending_question, "answer": content})
            pending_question = ""
    return pairs


def get_history(session_id: str) -> list:
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        conv = client.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
        if not conv.data:
            return []
        r = (client.table("messages").select("id, role, content, created_at")
             .eq("conversation_id", conv.data[0]["id"])
             .order("created_at", desc=True)
             .limit(10).execute())
        return _messages_to_history(list(reversed(r.data or [])))
    except Exception as e:
        logger.warning(f"[MEMORY] get_history : {e}")
        return []


def get_conversation(session_id: str) -> list:
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        conv = client.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
        if not conv.data:
            return []
        r = (client.table("messages").select("id, role, content, created_at")
             .eq("conversation_id", conv.data[0]["id"])
             .order("created_at")
             .execute())
        return _messages_to_history(r.data or [])
    except Exception as e:
        logger.warning(f"[MEMORY] get_conversation : {e}")
        return []


def conversation_belongs_to_user(session_id: str, user_id: str) -> bool:
    client = _get_client()
    if not client or not session_id or not user_id:
        return False
    try:
        r = (client.table("conversations").select("id")
             .eq("session_id", session_id)
             .eq("user_id", user_id)
             .limit(1).execute())
        return bool(r.data)
    except Exception as e:
        logger.warning(f"[MEMORY] conversation_belongs_to_user : {e}")
        return False


def get_conversation_owner(session_id: str) -> str:
    client = _get_client()
    if not client or not session_id:
        return ""
    try:
        r = (client.table("conversations").select("user_id")
             .eq("session_id", session_id)
             .limit(1).execute())
        return r.data[0].get("user_id", "") if r.data else ""
    except Exception as e:
        logger.warning(f"[MEMORY] get_conversation_owner : {e}")
        return ""


def delete_conversation(session_id: str) -> None:
    client = _get_client()
    if not client or not session_id:
        return
    try:
        conv = client.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
        if not conv.data:
            return
        cid = conv.data[0]["id"]
        client.table("messages").delete().eq("conversation_id", cid).execute()
        client.table("conversations").delete().eq("id", cid).execute()
    except Exception as e:
        logger.warning(f"[MEMORY] delete_conversation : {e}")


def save_exchange(session_id: str, question: str, answer: str, user_id: str = "") -> None:
    client = _get_client()
    if not client or not session_id:
        return
    try:
        cid = _get_or_create_conversation(client, session_id, user_id)
        if not cid:
            return
        client.table("messages").insert([
            {"conversation_id": cid, "role": "user",      "content": question, "user_id": user_id},
            {"conversation_id": cid, "role": "assistant", "content": answer,   "user_id": user_id},
        ]).execute()
    except Exception as e:
        logger.warning(f"[MEMORY] save_exchange : {e}")


# ── Mémoire long-terme utilisateur ───────────────────────────────────────────

def get_user_summary(user_id: str) -> str:
    client = _get_client()
    if not client or not user_id:
        return ""
    try:
        r = client.table("user_memory").select("summary").eq("user_id", user_id).limit(1).execute()
        return r.data[0]["summary"] if r.data else ""
    except Exception as e:
        logger.warning(f"[MEMORY] get_user_summary : {e}")
        return ""


def save_user_summary(user_id: str, summary: str) -> None:
    client = _get_client()
    if not client or not user_id:
        return
    try:
        client.table("user_memory").upsert({"user_id": user_id, "summary": summary}).execute()
        logger.info(f"[MEMORY] Résumé mis à jour pour user '{user_id[:8]}…'")
    except Exception as e:
        logger.warning(f"[MEMORY] save_user_summary : {e}")


def count_user_exchanges(user_id: str) -> int:
    client = _get_client()
    if not client or not user_id:
        return 0
    try:
        r = (client.table("messages").select("id", count="exact")
             .eq("user_id", user_id).eq("role", "user").execute())
        return r.count or 0
    except Exception as e:
        logger.warning(f"[MEMORY] count_user_exchanges : {e}")
        return 0


# ── Stats dashboard ───────────────────────────────────────────────────────────

def get_stats() -> dict:
    client = _get_client()
    if not client:
        return {"error": "Supabase non configuré", "counts": {}, "events": []}
    try:
        types = ["question", "injection_regex", "injection_lakera", "rate_limit",
                 "error", "voice", "tts", "upload", "upload_blocked", "reindex", "fallback"]
        counts = {}
        for t in types:
            r = client.table("events").select("id", count="exact").eq("type", t).execute()
            counts[t] = r.count or 0

        latency_r = (client.table("events").select("latency_ms").eq("type", "question")
                     .not_.is_("latency_ms", "null").order("created_at", desc=True).limit(100).execute())
        latencies = [row["latency_ms"] for row in latency_r.data if row.get("latency_ms")]
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

        recent = client.table("events").select("*").order("created_at", desc=True).limit(50).execute()

        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        spike_r = (client.table("events").select("id", count="exact")
                   .in_("type", ["injection_regex", "injection_lakera"])
                   .gte("created_at", since).execute())

        return {
            "counts": counts, "avg_latency_ms": avg_latency,
            "injection_spike": (spike_r.count or 0) >= 10,
            "events": recent.data,
        }
    except Exception as e:
        logger.error(f"[MONITORING] get_stats : {e}")
        return {"error": str(e), "counts": {}, "events": []}
