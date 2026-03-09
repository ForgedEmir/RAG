"""
L'extracteur universel.
Son but est de lire tous les types de fichiers (Markdown, CSV, Excel, JSON...) 
et de les transformer en texte brut et propre, prêt à être indexé.
"""
import os
import re
import csv
import json
import logging
import unicodedata
from typing import Optional, List

logger = logging.getLogger(__name__)

# Formats supportés
SUPPORTED_FORMATS = [".txt", ".md", ".csv", ".json", ".xlsx", ".xml"]

# Liste des encodages à essayer en cas d'échec (ordre de priorité)
FALLBACK_ENCODINGS = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1', 'windows-1252']


def _try_multiple_encodings(filepath: str, encodings: List[str] = None) -> Optional[str]:
    """
    Essaie de lire un fichier avec plusieurs encodages différents.
    Retourne le contenu du fichier dès qu'un encodage fonctionne, ou None si tous échouent.
    """
    if encodings is None:
        encodings = FALLBACK_ENCODINGS
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
                logger.debug(f"Fichier {os.path.basename(filepath)} lu avec succès en {encoding}")
                return content
        except (UnicodeDecodeError, UnicodeError):
            logger.debug(f"Échec de lecture en {encoding} pour {os.path.basename(filepath)}")
            continue
        except Exception as e:
            logger.warning(f"Erreur inattendue avec l'encodage {encoding} : {e}")
            continue
    
    logger.error(f"Impossible de lire {os.path.basename(filepath)} avec les encodages : {', '.join(encodings)}")
    return None


def _clean_invalid_characters(text: str) -> str:
    """
    Nettoie les caractères invalides ou problématiques dans une chaîne Unicode.
    Remplace les caractères de contrôle et normalise les caractères spéciaux.
    """
    if not text:
        return ""
    
    # Normaliser les caractères Unicode (forme NFC = forme canonique composée)
    text = unicodedata.normalize('NFC', text)
    
    # Supprimer les caractères de contrôle sauf les sauts de ligne et tabulations
    cleaned = ""
    for char in text:
        # Garder les caractères imprimables et quelques blancs utiles
        if char in ['\n', '\r', '\t'] or not unicodedata.category(char).startswith('C'):
            cleaned += char
        else:
            # Remplacer les caractères de contrôle par un espace
            cleaned += ' '
    
    return cleaned


def clean_text(raw_text: str) -> str:
    """
    La moulinette de nettoyage.
    Prend du texte brut plein de balises de code et le rend propre et lisible pour l'IA.
    """
    if not raw_text:
        return ""

    # On utilise une expression régulière (Regex) pour effacer tout ce qui ressemble à une balise <...>.
    text = re.sub(r'<[^>]+>', '', raw_text)

    # Il y a aussi des variables de code du jeu. On les remplace par du texte en bon français.
    text = text.replace('%PLAYER_NAME%', 'le joueur')

    def replace_unknown_vars(match):
        # We just return the word without the % signs
        return match.group(0).replace('%', '')

    # Et si on croise d'autres variables magiques genre %NPC_NAME% ou %QUEST_24%,
    # on garde le nom de la variable sans les % pour que l'IA ait du contexte.
    text = re.sub(r'%[A-Z_0-9]+%', replace_unknown_vars, text)

    # Enfin, on vire les doubles ou triples espaces créés par nos nettoyages précédents.
    return " ".join(text.split())


def extract_text_from_file(filepath: str) -> Optional[str]:
    """
    Le couteau suisse de la lecture de fichiers.
    Il regarde l'extension du fichier et utilise la bonne méthode pour l'ouvrir.
    S'il n'y arrive pas, il retourne 'None' au lieu de faire crasher toute l'application.
    """
    if not os.path.exists(filepath):
        logger.error(f"Oups, le fichier {filepath} semble avoir disparu.")
        return None

    _, extension = os.path.splitext(filepath)
    extension = extension.lower()

    try:
        # --- Fichiers texte normaux ---
        if extension in ['.txt', '.md']:
            content = _try_multiple_encodings(filepath)
            if content is None:
                return None
            return _clean_invalid_characters(content)

        # --- Fichiers JSON ---
        elif extension == '.json':
            return _extraire_texte_json_safe(filepath)

        # --- Fichiers d'espacement (CSV) ---
        elif extension == '.csv':
            return _extraire_texte_csv_safe(filepath)

        # --- Fichiers Excel ---
        elif extension == '.xlsx':
            return _extraire_texte_excel(filepath)

        # --- Fichiers XML (pas encore implémenté) ---
        elif extension == '.xml':
            logger.info(f"Le support XML n'est pas encore implémenté pour {os.path.basename(filepath)}. Fichier ignoré.")
            return None

        else:
            formats_supportes = ", ".join(SUPPORTED_FORMATS)
            logger.warning(
                f"Format non supporté détecté : '{extension}' pour le fichier {os.path.basename(filepath)}. "
                f"Formats acceptés : {formats_supportes}. Ce fichier sera ignoré."
            )
            return None

    except Exception as e:
        logger.error(f"Un problème est survenu en lisant {filepath} : {e}")
        return None


