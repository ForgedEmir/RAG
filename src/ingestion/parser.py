"""
Module parser : lit les fichiers de données (TXT, MD, CSV, JSON, Excel)
et en extrait le texte brut. Nettoie aussi les balises HTML et les variables de jeu.
"""
import os
import re
import csv
import json
import logging
from typing import Optional

# Créer un logger pour ce module
logger = logging.getLogger(__name__)


def clean_text(raw_text: str) -> str:
    """
    Nettoie un texte brut :
    - Supprime les balises HTML/XML comme <color=red> ou </b>
    - Remplace les variables comme %PLAYER_NAME% par "le joueur"
    - Supprime les espaces en trop
    """
    if not raw_text:
        return ""

    # Supprimer les balises HTML/XML avec une expression régulière (regex)
    text = re.sub(r'<[^>]+>', '', raw_text)

    # Remplacer les variables connues par des termes lisibles
    text = text.replace('%PLAYER_NAME%', 'le joueur')

    # Supprimer les autres variables inconnues (ex: %QUEST_NAME%, %NPC_NAME%)
    text = re.sub(r'%[A-Z_]+%', '', text)

    # Nettoyer les espaces en double et retourner le résultat
    return " ".join(text.split())


def extract_text_from_file(filepath: str) -> Optional[str]:
    """
    Lit un fichier et en extrait le texte selon son format.
    Supporte : .txt, .md, .csv, .json, .xlsx
    Retourne None si le fichier est illisible (ne plante jamais).
    """
    if not os.path.exists(filepath):
        logger.error(f"Le fichier {filepath} n'existe pas.")
        return None

    # Récupérer l'extension du fichier (.txt, .md, .csv, .json, .xlsx)
    _, extension = os.path.splitext(filepath)
    extension = extension.lower()

    try:
        # --- Fichiers texte simples (TXT et Markdown) ---
        if extension in ['.txt', '.md']:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()

        # --- Fichiers JSON ---
        elif extension == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return _extraire_texte_json(data)

        # --- Fichiers CSV ---
        elif extension == '.csv':
            lignes = []
            with open(filepath, 'r', encoding='utf-8') as f:
                # Détecter automatiquement le séparateur (virgule, point-virgule, tabulation...)
                contenu = f.read()
                dialect = csv.Sniffer().sniff(contenu)
                f.seek(0)
                reader = csv.reader(f, dialect)
                for row in reader:
                    # On assemble chaque ligne du CSV en une phrase
                    ligne = " ".join([cell for cell in row if cell.strip()])
                    if ligne:
                        lignes.append(ligne)
            return "\n".join(lignes)

        # --- Fichiers Excel ---
        elif extension == '.xlsx':
            return _extraire_texte_excel(filepath)

        else:
            logger.warning(f"Format non supporté : {extension}")
            return None

    except Exception as e:
        # Si le fichier est corrompu, on loggue l'erreur mais on ne plante pas
        logger.error(f"Erreur lors de la lecture de {filepath} : {e}")
        return None


def _extraire_texte_excel(filepath: str) -> str:
    """
    Lit un fichier Excel (.xlsx) et en extrait le texte.
    Chaque ligne du tableur est convertie en texte : "Colonne1: Valeur1 | Colonne2: Valeur2"
    """
    import openpyxl

    classeur = openpyxl.load_workbook(filepath, read_only=True)
    lignes = []

    for feuille in classeur.sheetnames:
        sheet = classeur[feuille]
        rows = list(sheet.rows)

        if not rows:
            continue

        # La première ligne contient les noms de colonnes (en-têtes)
        en_tetes = [str(cell.value or "") for cell in rows[0]]

        # Chaque ligne suivante est convertie en texte lisible
        for row in rows[1:]:
            parties = []
            for i, cell in enumerate(row):
                if cell.value is not None:
                    nom_colonne = en_tetes[i] if i < len(en_tetes) else f"Col{i}"
                    parties.append(f"{nom_colonne}: {cell.value}")
            if parties:
                lignes.append(" | ".join(parties))

    classeur.close()
    return "\n".join(lignes)


def _extraire_texte_json(data, niveau: int = 0) -> str:
    """
    Parcourt un JSON de manière récursive pour en extraire le texte
    sous forme lisible : "Clé: Valeur" sur chaque ligne.
    """
    lignes = []
    espace = "  " * niveau  # Indentation pour la lisibilité

    if isinstance(data, dict):
        for cle, valeur in data.items():
            if isinstance(valeur, (dict, list)):
                lignes.append(f"{espace}{cle}:")
                lignes.append(_extraire_texte_json(valeur, niveau + 1))
            else:
                lignes.append(f"{espace}{cle}: {valeur}")

    elif isinstance(data, list):
        for element in data:
            lignes.append(_extraire_texte_json(element, niveau))
            lignes.append(f"{espace}---")

    else:
        lignes.append(f"{espace}{data}")

    return "\n".join([l for l in lignes if l])