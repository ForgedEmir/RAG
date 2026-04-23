"""
Tests pour la résolution de conflits entre versions d'un même sujet (#175).

Règle :
  - Deux fichiers qui partagent un préfixe de nom (split sur _ ou -) sont
    considérés comme des versions d'un même sujet.
  - En cas de conflit au retrieval, seul le fichier au indexed_at le plus
    récent est conservé.
  - Tie parfait (même indexed_at) → les deux sont gardés, le system prompt
    demande au LLM de signaler la contradiction.
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
    docs = [{"id": "1", "fichier": "alaric.md", "indexed_at": 100.0, "text": "t"}]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert kept == docs
    assert ties == set()


def test_resolve_fichiers_sujets_differents_tous_conserves():
    """Aucun conflit → rien n'est filtré."""
    docs = [
        {"id": "1", "fichier": "alaric.md",  "indexed_at": 100.0, "text": "a"},
        {"id": "2", "fichier": "elarion.md", "indexed_at": 50.0,  "text": "b"},
        {"id": "3", "fichier": "vael.md",    "indexed_at": 200.0, "text": "c"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 3
    assert ties == set()


def test_resolve_deux_versions_meme_sujet_plus_recent_gagne():
    """alaric_v1 (ancien) vs alaric_v2 (récent) → seul v2 reste, pas de tie."""
    docs = [
        {"id": "1", "fichier": "alaric_v1.md", "indexed_at": 100.0, "text": "1.70m"},
        {"id": "2", "fichier": "alaric_v2.md", "indexed_at": 200.0, "text": "1.90m"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["fichier"] == "alaric_v2.md"
    assert "1.90m" in kept[0]["text"]
    assert ties == set()   # pas de tie : v2 gagne clairement


def test_resolve_tie_parfait_garde_les_deux():
    """Même indexed_at sur 2 versions → garde les 2 ET retourne le sujet dans tie_subjects."""
    docs = [
        {"id": "1", "fichier": "alaric_v1.md", "indexed_at": 100.0, "text": "1.70m"},
        {"id": "2", "fichier": "alaric_v2.md", "indexed_at": 100.0, "text": "1.90m"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 2
    fichiers = {d["fichier"] for d in kept}
    assert fichiers == {"alaric_v1.md", "alaric_v2.md"}
    assert "alaric" in ties   # sujet en tie signalé pour le LLM


def test_resolve_trois_versions_seule_la_plus_recente_reste():
    docs = [
        {"id": "1", "fichier": "alaric_draft.md", "indexed_at": 50.0,  "text": "v1"},
        {"id": "2", "fichier": "alaric_v2.md",    "indexed_at": 100.0, "text": "v2"},
        {"id": "3", "fichier": "alaric_final.md", "indexed_at": 300.0, "text": "vFinal"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["fichier"] == "alaric_final.md"
    assert ties == set()


def test_resolve_conflits_sur_un_sujet_naffecte_pas_les_autres():
    """Si alaric a un conflit, ça ne doit pas impacter elarion qui n'en a pas."""
    docs = [
        {"id": "1", "fichier": "alaric_v1.md",  "indexed_at": 100.0, "text": "a1"},
        {"id": "2", "fichier": "alaric_v2.md",  "indexed_at": 200.0, "text": "a2"},
        {"id": "3", "fichier": "elarion.md",    "indexed_at": 50.0,  "text": "e"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 2
    fichiers = {d["fichier"] for d in kept}
    assert fichiers == {"alaric_v2.md", "elarion.md"}
    assert ties == set()


def test_resolve_preserve_lordre_initial():
    """L'ordre relatif des docs gardés doit être conservé (le ranking RRF/rerank
    décide de la pertinence, pas nous)."""
    docs = [
        {"id": "2", "fichier": "alaric_v2.md",    "indexed_at": 200.0, "text": "a2"},
        {"id": "3", "fichier": "elarion.md",      "indexed_at": 50.0,  "text": "e"},
        {"id": "1", "fichier": "alaric_v1.md",    "indexed_at": 100.0, "text": "a1"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert [d["id"] for d in kept] == ["2", "3"]


def test_resolve_indexed_at_manquant_traite_comme_zero():
    """Compat ascendante : un chunk sans indexed_at (0.0) est plus vieux que tout."""
    docs = [
        {"id": "1", "fichier": "alaric_legacy.md", "indexed_at": 0.0,   "text": "old"},
        {"id": "2", "fichier": "alaric_new.md",    "indexed_at": 100.0, "text": "new"},
    ]
    kept, ties = _resolve_conflicts_by_recency(docs)
    assert len(kept) == 1
    assert kept[0]["fichier"] == "alaric_new.md"
    assert ties == set()
