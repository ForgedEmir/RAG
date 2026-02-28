"""
Module run (orchestrateur) : gère tout le processus d'ingestion des données.
- Lit les fichiers du dossier data/
- Détecte les fichiers nouveaux, modifiés ou supprimés
- Met à jour la base de données ChromaDB automatiquement
"""
import os
import json
import logging
from typing import List, Set

# Détection de l'environnement Vercel (serverless, filesystem read-only)
IS_VERCEL = os.environ.get("VERCEL") == "1"

from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.loader import (
    store_in_chromadb,
    add_to_chromadb,
    remove_files_from_chromadb,
    _get_collection
)

# Créer un logger pour ce module
logger = logging.getLogger(__name__)

# Chemin vers le dossier contenant les fichiers de données
DATA_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))

# Fichier JSON qui "se souvient" des fichiers déjà traités
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chroma_db", "files_metadata.json")

# Types de fichiers acceptés (Marcus demande MD, TXT, CSV, JSON et Excel)
SUPPORTED_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".xlsx")


# ============================================================
#  FONCTIONS UTILITAIRES
# ============================================================

def load_memory() -> dict:
    """Charge la mémoire des fichiers déjà traités (depuis le fichier JSON)."""
    if IS_VERCEL:
        return {}  # Pas de mémoire persistante sur Vercel
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_memory(fichiers: dict) -> None:
    """Sauvegarde la liste des fichiers traités pour la prochaine exécution."""
    if IS_VERCEL:
        return  # Pas d'écriture sur Vercel (filesystem read-only)
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(fichiers, f, indent=2)


def list_current_files() -> dict:
    """
    Scanne le dossier data/ et retourne un dictionnaire :
    { "nom_fichier.md": date_de_modification, ... }
    """
    fichiers = {}
    if os.path.exists(DATA_FOLDER):
        for nom in os.listdir(DATA_FOLDER):
            if nom.lower().endswith(SUPPORTED_EXTENSIONS):
                chemin = os.path.join(DATA_FOLDER, nom)
                fichiers[nom] = os.path.getmtime(chemin)
    return fichiers


def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[dict]:
    """
    Pour chaque fichier donné :
    1. Extrait le texte (peu importe le format)
    2. Nettoie les balises et variables
    3. Découpe en petits morceaux
    Retourne une liste de dictionnaires {"texte": ..., "fichier": ...}
    """
    morceaux = []

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue

        try:
            # Étape 1 : lire le fichier (TXT, MD, CSV, JSON ou Excel)
            texte_brut = extract_text_from_file(chemin)
            if not texte_brut:
                continue

            # Étape 2 : nettoyer les balises HTML et variables
            texte_propre = clean_text(texte_brut)
            if not texte_propre:
                continue

            # Étape 3 : découper en morceaux pour la base de données
            petits_morceaux = split_into_chunks(texte_propre)

            for morceau in petits_morceaux:
                morceaux.append({"texte": morceau, "fichier": nom})

        except Exception as e:
            # Si un fichier pose problème, on le loggue et on continue
            logger.error(f"Erreur au traitement de {nom} : {e}")
            continue

    return morceaux


# ============================================================
#  FONCTION PRINCIPALE
# ============================================================

def index_data(force_reindex: bool = False) -> bool:
    """
    Fonction principale d'indexation.
    - Si force_reindex=True : tout recréer de zéro
    - Sinon : ne traiter que les fichiers nouveaux ou modifiés
    """
    logger.info("Lancement de l'indexation...")

    fichiers_actuels = list_current_files()

    # --- CAS 1 : Réindexation forcée (tout refaire) ---
    if force_reindex:
        logger.info("Réindexation complète en cours...")
        morceaux = prepare_files_for_ai(set(fichiers_actuels.keys()))
        if morceaux:
            store_in_chromadb(morceaux, force_reindex=True)
            save_memory(fichiers_actuels)
            logger.info("Indexation complète terminée.")
            return True
        else:
            logger.warning("Aucun fichier valide trouvé.")
            return False

    # --- CAS 2 : Mise à jour intelligente (seulement ce qui a changé) ---
    memoire = load_memory()

    fichiers_actuels_set = set(fichiers_actuels.keys())
    fichiers_memoire_set = set(memoire.keys())

    # Trouver les différences avec des opérations sur les ensembles (sets)
    fichiers_supprimes = fichiers_memoire_set - fichiers_actuels_set
    fichiers_nouveaux = fichiers_actuels_set - fichiers_memoire_set
    fichiers_modifies = {
        nom for nom in (fichiers_actuels_set & fichiers_memoire_set)
        if fichiers_actuels[nom] > memoire[nom]
    }

    changements = False
    collection = _get_collection(force_reindex=False)

    # Étape A : supprimer les anciens contenus de la base
    a_supprimer = fichiers_supprimes | fichiers_modifies
    if a_supprimer:
        logger.info(f"Nettoyage de {len(a_supprimer)} fichier(s)...")
        remove_files_from_chromadb(collection, a_supprimer)
        changements = True

    # Étape B : ajouter les nouveaux contenus
    a_ajouter = fichiers_nouveaux | fichiers_modifies
    if a_ajouter:
        logger.info(f"Indexation de {len(a_ajouter)} fichier(s)...")
        morceaux = prepare_files_for_ai(a_ajouter)
        add_to_chromadb(collection, morceaux)
        changements = True

    if changements:
        save_memory(fichiers_actuels)
        logger.info("Base de données mise à jour.")
        return True
    else:
        logger.info("La base de données est déjà à jour.")
        return False


if __name__ == "__main__":
    index_data(force_reindex=False)