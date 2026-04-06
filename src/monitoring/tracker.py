import os
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
INJECTION_TYPES    = ("injection_regex", "injection_lakera")
SPIKE_THRESHOLD    = 10
SPIKE_WINDOW_MIN   = 5
MAX_DETAIL_LEN     = 500
HISTORY_LIMIT      = 10
STATS_LATENCY_LIMIT = 100
STATS_EVENTS_LIMIT  = 200

_client      = None
_client_lock = threading.Lock()

def _get_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        # WHY: Double-checked locking évite de créer plusieurs clients en cas de startup concurrent.
        if _client is None and SUPABASE_URL and SUPABASE_KEY:
            from supabase import create_client
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def track(event_type: str, detail: str = "", latency_ms: Optional[int] = None) -> None:
    client = _get_client()
    if not client:
        return
    try:
        data = {"type": event_type, "detail": detail[:MAX_DETAIL_LEN]}
        if latency_ms is not None:
            data["latency_ms"] = latency_ms
        client.table("events").insert(data).execute()
        if event_type in INJECTION_TYPES:
            _check_injection_spike(client)
    except Exception as e:
        logger.warning(f"[MONITORING] Supabase : {e}")

def _check_injection_spike(client) -> None:
    try:
        since = (datetime.now(timezone.utc) - timedelta(minutes=SPIKE_WINDOW_MIN)).isoformat()
        r = (client.table("events").select("id", count="exact")
             .in_("type", INJECTION_TYPES)
             .gte("created_at", since).execute())
        if (r.count or 0) >= SPIKE_THRESHOLD:
            logger.warning(f"[MONITORING] Spike d'injections : >{SPIKE_THRESHOLD} en {SPIKE_WINDOW_MIN} minutes.")
            try:
                import sentry_sdk
                sentry_sdk.capture_message(f"Spike d'injections : >{SPIKE_THRESHOLD} en {SPIKE_WINDOW_MIN} minutes", level="warning")
            except ImportError:
                pass
    except Exception:
        pass

def _get_conv_id(client, session_id: str) -> Optional[int]:
    r = client.table("conversations").select("id").eq("session_id", session_id).limit(1).execute()
    return r.data[0]["id"] if r.data else None

def _get_or_create_conversation(client, session_id: str, user_id: str) -> Optional[int]:
    try:
        cid = _get_conv_id(client, session_id)
        if cid:
            return cid
        inserted = client.table("conversations").insert({"session_id": session_id, "user_id": user_id}).execute()
        return inserted.data[0]["id"] if inserted.data else None
    except Exception as e:
        logger.warning(f"[MEMORY] _get_or_create_conversation : {e}")
        return None

def _messages_to_history(messages: list) -> list:
    # Stabilisation de l'ordre pour pallier le non-déterminisme de Supabase sur les timestamps identiques.
    normalized = sorted(
        messages,
        key=lambda m: (str(m.get("created_at", "")), int(m.get("id", 0) or 0), 0 if m.get("role") == "user" else 1)
    ) if any(m.get("created_at") or m.get("id") for m in messages) else messages

    pairs, pending_question = [], ""
    for msg in normalized:
        content = msg.get("content", "")
        if msg.get("role") == "user":
            pending_question = content
        elif msg.get("role") == "assistant" and pending_question:
            pairs.append({"question": pending_question, "answer": content})
            pending_question = ""
    return pairs

def get_history(session_id: str) -> list:
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        cid = _get_conv_id(client, session_id)
        if not cid:
            return []
        r = (client.table("messages").select("id, role, content, created_at")
             .eq("conversation_id", cid)
             .order("created_at", desc=True)
             .limit(HISTORY_LIMIT).execute())
        return _messages_to_history(list(reversed(r.data or [])))
    except Exception as e:
        logger.warning(f"[MEMORY] get_history : {e}")
        return []

