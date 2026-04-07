"""Tests unitaires pour l'apprentissage par feedback (boost/pénalité RAG)."""

from src.feedback import learning


def _reset_learning(tmp_path):
    learning._STATE = None
    learning._STATE_PATH = str(tmp_path / "feedback_learning_test.json")


def test_feedback_learning_records_trace_and_feedback(tmp_path):
    _reset_learning(tmp_path)

    learning.register_trace_context(
        trace_id="trace-1",
        user_id="u1",
        question="Qui est Lucas ?",
        passages=["Lucas est un mage."],
        sources=["lucas.txt"],
        chunk_ids=["lucas_0"],
    )

    meta = learning.record_feedback_event(
        trace_id="trace-1",
        user_id="u1",
        value=1,
        question="Qui est Lucas ?",
        message="Bonne reponse",
    )

    assert meta["matched_trace"] is True
    assert meta["sources_count"] == 1
    assert meta["chunks_count"] == 1


def test_feedback_learning_reranks_docs_from_votes(tmp_path):
    _reset_learning(tmp_path)

    learning.register_trace_context(
        trace_id="trace-neg",
        user_id="u1",
        question="Qui est Lucas ?",
        passages=["Texte A"],
        sources=["mauvaise_source.md"],
        chunk_ids=["bad_1"],
    )
    learning.record_feedback_event(trace_id="trace-neg", user_id="u1", value=-1)

    learning.register_trace_context(
        trace_id="trace-pos",
        user_id="u1",
        question="Qui est Lucas ?",
        passages=["Texte B"],
        sources=["bonne_source.md"],
        chunk_ids=["good_1"],
    )
    learning.record_feedback_event(trace_id="trace-pos", user_id="u1", value=1)

    docs = [
        {"id": "bad_1", "fichier": "mauvaise_source.md", "text": "A"},
        {"id": "good_1", "fichier": "bonne_source.md", "text": "B"},
    ]

    reranked, meta = learning.rerank_documents_with_feedback("Qui est Lucas exactement ?", "u1", docs)

    assert meta["matched_feedbacks"] >= 1
    assert reranked[0]["id"] == "good_1"
