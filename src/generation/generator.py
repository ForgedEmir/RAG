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
_primary_model  = os.getenv("LLM_MODEL", "llama3.1-8b")
_primary_base   = os.getenv("LLM_BASE_URL", "https://api.cerebras.ai/v1")

_fallback_key   = os.getenv("FALLBACK_API_KEY")
_fallback_model = os.getenv("FALLBACK_MODEL", "llama-3.3-70b-versatile")
_fallback_base  = os.getenv("FALLBACK_BASE_URL", "https://api.groq.com/openai/v1")

_reformulation_key   = os.getenv("REFORMULATION_API_KEY") or _api_key
_reformulation_model = os.getenv("REFORMULATION_MODEL", _primary_model)
_reformulation_base  = os.getenv("REFORMULATION_BASE_URL", _primary_base)

_CONV_DEPTH            = int(os.getenv("CONVERSATION_DEPTH", "5"))
_REFORMULATION_ENABLED = os.getenv("REFORMULATION_ENABLED", "true").lower() != "false"

_llm: Optional[ChatOpenAI] = ChatOpenAI(
    model=_primary_model,
    base_url=_primary_base,
    api_key=_api_key, temperature=0.2,
) if _api_key else None

_llm_fallback: Optional[ChatOpenAI] = ChatOpenAI(
    model=_fallback_model,
    base_url=_fallback_base,
    api_key=_fallback_key, temperature=0.2,
) if _fallback_key else None

_llm_reformulation: Optional[ChatOpenAI] = ChatOpenAI(
    model=_reformulation_model,
    base_url=_reformulation_base,
    api_key=_reformulation_key,
    temperature=0.0,
) if _reformulation_key else None

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

def _langfuse_handler(name: str = "nexus", **meta):
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


def _callbacks(name: str = "nexus", **meta) -> list:
    h = _langfuse_handler(name, **meta)
    return [h] if h else []


async def send_langfuse_score(trace_id: str, value: int, comment: str = "") -> None:
    """Envoie un score human_feedback sur la trace Langfuse liée à notre trace_id interne."""
    if not trace_id:
        return
    try:
        # Résoudre le vrai trace_id Langfuse (récupéré après le stream via handler.get_trace_id())
        from src.monitoring.tracker import get_trace_context
        ctx = await get_trace_context(trace_id)
        langfuse_id = ctx.get("langfuse_trace_id") or ""

        if not langfuse_id:
            logger.debug(f"[LANGFUSE] Pas de trace Langfuse liée à {trace_id[:8]} — score ignoré.")
            return

        if _langfuse_client is None:
            _langfuse_handler()
        if _langfuse_client:
            _langfuse_client.score(
                trace_id=langfuse_id,
                name="human_feedback",
                value=float(value),
                comment=comment or None,
            )
            logger.debug(f"[LANGFUSE] Score human_feedback={value} sur trace Langfuse {langfuse_id[:8]}")
    except Exception as e:
        logger.debug(f"[LANGFUSE] Score failed: {e}")


# ── Messages ──────────────────────────────────────────────────────────────────

def _build_messages(question: str, passages: List[str], sources: List[str],
                    history: List[dict], user_summary: str = "",
                    vector_memories: List[str] = None,
                    tie_subjects: set = None) -> list:
    contexte      = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"
    system = (
        "Tu es RABELIA, un moteur de recherche sémantique de grade production."
        "Ton rôle est d'analyser le CONTEXTE fourni pour répondre aux questions avec précision. "
        "\n\n"
        "Directives strictes : "
        "1. Ne réponds QUE sur la base du contexte fourni. "
        "2. Si l'information est absente, dis-le poliment et n'invente rien. "
        "3. En cas de contradiction entre les sources, mentionne-le explicitement. "
        "4. Cite toujours tes sources (ex: [fichier.md]) à la fin de chaque paragraphe pertinent. "
        "5. Ton ton est professionnel, neutre et analytique. "
        "\n\n"
        f"Sources : {liste_sources}\n\nContexte :\n{contexte}"
    )
    # WHY: quand plusieurs fichiers traitent du même sujet et partagent la même date
    # d'indexation, on ne peut pas savoir lequel est "officiel". On prévient le LLM
    # pour qu'il signale explicitement la divergence plutôt que de trancher arbitrairement.
    if tie_subjects:
        sujets_str = ", ".join(sorted(tie_subjects))
        system += (
            f"\n\n[AVERTISSEMENT] Plusieurs sources de même date traitent du/des sujet(s) : {sujets_str}. "
            "Il n'est pas possible de déterminer laquelle est la version officielle. "
            "Tu DOIS signaler cette ambigüité dans ta réponse en citant les deux sources et leurs informations divergentes, "
            "et inviter l'administrateur à clarifier la version de référence."
        )
    if user_summary:
        system += f"\n\nMémoire utilisateur :\n{user_summary}"
    if vector_memories:
        system += "\n\nSouvenirs précis :\n" + "\n".join(vector_memories)

    messages = [SystemMessage(content=system)]
    for ex in history[-_CONV_DEPTH:]:
        messages += [HumanMessage(content=ex["question"]), AIMessage(content=ex["answer"])]
    messages.append(HumanMessage(content=question))

    # Estimation tokens (1 token ≈ 4 chars) — log si contexte > 50k tokens
    estimated_tokens = sum(len(m.content) for m in messages) // 4
    if estimated_tokens > 50_000:
        logger.warning(f"[CONTEXT] Contexte large : ~{estimated_tokens} tokens estimés ({len(history)} msgs historique)")
    else:
        logger.debug(f"[CONTEXT] ~{estimated_tokens} tokens estimés")

    return messages


# ── LLM calls ─────────────────────────────────────────────────────────────────

