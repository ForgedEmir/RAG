"""Génère les réponses via LLM. Langfuse pour le tracing. Fallback automatique."""
import os
import logging
import importlib
import threading
from collections import deque
from typing import List, Optional, Iterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_api_key        = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
_primary_model  = os.getenv("LLM_MODEL", "deepseek-chat")
_fallback_key   = os.getenv("FALLBACK_API_KEY")
_fallback_model = os.getenv("FALLBACK_MODEL", "llama-3.1-8b-instant")
_CONV_DEPTH     = int(os.getenv("CONVERSATION_DEPTH", "5"))
_REFORMULATION_ENABLED = os.getenv("REFORMULATION_ENABLED", "true").lower() != "false"

# Dedicated Groq fallback (GROQ_API_KEY takes precedence over the generic
# FALLBACK_API_KEY so projects can use separate credentials for each tier).
_groq_api_key   = os.getenv("GROQ_API_KEY")
_groq_model     = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Hardcoded free tier: OpenRouter's free mixtral route (no key needed for
# low-volume usage; requests that fail here raise normally).
_FREE_FALLBACK_BASE_URL = "https://openrouter.ai/api/v1"
_FREE_FALLBACK_MODEL    = "mistralai/mistral-7b-instruct:free"

_llm: Optional[ChatOpenAI] = ChatOpenAI(
    model=_primary_model,
    base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=_api_key, temperature=0.2,
) if _api_key else None

