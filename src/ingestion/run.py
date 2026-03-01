"""
Le maestro du projet.
C'est le script qui orchestre toute la chaîne de traitement (l'ingestion de données).
Il repère quelles archives sont nouvelles ou modifiées, les fait lire par le `parser`, 
les fait découper par le `chunker`, puis les fait stocker par le `loader`.
"""
import os
import json
import logging
from typing import List, Set

from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.loader import (
    store_in_chromadb,
    add_to_chromadb,
    remove_files_from_chromadb,
    _get_collection
)

logger = logging.getLogger(__name__)

# On part du principe que nos archives de lore sont dans le dossier data/sample/
DATA_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))

# Pour éviter de relire tous les fichiers à chaque fois qu'on lance l'app,
# on se crée un petit carnet de notes (JSON) avec la date de dernière modif de chaque fichier.
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chroma_db", "files_metadata.json")

# Les formats demandés par le cahier des charges de Marcus/Emir
SUPPORTED_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".xlsx")


#  FONCTIONS UTILITAIRES DE GESTION DE LA MEMOIRE

def load_memory() -> dict:
    """Lit notre petit carnet de notes pour savoir ce qu'on a déjà traité."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_memory(fichiers: dict) -> None:
    """Met à jour notre carnet de notes avec les dernières dates de modif."""
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


def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[dict]:
    """
    Le pipeline de bout en bout pour une liste de fichiers donnés.
    On lit -> on nettoie -> on découpe.
    """
    morceaux = []

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue

        try:
            # 1. On donne le fichier au parser pour qu'il le traduise en texte brut
            texte_brut = extract_text_from_file(chemin)
            if not texte_brut:
                continue

            # 2. On enlève toute la tuyauterie HTML/Jeu
            texte_propre = clean_text(texte_brut)
            if not texte_propre:
                continue

            # 3. On demande au chunker d'en faire des paragraphes taillés pour ChromaDB
            petits_morceaux = split_into_chunks(texte_propre)

            for morceau in petits_morceaux:
                morceaux.append({"texte": morceau, "fichier": nom})

        except Exception as e:
            logger.error(f"Erreur imprévue pendant le traitement de {nom} : {e}")
            continue

    return morceaux


#  FONCTION PRINCIPALE D'ORCHESTRATION


def index_data(force_reindex: bool = False) -> bool:
    """
    C'est la méthode qu'on appelle depuis main.py au démarrage.
    Elle est suffisamment intelligente pour ne travailler que sur ce qui a changé.
    """
    logger.info("Vérification des archives de lore en cours...")

    fichiers_actuels = list_current_files()

    # --- CAS 1 : On nous demande explicitement de tout reconstruire ---
    if force_reindex:
        logger.info("Destruction de la mémoire et réindexation totale...")
        morceaux = prepare_files_for_ai(set(fichiers_actuels.keys()))
        if morceaux:
            store_in_chromadb(morceaux, force_reindex=True)
            save_memory(fichiers_actuels)
            logger.info("Fin de la reconstruction de la base !")
            return True
        else:
            logger.warning("Rien de valide n'a été trouvé pour peupler la base.")
            return False

    # --- CAS 2 : On fait une petite mise à jour intelligente ---
    memoire = load_memory()

    # Les 'sets' de Python sont parfaits pour trouver rapidement
    # ce qui a été ajouté, retiré, ou modifié.
    fichiers_actuels_set = set(fichiers_actuels.keys())
    fichiers_memoire_set = set(memoire.keys())

    fichiers_supprimes = fichiers_memoire_set - fichiers_actuels_set
    fichiers_nouveaux = fichiers_actuels_set - fichiers_memoire_set
    
    # Un fichier est considéré comme "modifié" si sa date réelle est plus récente que dans notre carnet
    fichiers_modifies = {
        nom for nom in (fichiers_actuels_set & fichiers_memoire_set)
        if fichiers_actuels[nom] > memoire[nom]
    }

    changements = False
    collection = _get_collection(force_reindex=False)

    # Étape A: Si un fichier a disparu ou été modifié, on commence par retirer sa vieille version de ChromeDB
    a_supprimer = fichiers_supprimes | fichiers_modifies
    if a_supprimer:
        logger.info(f"On nettoie les anciennes traces de {len(a_supprimer)} fichier(s)...")
        remove_files_from_chromadb(collection, a_supprimer)
        changements = True

    # Étape B: On donne au loader les tout nouveaux fichiers, ainsi que les nouvelles versions fraîchement corrigées
    a_ajouter = fichiers_nouveaux | fichiers_modifies
    if a_ajouter:
        logger.info(f"Traitement de {len(a_ajouter)} nouveau(x) fichier(s)...")
        morceaux = prepare_files_for_ai(a_ajouter)
        add_to_chromadb(collection, morceaux)
        changements = True

    # Bilan
    if changements:
        save_memory(fichiers_actuels)
        logger.info("Mise à jour incrémentale terminée avec succès.")
        return True
    else:
        logger.info("Rien n'a bougé. Les archives sont toujours à jour.")
        return False


if __name__ == "__main__":
    # Test local rapide si jamais on exécute juste ce fichier
    index_data(force_reindex=False)