def get_conversation(session_id: str) -> list:
    client = _get_client()
    if not client or not session_id:
        return []
    try:
        cid = _get_conv_id(client, session_id)
        if not cid:
            return []
        r = (client.table("messages").select("id, role, content, created_at")
             .eq("conversation_id", cid)
             .order("created_at").execute())
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
             .eq("session_id", session_id).eq("user_id", user_id)
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
             .eq("session_id", session_id).limit(1).execute())
        return r.data[0].get("user_id", "") if r.data else ""
    except Exception as e:
        logger.warning(f"[MEMORY] get_conversation_owner : {e}")
        return ""

def delete_conversation(session_id: str) -> None:
    client = _get_client()
    if not client or not session_id:
        return
    try:
        cid = _get_conv_id(client, session_id)
        if not cid:
            return
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
        if cid:
            client.table("messages").insert([
                {"conversation_id": cid, "role": "user", "content": question, "user_id": user_id},
                {"conversation_id": cid, "role": "assistant", "content": answer, "user_id": user_id},
            ]).execute()
    except Exception as e:
        logger.warning(f"[MEMORY] save_exchange : {e}")

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

def get_user_conversations(user_id: str) -> list:
    """Returns [{id, title, created_at}] for a user, newest first.
    Uses a single join query: conversations → first user message per conversation.
    """
    client = _get_client()
    if not client or not user_id:
        return []
    try:
        # One query: conversations with their first user message via FK join
        r = (client.table("conversations")
             .select("id, session_id, created_at, messages(content, role, created_at)")
             .eq("user_id", user_id)
             .eq("messages.role", "user")
             .order("created_at", desc=True)
             .limit(50).execute())
        result = []
        for row in (r.data or []):
            msgs = row.get("messages") or []
            # Sort by created_at to get the first user message
            msgs_sorted = sorted(msgs, key=lambda m: m.get("created_at", ""))
            if msgs_sorted:
                c = msgs_sorted[0]["content"]
                title = c[:45] + ("…" if len(c) > 45 else "")
            else:
                title = "Conversation"
            result.append({"id": row["session_id"], "title": title, "created_at": row["created_at"]})
        return result
    except Exception as e:
        logger.warning(f"[MEMORY] get_user_conversations : {e}")
        return []

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

def get_stats() -> dict:
    client = _get_client()
    if not client:
        return {"error": "Supabase non configuré", "counts": {}, "events": []}
    try:
        event_types = ["question", "injection_regex", "injection_lakera", "rate_limit", "error", "voice", "tts", "upload", "upload_blocked", "reindex", "fallback"]
        counts = {t: client.table("events").select("id", count="exact").eq("type", t).execute().count or 0 for t in event_types}

        latency_r = (client.table("events").select("latency_ms").eq("type", "question")
                     .not_.is_("latency_ms", "null").order("created_at", desc=True).limit(STATS_LATENCY_LIMIT).execute())
        latencies = [row["latency_ms"] for row in latency_r.data if row.get("latency_ms")]
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

        recent = client.table("events").select("*").order("created_at", desc=True).limit(STATS_EVENTS_LIMIT).execute()
        since = (datetime.now(timezone.utc) - timedelta(minutes=SPIKE_WINDOW_MIN)).isoformat()
        spike_count = client.table("events").select("id", count="exact").in_("type", INJECTION_TYPES).gte("created_at", since).execute().count or 0

        injections_blocked = counts.get("injection_regex", 0) + counts.get("injection_lakera", 0)
        total_questions    = counts.get("question", 0)
        errors             = counts.get("error", 0)
        total_events       = total_questions + errors or 1
        error_rate_pct     = round(errors / total_events * 100, 1)

        # Médiane des latences
        sorted_lat = sorted(latencies)
        mid = len(sorted_lat) // 2
        latency_p50 = sorted_lat[mid] if sorted_lat else 0

        return {
            # Clés attendues par le frontend
            "total_questions":    total_questions,
            "latency_p50":        latency_p50,
            "injections_blocked": injections_blocked,
            "error_rate_pct":     error_rate_pct,
            "last_events":        recent.data,
            "injection_spike":    spike_count >= SPIKE_THRESHOLD,
            # Données brutes conservées
            "counts":             counts,
            "avg_latency_ms":     avg_latency,
        }
    except Exception as e:
        logger.error(f"[MONITORING] get_stats : {e}")
        return {"error": str(e), "counts": {}, "events": []}
