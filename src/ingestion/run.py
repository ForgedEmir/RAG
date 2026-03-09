"""
Le maestro du projet.
C'est le script qui orchestre toute la chaine de traitement (l'ingestion de donnees).
Il repere quelles archives sont nouvelles ou modifiees, les fait lire par le parser,
les fait decouper par le chunker, puis les fait stocker dans Qdrant via LangChain.
"""
import os
import json
import logging
from typing import List, Set

from dotenv import load_dotenv
from langchain_core.documents import Document
from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.vector_store import get_store, add_documents, remove_files

load_dotenv()
logger = logging.getLogger(__name__)

# Choix du parser via variable d'environnement
# "unstructured" = Unstructured.io (recommande), "custom" = parser maison (fallback)
PARSER_MODE = os.getenv("PARSER", "unstructured")

# On part du principe que nos archives de lore sont dans le dossier data/sample/
DATA_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))

# Pour eviter de relire tous les fichiers a chaque fois qu'on lance l'app,
# on se cree un petit carnet de notes (JSON) avec la date de derniere modif de chaque fichier.
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "qdrant_db", "files_metadata.json")

# Les formats demandes par le cahier des charges de Marcus
SUPPORTED_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".xlsx", ".xml")


#  FONCTIONS UTILITAIRES DE GESTION DE LA MEMOIRE

def load_memory() -> dict:
    """Lit notre petit carnet de notes pour savoir ce qu'on a deja traite."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_memory(fichiers: dict) -> None:
    """Met a jour notre carnet de notes avec les dernieres dates de modif."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(fichiers, f, indent=2)


def list_current_files() -> dict:
    """
    Jette un oeil dans le dossier data/ et note la date de chaque fichier.
    Format de retour : { "persos.md": 1705322941.5, ... }
    """
    fichiers = {}
    if os.path.exists(DATA_FOLDER):
        for nom in os.listdir(DATA_FOLDER):
            if nom.lower().endswith(SUPPORTED_EXTENSIONS):
                chemin = os.path.join(DATA_FOLDER, nom)
                fichiers[nom] = os.path.getmtime(chemin)
    return fichiers


def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[Document]:
    """
    Le pipeline de bout en bout pour une liste de fichiers donnes.
    On lit -> on nettoie -> on decoupe -> on retourne des Documents LangChain.
    """
    documents = []

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue

        try:
            # 1. Extraction du texte selon le parser choisi
            if PARSER_MODE == "unstructured":
                from src.ingestion.document_loader import extract_text_with_unstructured
                texte_propre = extract_text_with_unstructured(chemin)
            else:
                # Fallback : parser maison
                texte_brut = extract_text_from_file(chemin)
                texte_propre = clean_text(texte_brut) if texte_brut else None

            if not texte_propre:
                continue

            # 3. On demande au chunker d'en faire des paragraphes optimises
            petits_morceaux = split_into_chunks(texte_propre)

            # 4. On transforme chaque morceau en Document LangChain
            for morceau in petits_morceaux:
                documents.append(Document(
                    page_content=morceau,
                    metadata={"fichier": nom}
                ))

        except Exception as e:
            logger.error(f"Erreur imprevue pendant le traitement de {nom} : {e}")
            continue

    return documents


#  FONCTION PRINCIPALE D'ORCHESTRATION


def index_data(force_reindex: bool = False) -> bool:
    """
    C'est la methode qu'on appelle depuis main.py au demarrage.
    Elle est suffisamment intelligente pour ne travailler que sur ce qui a change.
    """
    logger.info("Verification des archives de lore en cours...")

    fichiers_actuels = list_current_files()

    # --- CAS 1 : On nous demande explicitement de tout reconstruire ---
    if force_reindex:
        logger.info("Destruction de la memoire et reindexation totale...")
        documents = prepare_files_for_ai(set(fichiers_actuels.keys()))
        if documents:
            store = get_store(force_reindex=True)
            add_documents(store, documents)
            save_memory(fichiers_actuels)
            logger.info("Fin de la reconstruction de la base !")
            return True
        else:
            logger.warning("Rien de valide n'a ete trouve pour peupler la base.")
            return False

    # --- CAS 2 : On fait une petite mise a jour intelligente ---
    memoire = load_memory()

    fichiers_actuels_set = set(fichiers_actuels.keys())
    fichiers_memoire_set = set(memoire.keys())

    fichiers_supprimes = fichiers_memoire_set - fichiers_actuels_set
    fichiers_nouveaux = fichiers_actuels_set - fichiers_memoire_set

    # Un fichier est considere comme "modifie" si sa date reelle est plus recente que dans notre carnet
    fichiers_modifies = {
        nom for nom in (fichiers_actuels_set & fichiers_memoire_set)
        if fichiers_actuels[nom] > memoire[nom]
    }

    changements = False
    store = get_store(force_reindex=False)

    # Etape A: Si un fichier a disparu ou ete modifie, on commence par retirer sa vieille version
    a_supprimer = fichiers_supprimes | fichiers_modifies
    if a_supprimer:
        logger.info(f"On nettoie les anciennes traces de {len(a_supprimer)} fichier(s)...")
        remove_files(store, a_supprimer)
        changements = True

    # Etape B: On ajoute les nouveaux fichiers et les versions mises a jour
    a_ajouter = fichiers_nouveaux | fichiers_modifies
    if a_ajouter:
        logger.info(f"Traitement de {len(a_ajouter)} nouveau(x) fichier(s)...")
        documents = prepare_files_for_ai(a_ajouter)
        add_documents(store, documents)
        changements = True

    # Bilan
    if changements:
        save_memory(fichiers_actuels)
        logger.info("Mise a jour incrementale terminee avec succes.")
        return True
    else:
        logger.info("Rien n'a bouge. Les archives sont toujours a jour.")
        return False


if __name__ == "__main__":
    # Test local rapide si jamais on execute juste ce fichier
    index_data(force_reindex=False)