_llm_fallback: Optional[ChatOpenAI] = ChatOpenAI(
    model=_fallback_model,
    base_url=os.getenv("FALLBACK_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=_fallback_key, temperature=0.2,
) if _fallback_key else None

# Groq-specific fallback (second tier — used when both primary and
# _llm_fallback fail, or when GROQ_API_KEY is set independently).
_llm_groq: Optional[ChatOpenAI] = ChatOpenAI(
    model=_groq_model,
    base_url="https://api.groq.com/openai/v1",
    api_key=_groq_api_key, temperature=0.2,
) if _groq_api_key else None

# Third-tier free fallback via OpenRouter (requires auth since 2025-Q4).
_llm_free: Optional[ChatOpenAI] = ChatOpenAI(
    model=_FREE_FALLBACK_MODEL,
    base_url=_FREE_FALLBACK_BASE_URL,
    api_key=_api_key or _fallback_key or "no-key",
    temperature=0.2,
) if (_api_key or _fallback_key) else None

# Dedicated fast LLM for reformulation (cheap, low-latency ~500ms).
# Uses Groq by default (llama-3.1-8b-instant). Falls back gracefully to
# _llm_fallback then _llm so reformulation never breaks when Groq is unavailable.
_reformulation_model = os.getenv("REFORMULATION_MODEL", "llama-3.1-8b-instant")
_llm_reformulation: Optional[ChatOpenAI] = ChatOpenAI(
    model=_reformulation_model,
    base_url="https://api.groq.com/openai/v1",
    api_key=_groq_api_key,
    temperature=0.0,  # deterministic reformulation
) if _groq_api_key else None

_LANGFUSE_LOGGED    = False
_langfuse_client    = None
_langfuse_lock      = threading.Lock()


_reformulation_history: deque = deque(maxlen=50)

def get_reformulation_enabled() -> bool:
    return _REFORMULATION_ENABLED

def get_reformulation_history() -> list:
    return list(_reformulation_history[-20:])


def set_reformulation_enabled(enabled: bool) -> bool:
    global _REFORMULATION_ENABLED
    _REFORMULATION_ENABLED = bool(enabled)
    logger.info("Reformulation %s", "activée" if _REFORMULATION_ENABLED else "désactivée")
    return _REFORMULATION_ENABLED


# ── Langfuse (optionnel) ──────────────────────────────────────────────────────

def _langfuse_handler(name: str = "lorekeeper", **meta):
    """Retourne un callback Langfuse si configuré, sinon None."""
    global _LANGFUSE_LOGGED

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        if not _LANGFUSE_LOGGED:
            logger.info("Langfuse désactivé (LANGFUSE_PUBLIC_KEY/SECRET_KEY manquantes).")
            _LANGFUSE_LOGGED = True
        return None

    try:
        global _langfuse_client
        with _langfuse_lock:
            try:
                # Langfuse v2 (legacy path)
                CallbackHandler = importlib.import_module("langfuse.callback").CallbackHandler
                handler = CallbackHandler(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                    trace_name=name,
                    metadata=meta,
                )
            except Exception:
                # Langfuse récent (langchain integration)
                from langfuse import Langfuse
                from langfuse.langchain import CallbackHandler
                if _langfuse_client is None:
                    _langfuse_client = Langfuse(
                        public_key=public_key,
                        secret_key=secret_key,
                        host=host,
                    )
                handler = CallbackHandler(public_key=public_key)

        if not _LANGFUSE_LOGGED:
            logger.info(f"Langfuse activé sur {host}")
            _LANGFUSE_LOGGED = True
        return handler
    except Exception as e:
        logger.warning(
            "Langfuse indisponible : %s. Vérifie `pip install langfuse langchain` et les clés LANGFUSE_*." % e
        )
        return None


def _callbacks(name: str = "lorekeeper", **meta) -> list:
    h = _langfuse_handler(name, **meta)
    return [h] if h else []


# ── Messages ──────────────────────────────────────────────────────────────────

def _build_messages(question: str, passages: List[str], sources: List[str],
                    history: List[dict], user_summary: str = "",
                    vector_memories: List[str] = None) -> list:
    contexte      = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"
    system = (
        "Tu es l'Oracle des Archives, gardien du lore du jeu Aethelgard Online. "
        "Réponds uniquement en te basant sur le contexte ci-dessous. "
        "N'invente rien. Si l'information est absente du contexte, dis-le honnêtement. "
        "Utilise des paragraphes pour narrer et des tirets (-) pour les listes. Évite les astérisques. "
        f"Sources : {liste_sources}\n\nContexte :\n{contexte}"
    )
    if user_summary:
        system += f"\n\nMémoire utilisateur :\n{user_summary}"
    if vector_memories:
        system += "\n\nSouvenirs précis :\n" + "\n".join(vector_memories)

    messages = [SystemMessage(content=system)]
    for ex in history[-_CONV_DEPTH:]:
        messages += [HumanMessage(content=ex["question"]), AIMessage(content=ex["answer"])]
    messages.append(HumanMessage(content=question))
    return messages


# ── LLM calls ─────────────────────────────────────────────────────────────────

def generer_resume_utilisateur(new_exchanges: List[dict], old_summary: str = "") -> str:
    """Met à jour le résumé long-terme (max 150 mots)."""
    if not _llm or not new_exchanges:
        return old_summary
    nouveaux = "\n".join(
        f"User: {e['question']}\nAssistant: {e['answer'][:200]}" for e in new_exchanges[-5:]
    )
    context = (f"Résumé précédent :\n{old_summary}\n\nNouveaux échanges :\n{nouveaux}"
               if old_summary else f"Échanges :\n{nouveaux}")
    try:
        result = _llm.invoke([
            SystemMessage(content=(
                "Tu maintiens la mémoire long-terme d'un joueur dans un jeu de rôle. "
                "Mets à jour le résumé : faits importants, personnages/lieux, préférences, objectifs. "
                "Règles : n'invente rien, 150 mots max, pas d'introduction."
            )),
            HumanMessage(content=context),
        ], config={"callbacks": _callbacks("résumé-utilisateur")})
        return result.content.strip()
    except Exception as e:
        logger.warning(f"Résumé échoué : {e}")
        return old_summary


def reformuler_question(question: str, history: List[dict]) -> str:
    """Reformule une question vague grâce à l'historique."""
    if not _REFORMULATION_ENABLED:
        return question
    if not history:
        return question
    # Skip reformulation pour questions courtes sans historique pertinent — économise un appel LLM
    if len(question.split()) <= 5 and len(history) <= 1:
        return question
    # Use fast dedicated model (Groq ~500ms), fall back to primary if unavailable
    llm = _llm_reformulation or _llm_fallback or _llm
    if not llm:
        return question
    historique = "\n".join(f"User: {e['question']}\nAssistant: {e['answer']}" for e in history[-_CONV_DEPTH:])
    try:
        result = llm.invoke([
            SystemMessage(content=(
                "Reformule la question en version autonome et précise grâce à l'historique. "
                "Retourne uniquement la question reformulée, sans explication."
            )),
            HumanMessage(content=f"Historique :\n{historique}\n\nQuestion : {question}"),
        ], config={"callbacks": _callbacks("reformulation", model=_reformulation_model)})
        reformulated = result.content.strip()
        logger.info(f"Reformulée ({_reformulation_model}) : {reformulated!r}")
        _reformulation_history.append({"original": question, "reformulated": reformulated})
        return reformulated
    except Exception as e:
        logger.warning(f"Reformulation échouée ({_reformulation_model}) : {e}")
        return question


def generer_reponse(question: str, passages: List[str], sources: List[str] = None,
                    history: List[dict] = None, user_summary: str = "",
                    vector_memories: List[str] = None) -> str:
    if not _llm:
        raise ValueError("OPENAI_API_KEY manquante dans .env")
    messages = _build_messages(question, passages, sources or [], history or [], user_summary, vector_memories)
    _sync_chain = [
        (_llm,          _primary_model,       "ask"),
        (_llm_fallback, _fallback_model,       "fallback"),
        (_llm_groq,     _groq_model,           "groq-fallback"),
        (_llm_free,     _FREE_FALLBACK_MODEL,  "free-fallback"),
    ]
    last_err: Exception = ValueError("No LLM available")
    for fb_llm, fb_model, fb_label in _sync_chain:
        if fb_llm is None:
            continue
        try:
            return fb_llm.invoke(messages, config={"callbacks": _callbacks(fb_label, question=question[:80])}).content.strip()
        except Exception as e:
            logger.warning(f"generer_reponse: {fb_label} ({fb_model}) failed — {e}")
            last_err = e
    raise last_err


def stream_reponse(question: str, passages: List[str], sources: List[str] = None,
                   history: List[dict] = None, model_used: Optional[list] = None,
                   user_summary: str = "", vector_memories: List[str] = None) -> Iterator[str]:
    """Streame la réponse token par token. Bascule sur le fallback si erreur."""
    if not _llm:
        raise ValueError("OPENAI_API_KEY manquante dans .env")
    messages = _build_messages(question, passages, sources or [], history or [], user_summary, vector_memories)
    cb = _callbacks("ask-stream", question=question[:80])
    if model_used is not None:
        model_used.append(_primary_model)
    def _track_fallback(from_model: str, to_model: str, err: Exception) -> None:
        try:
            from src.monitoring.tracker import track
            track("fallback", detail=f"{from_model} → {to_model} | {str(err)[:100]}")
        except Exception:
            pass

    # Build ordered fallback chain: primary is already tried above;
    # remaining tiers: OpenRouter fallback → Groq → free OpenRouter model.
    _fallback_chain = [
        (_llm_fallback, _fallback_model, "fallback"),
        (_llm_groq,     _groq_model,     "groq-fallback"),
        (_llm_free,     _FREE_FALLBACK_MODEL, "free-fallback"),
    ]

    try:
        for chunk in _llm.stream(messages, config={"callbacks": cb}):
            if chunk.content:
                yield chunk.content
    except Exception as primary_err:
        last_err = primary_err
        for fb_llm, fb_model, fb_label in _fallback_chain:
            if fb_llm is None:
                continue
            logger.warning(f"LLM KO ({last_err}), trying {fb_label} → {fb_model}")
            if model_used is not None:
                model_used[0] = f"{fb_model} [{fb_label}]"
            _track_fallback(_primary_model, fb_model, last_err)
            try:
                for chunk in fb_llm.stream(messages, config={"callbacks": _callbacks(fb_label)}):
                    if chunk.content:
                        yield chunk.content
                return  # success — stop iterating the chain
            except Exception as fb_err:
                last_err = fb_err
                logger.warning(f"{fb_label} also failed: {fb_err}")
        raise last_err