async def generer_resume_utilisateur(new_exchanges: List[dict], old_summary: str = "") -> str:
    """Met à jour le résumé long-terme (max 150 mots)."""
    if not _llm or not new_exchanges:
        return old_summary
    nouveaux = "\n".join(
        f"User: {e['question']}\nAssistant: {e['answer'][:200]}" for e in new_exchanges[-5:]
    )
    context = (f"Résumé précédent :\n{old_summary}\n\nNouveaux échanges :\n{nouveaux}"
               if old_summary else f"Échanges :\n{nouveaux}")
    try:
        result = await _llm.ainvoke([
            SystemMessage(content=(
                "Tu maintiens la mémoire long-terme d'un utilisateur professionnel. "
                "Mets à jour le résumé : sujets abordés, documents consultés, préférences, objectifs. "
                "Règles : n'invente rien, 150 mots max, pas d'introduction."
            )),
            HumanMessage(content=context),
        ], config={"callbacks": _callbacks("résumé-utilisateur")})
        return result.content.strip()
    except Exception as e:
        logger.warning(f"Résumé échoué : {e}")
        return old_summary


async def reformuler_question(question: str, history: List[dict]) -> str:
    """Reformule une question vague grâce à l'historique."""
    if not _REFORMULATION_ENABLED:
        return question
    if not history:
        return question
    # Skip reformulation si la question est autonome (pas de pronom anaphorique ni référence floue)
    if len(question.split()) <= 8 and not any(
        w in question.lower() for w in ("il", "elle", "ils", "elles", "ce", "ça", "cela", "celui", "celle", "lui", "en", "y")
    ):
        return question
    # Use fast dedicated model (Groq ~500ms), fall back to primary if unavailable
    llm = _llm_reformulation or _llm_fallback or _llm
    if not llm:
        return question
    historique = "\n".join(f"User: {e['question']}\nAssistant: {e['answer']}" for e in history[-_CONV_DEPTH:])
    try:
        result = await llm.ainvoke([
            SystemMessage(content=(
                "Tu est un assistant qui reformule des questions. "
                "Retourne UNIQUEMENT la question reformulée en une seule phrase, sans répondre, sans explication, sans ponctuation finale."
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


async def generer_reponse(question: str, passages: List[str], sources: List[str] = None,
                    history: List[dict] = None, user_summary: str = "",
                    vector_memories: List[str] = None,
                    tie_subjects: set = None) -> str:
    if not _llm:
        raise ValueError("OPENAI_API_KEY manquante dans .env")
    messages = _build_messages(question, passages, sources or [], history or [], user_summary, vector_memories, tie_subjects)
    fallbacks = [llm for llm in [_llm_fallback] if llm is not None]
    chain = _llm.with_fallbacks(fallbacks)
    result = await chain.ainvoke(messages, config={"callbacks": _callbacks("ask", question=question[:80])})
    return result.content.strip()


async def stream_reponse(question: str, passages: List[str], sources: List[str] = None,
                   history: List[dict] = None, model_used: Optional[list] = None,
                   user_summary: str = "", vector_memories: List[str] = None,
                   langfuse_trace_ids: Optional[list] = None,
                   tie_subjects: set = None):
    """Streame la réponse token par token. Bascule sur le fallback si erreur."""
    if not _llm:
        raise ValueError("OPENAI_API_KEY manquante dans .env")
    messages = _build_messages(question, passages, sources or [], history or [], user_summary, vector_memories, tie_subjects)
    cb = _callbacks("ask-stream", question=question[:80])
    handler = cb[0] if cb else None
    if model_used is not None:
        model_used.append(_primary_model)

    async def _track_fallback(from_model: str, to_model: str, err: Exception) -> None:
        try:
            from src.monitoring.tracker import track
            await track("fallback", detail=f"{from_model} → {to_model} | {str(err)[:100]}")
        except Exception:
            pass

    _fallback_chain = [
        (_llm_fallback, _fallback_model, "fallback"),
    ]

    try:
        async for chunk in _llm.astream(messages, config={"callbacks": cb}):
            if chunk.content:
                yield chunk.content
    except Exception as primary_err:
        err_str = str(primary_err).lower()
        is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str or "too many" in err_str
        is_timeout    = "timeout" in err_str or "timed out" in err_str or "read timeout" in err_str
        if is_rate_limit:
            logger.warning(f"[FALLBACK] Cerebras rate-limited (429) — bascule sur Groq.")
        elif is_timeout:
            logger.warning(f"[FALLBACK] Cerebras timeout — bascule sur Groq.")
        else:
            logger.warning(
                f"[FALLBACK] Cerebras KO ({primary_err.__class__.__name__}: "
                f"{str(primary_err)[:120]}) — bascule sur Groq."
            )

        last_err = primary_err
        for fb_llm, fb_model, fb_label in _fallback_chain:
            if fb_llm is None:
                continue
            if model_used is not None:
                model_used[0] = f"{fb_model} [{fb_label}]"
            await _track_fallback(_primary_model, fb_model, last_err)
            try:
                async for chunk in fb_llm.astream(messages, config={"callbacks": _callbacks(fb_label)}):
                    if chunk.content:
                        yield chunk.content
                logger.info(f"[FALLBACK] Groq ({fb_model}) a pris le relais avec succès.")
                return
            except Exception as fb_err:
                last_err = fb_err
                logger.warning(f"[FALLBACK] Groq ({fb_model}) aussi KO : {fb_err}")
        raise last_err
    finally:
        # Récupère l'ID de trace Langfuse généré par le handler (v4 API)
        if langfuse_trace_ids is not None and handler is not None:
            try:
                lf_id = handler.get_trace_id()
                if lf_id:
                    langfuse_trace_ids.append(str(lf_id))
            except Exception:
                pass
