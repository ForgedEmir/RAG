"""
Tests for conflict resolution between versions of the same subject (#175).

Rule:
  - Two files that share a name prefix (split on _ or -) are
    considered as versions of the same subject.
  - In case of a conflict during retrieval, only the file with the most
    recent indexed_at is kept.
  - Perfect tie (same indexed_at) -> both are kept, the system prompt
    asks the LLM to signal the contradiction.
"""
from src.search.search import _subject_key, _resolve_conflicts_by_recency


# ===== _subject_key =====

def test_subject_key_extrait_le_prefixe_avant_underscore():
    assert _subject_key("alaric_v1.md") == "alaric"
    assert _subject_key("alaric_v2.md") == "alaric"
    assert _subject_key("alaric_canonical.md") == "alaric"


def test_subject_key_extrait_le_prefixe_avant_tiret():
    assert _subject_key("alaric-v1.md") == "alaric"
    assert _subject_key("alaric-final.md") == "alaric"


def test_subject_key_sans_separateur_retourne_le_nom_complet():
    assert _subject_key("factions.md") == "factions"
    assert _subject_key("historique.txt") == "historique"


def test_subject_key_insensible_a_la_casse():
    assert _subject_key("Alaric_V1.md") == "alaric"
    assert _subject_key("ALARIC-final.md") == "alaric"


def test_subject_key_deux_fichiers_differents_sujets_differents():
    assert _subject_key("alaric.md") != _subject_key("elarion.md")
    assert _subject_key("factions_nord.md") != _subject_key("villes_sud.md")


# ===== _resolve_conflicts_by_recency =====

def test_resolve_un_seul_fichier_inchange():
    docs = [{"id": "1", "filename": "alaric.md", "indexed_at": 100.0, "text": "t"}]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert kept == docs
    assert ties == set()


def test_resolve_fichiers_sujets_differents_tous_conserves():
    """No conflict -> nothing is filtered."""
    docs = [
        {"id": "1", "filename": "alaric.md",  "indexed_at": 100.0, "text": "a"},
        {"id": "2", "filename": "elarion.md", "indexed_at": 50.0,  "text": "b"},
        {"id": "3", "filename": "vael.md",    "indexed_at": 200.0, "text": "c"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 3
    assert ties == set()


def test_resolve_deux_versions_meme_sujet_plus_recent_gagne():
    """alaric_v1 (old) vs alaric_v2 (recent) -> only v2 remains, no tie."""
    docs = [
        {"id": "1", "filename": "alaric_v1.md", "indexed_at": 100.0, "text": "1.70m"},
        {"id": "2", "filename": "alaric_v2.md", "indexed_at": 200.0, "text": "1.90m"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["filename"] == "alaric_v2.md"
    assert "1.90m" in kept[0]["text"]
    assert ties == set()   # no tie: v2 clearly wins


def test_resolve_tie_parfait_garde_les_deux():
    """Same indexed_at on 2 versions -> keeps both AND returns the subject in tie_subjects."""
    docs = [
        {"id": "1", "filename": "alaric_v1.md", "indexed_at": 100.0, "text": "1.70m"},
        {"id": "2", "filename": "alaric_v2.md", "indexed_at": 100.0, "text": "1.90m"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 2
    filenames = {d["filename"] for d in kept}
    assert filenames == {"alaric_v1.md", "alaric_v2.md"}
    assert "alaric" in ties   # tie subject signaled for the LLM


def test_resolve_trois_versions_seule_la_plus_recente_reste():
    docs = [
        {"id": "1", "filename": "alaric_draft.md", "indexed_at": 50.0,  "text": "v1"},
        {"id": "2", "filename": "alaric_v2.md",    "indexed_at": 100.0, "text": "v2"},
        {"id": "3", "filename": "alaric_final.md", "indexed_at": 300.0, "text": "vFinal"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["filename"] == "alaric_final.md"
    assert ties == set()


def test_resolve_conflits_sur_un_sujet_naffecte_pas_les_autres():
    """If alaric has a conflict, it must not impact elarion which doesn't have one."""
    docs = [
        {"id": "1", "filename": "alaric_v1.md",  "indexed_at": 100.0, "text": "a1"},
        {"id": "2", "filename": "alaric_v2.md",  "indexed_at": 200.0, "text": "a2"},
        {"id": "3", "filename": "elarion.md",    "indexed_at": 50.0,  "text": "e"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 2
    filenames = {d["filename"] for d in kept}
    assert filenames == {"alaric_v2.md", "elarion.md"}
    assert ties == set()


def test_resolve_preserve_lordre_initial():
    """The relative order of kept docs must be preserved (RRF/rerank ranking
    decides the relevance, not us)."""
    docs = [
        {"id": "2", "filename": "alaric_v2.md",    "indexed_at": 200.0, "text": "a2"},
        {"id": "3", "filename": "elarion.md",      "indexed_at": 50.0,  "text": "e"},
        {"id": "1", "filename": "alaric_v1.md",    "indexed_at": 100.0, "text": "a1"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert [d["id"] for d in kept] == ["2", "3"]


def test_resolve_indexed_at_manquant_traite_comme_zero():
    """Backward compat: a chunk without indexed_at (0.0) is older than anything."""
    docs = [
        {"id": "1", "filename": "alaric_legacy.md", "indexed_at": 0.0,   "text": "old"},
        {"id": "2", "filename": "alaric_new.md",    "indexed_at": 100.0, "text": "new"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["filename"] == "alaric_new.md"
    assert ties == set()