def _extraire_texte_csv_safe(filepath: str) -> Optional[str]:
    """
    Lit un fichier CSV avec gestion robuste des encodages mixtes.
    Essaie plusieurs encodages et détecte automatiquement le délimiteur.
    """
    for encoding in FALLBACK_ENCODINGS:
        try:
            lignes = []
            with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                # Le csv.Sniffer devine le délimiteur (virgule, point-virgule, tabulation...)
                contenu = f.read()
                
                # Nettoyer les caractères invalides
                contenu = _clean_invalid_characters(contenu)
                
                # Essayer de deviner le dialecte CSV
                try:
                    dialect = csv.Sniffer().sniff(contenu[:1024])  # Analyser les 1024 premiers caractères
                except csv.Error:
                    # Si Sniffer échoue, utiliser le délimiteur par défaut (virgule)
                    dialect = csv.excel
                
                # Relire le fichier avec le bon dialecte
                from io import StringIO
                reader = csv.reader(StringIO(contenu), dialect)
                
                for row in reader:
                    # Nettoyer chaque cellule et créer une phrase
                    ligne = " ".join([cell.strip() for cell in row if cell.strip()])
                    if ligne:
                        lignes.append(ligne)
                
                if lignes:
                    logger.info(f"CSV {os.path.basename(filepath)} lu avec succès en {encoding}")
                    return "\n".join(lignes)
                    
        except Exception as e:
            logger.debug(f"Échec de lecture CSV en {encoding} pour {filepath}: {e}")
            continue
    
    logger.error(f"Impossible de lire le fichier CSV {filepath} avec tous les encodages disponibles")
    return None


def _extraire_texte_json_safe(filepath: str) -> Optional[str]:
    """
    Lit un fichier JSON avec gestion robuste des encodages et caractères spéciaux.
    Essaie plusieurs encodages et nettoie les caractères invalides.
    """
    for encoding in FALLBACK_ENCODINGS:
        try:
            with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
                
                # Nettoyer les caractères invalides
                content = _clean_invalid_characters(content)
                
                # Parser le JSON
                data = json.loads(content)
                
                logger.info(f"JSON {os.path.basename(filepath)} lu avec succès en {encoding}")
                return _extraire_texte_json(data)
                
        except json.JSONDecodeError as e:
            logger.debug(f"Erreur de parsing JSON en {encoding} pour {filepath}: {e}")
            # Essayer avec un autre encodage
            continue
        except Exception as e:
            logger.debug(f"Échec de lecture JSON en {encoding} pour {filepath}: {e}")
            continue
    
    # Dernier recours : essayer de lire le fichier comme texte brut
    try:
        logger.warning(f"Impossible de parser {filepath} comme JSON, lecture en texte brut")
        content = _try_multiple_encodings(filepath)
        if content:
            return _clean_invalid_characters(content)
    except Exception:
        pass
    
    logger.error(f"Impossible de lire le fichier JSON {filepath}")
    return None


def _extraire_texte_excel(filepath: str) -> str:
    """
    Extrait le texte d'un fichier Excel.
    Gère les formules en récupérant les valeurs calculées plutôt que les formules elles-mêmes.
    """
    import openpyxl
    
    try:
        # data_only=True : récupère les valeurs calculées des formules au lieu des formules
        # read_only=True : économise la mémoire RAM
        classeur = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    except Exception as e:
        logger.error(f"Erreur lors de l'ouverture du fichier Excel {filepath}: {e}")
        # Essayer sans data_only en dernier recours
        try:
            logger.warning(f"Nouvelle tentative sans data_only pour {filepath}")
            classeur = openpyxl.load_workbook(filepath, read_only=True, data_only=False)
        except Exception as e2:
            logger.error(f"Impossible d'ouvrir le fichier Excel {filepath}: {e2}")
            return ""
    
    lignes = []

    for feuille in classeur.sheetnames:
        try:
            sheet = classeur[feuille]
            rows = list(sheet.rows)

            if not rows:
                continue

            # La toute première ligne contient généralement le titre des colonnes
            en_tetes = [str(cell.value or "").strip() for cell in rows[0]]

            # Ensuite, on boucle sur les vraies données
            for row in rows[1:]:
                parties = []
                for i, cell in enumerate(row):
                    try:
                        # Gérer les différents types de valeurs
                        valeur = cell.value
                        
                        # Si la valeur est None (formule non calculée ou cellule vide)
                        if valeur is None:
                            continue
                        
                        # Nettoyer la valeur
                        valeur_str = str(valeur).strip()
                        
                        if valeur_str:
                            nom_colonne = en_tetes[i] if i < len(en_tetes) and en_tetes[i] else f"Col{i}"
                            parties.append(f"{nom_colonne}: {valeur_str}")
                    except Exception as e:
                        logger.debug(f"Erreur lors de la lecture d'une cellule : {e}")
                        continue
                
                if parties:
                    ligne = " | ".join(parties)
                    # Nettoyer les caractères invalides
                    ligne = _clean_invalid_characters(ligne)
                    lignes.append(ligne)
        except Exception as e:
            logger.warning(f"Erreur lors de la lecture de la feuille {feuille} : {e}")
            continue

    classeur.close()
    
    if not lignes:
        logger.warning(f"Aucune donnée extraite du fichier Excel {filepath}")
    
    return "\n".join(lignes)


def _extraire_texte_json(data, niveau: int = 0) -> str:
    """
    Prend un fichier JSON (avec potentiellement des listes et des dictionnaires imbriqués)
    et le déballe récursivement pour en faire du texte lisible platement.
    """
    lignes = []
    espace = "  " * niveau

    # Si c'est un dictionnaire (ex: un objet comme un item ou un monstre)
    if isinstance(data, dict):
        for cle, valeur in data.items():
            if isinstance(valeur, (dict, list)):
                lignes.append(f"{espace}{cle}:")
                lignes.append(_extraire_texte_json(valeur, niveau + 1))
            else:
                lignes.append(f"{espace}{cle}: {valeur}")

    # Si c'est un tableau de choses
    elif isinstance(data, list):
        for element in data:
            lignes.append(_extraire_texte_json(element, niveau))
            lignes.append(f"{espace}---")

    # Si c'est juste une valeur finale (chiffre, mot)
    else:
        lignes.append(f"{espace}{data}")

    return "\n".join([l for l in lignes if l])
