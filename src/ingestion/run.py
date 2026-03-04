"""
Le maestro du projet.
C'est le script qui orchestre toute la chaîne de traitement (l'ingestion de données).
Il repère quelles archives sont nouvelles ou modifiées, les fait lire par le `parser`, 
les fait découper par le `chunker`, puis les fait stocker par le `loader`.
"""
import os
import json
import logging
from typing import List, Set, Dict

from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.loader import (
    store_in_chromadb,
    add_to_chromadb,
    remove_files_from_chromadb,
    _get_collection
)
from src.ingestion.validator import validate_file, ValidationResult

logger = logging.getLogger(__name__)

# On part du principe que nos archives de lore sont dans le dossier data/sample/
DATA_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))

# Pour éviter de relire tous les fichiers à chaque fois qu'on lance l'app,
# on se crée un petit carnet de notes (JSON) avec la date de dernière modif de chaque fichier.
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "chroma_db", "files_metadata.json")

# Les formats demandés par le cahier des charges de Marcus/Emir
SUPPORTED_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".xlsx", ".xml")

# Variables globales pour tracker les fichiers ignorés et rejetés
ignored_files = []
rejected_files = []


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
    Logs les fichiers avec des extensions non supportées.
    """
    global ignored_files
    ignored_files = []  # Réinitialiser la liste
    fichiers = {}
    
    if os.path.exists(DATA_FOLDER):
        for nom in os.listdir(DATA_FOLDER):
            chemin = os.path.join(DATA_FOLDER, nom)
            
            # Ignorer les dossiers
            if os.path.isdir(chemin):
                continue
            
            # Vérifier l'extension
            _, extension = os.path.splitext(nom)
            extension_lower = extension.lower()
            
            if extension_lower in [ext.lower() for ext in SUPPORTED_EXTENSIONS]:
                # Fichier supporté
                fichiers[nom] = os.path.getmtime(chemin)
            else:
                # Fichier non supporté
                formats_supportes = ", ".join(SUPPORTED_EXTENSIONS)
                logger.warning(
                    f"Fichier ignoré : '{nom}' (extension '{extension_lower}' non supportée). "
                    f"Formats acceptés : {formats_supportes}"
                )
                ignored_files.append({"nom": nom, "extension": extension_lower})
    
    return fichiers


def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[dict]:
    """
    Le pipeline de bout en bout pour une liste de fichiers donnés.
    On valide -> on lit -> on nettoie -> on découpe.
    """
    global rejected_files
    morceaux = []
    validation_results = {}

    # Étape 0 : Validation de tous les fichiers
    logger.info(f"Validation de {len(noms_fichiers)} fichier(s) avant traitement...")
    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue
        
        # Valider le fichier
        validation_result = validate_file(chemin)
        validation_results[nom] = validation_result
        
        if not validation_result.is_valid:
            rejected_files.append({
                "nom": nom,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings
            })
            logger.error(f"Fichier rejeté : {nom}")
            for error in validation_result.errors:
                logger.error(f"  ✗ {error}")
    
    # Filtrer les fichiers valides
    valid_files = {nom for nom, result in validation_results.items() if result.is_valid}
    rejected_count = len(noms_fichiers) - len(valid_files)
    
    if rejected_count > 0:
        logger.warning(f"{rejected_count} fichier(s) rejeté(s) après validation")
    
    logger.info(f"{len(valid_files)} fichier(s) valide(s) seront traités")

    # Étape 1-3 : Traitement des fichiers valides
    for nom in valid_files:
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


def log_rejected_files_summary():
    """
    Affiche un récapitulatif des fichiers rejetés à cause de la validation.
    """
    global rejected_files
    
    if rejected_files:
        logger.error("="*60)
        logger.error(f"FICHIERS REJETÉS : {len(rejected_files)} fichier(s) non conforme(s)")
        logger.error("="*60)
        
        for file_info in rejected_files:
            logger.error(f"\n  ✗ {file_info['nom']}")
            for error in file_info['errors']:
                logger.error(f"      → {error}")
            if file_info['warnings']:
                for warning in file_info['warnings']:
                    logger.warning(f"      ⚠ {warning}")
        
        logger.error("="*60)
        logger.error("Veuillez corriger ces fichiers avant de relancer l'ingestion.")
        logger.error("="*60)
    else:
        logger.info("Aucun fichier rejeté - tous les fichiers ont passé la validation.")


def log_ignored_files_summary():
    """
    Affiche un récapitulatif des fichiers ignorés à cause d'extensions non supportées.
    """
    global ignored_files
    
    if ignored_files:
        logger.warning("="*60)
        logger.warning(f"RÉCAPITULATIF : {len(ignored_files)} fichier(s) ignoré(s) détecté(s)")
        logger.warning("="*60)
        
        # Grouper par extension pour un affichage plus clair
        extensions_count = {}
        for file_info in ignored_files:
            ext = file_info["extension"] or "(sans extension)"
            if ext not in extensions_count:
                extensions_count[ext] = []
            extensions_count[ext].append(file_info["nom"])
        
        for ext, fichiers in extensions_count.items():
            logger.warning(f"  • {ext} : {len(fichiers)} fichier(s)")
            for fichier in fichiers:
                logger.warning(f"      - {fichier}")
        
        formats_supportes = ", ".join(SUPPORTED_EXTENSIONS)
        logger.warning(f"\n Formats supportés : {formats_supportes}")
        logger.warning("="*60)
    else:
        logger.info("Aucun fichier ignoré - tous les fichiers du dossier sont supportés.")


#  FONCTION PRINCIPALE D'ORCHESTRATION


def index_data(force_reindex: bool = False) -> bool:
    """
    C'est la méthode qu'on appelle depuis main.py au démarrage.
    Elle est suffisamment intelligente pour ne travailler que sur ce qui a changé.
    """
    global rejected_files
    rejected_files = []  # Réinitialiser la liste des fichiers rejetés
    
    logger.info("Vérification des archives de lore en cours...")

    fichiers_actuels = list_current_files()
    
    # Afficher le récapitulatif des fichiers ignorés
    log_ignored_files_summary()

    # --- CAS 1 : On nous demande explicitement de tout reconstruire ---
    if force_reindex:
        logger.info("Destruction de la mémoire et réindexation totale...")
        morceaux = prepare_files_for_ai(set(fichiers_actuels.keys()))
        log_rejected_files_summary()
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
    log_rejected_files_summary()
    
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
