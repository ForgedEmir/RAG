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
from typing import Optional

logger = logging.getLogger(__name__)


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
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()

        # --- Fichiers JSON ---
        elif extension == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return _extraire_texte_json(data)

        # --- Fichiers d'espacement (CSV) ---
        elif extension == '.csv':
            lignes = []
            with open(filepath, 'r', encoding='utf-8') as f:
                # Le csv.Sniffer est intelligent : il devine tout seul si le fichier
                # utilise des virgules, des points-virgules ou des tabulations.
                contenu = f.read()
                dialect = csv.Sniffer().sniff(contenu)
                f.seek(0)
                reader = csv.reader(f, dialect)
                for row in reader:
                    # On transforme chaque ligne du tableau en une phrase simple
                    ligne = " ".join([cell for cell in row if cell.strip()])
                    if ligne:
                        lignes.append(ligne)
            return "\n".join(lignes)

        # --- Fichiers Excel ---
        elif extension == '.xlsx':
            return _extraire_texte_excel(filepath)

        # --- Fichiers XML ---
        elif extension == '.xml':
            return _extraire_texte_xml(filepath)

        else:
            logger.warning(f"Format non supporté : {extension}. Ce fichier sera ignoré.")
            return None

    except Exception as e:
        # La philosophie ici : on log l'erreur pour pouvoir la réparer plus tard,
        # mais on laisse l'application tourner tranquillement.
        logger.error(f"Un problème est survenu en lisant {filepath} : {e}")
        return None


def _extraire_texte_excel(filepath: str) -> str:
    """
    On prend chaque ligne et on recrée un texte de type : "Colonne: Valeur | Autre: Valeur".
    """
    import openpyxl

    # On l'ouvre en mode "read_only" pour économiser de la mémoire RAM
    classeur = openpyxl.load_workbook(filepath, read_only=True)
    lignes = []

    for feuille in classeur.sheetnames:
        sheet = classeur[feuille]
        rows = list(sheet.rows)

        if not rows:
            continue

        # La toute première ligne contient généralement le titre des colonnes
        en_tetes = [str(cell.value or "") for cell in rows[0]]

        # Ensuite, on boucle sur les vraies données
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


def _extraire_texte_xml(filepath: str) -> str:
    """
    Lit un fichier XML et extrait tout le texte contenu dans les balises.
    On lit l'arbre XML et on récupère le texte de chaque nœud en ignorant les balises elles-mêmes.
    Simple et très efficace.
    """
    import xml.etree.ElementTree as ET
    
    try:
        # On charge l'entièreté de l'arbre XML en mémoire.
        tree = ET.parse(filepath)
        root = tree.getroot()
        lignes = []
        
        # On se balade dans absolument tous les éléments de l'arbre, peu importe leur profondeur
        for elem in root.iter():
            # Si l'élément contient du texte (et pas seulement d'autres balises)
            texte_brut = elem.text
            if texte_brut and isinstance(texte_brut, str):
                # On nettoie un peu le texte pour éviter d'avoir des phrases vides faites d'espaces
                texte = texte_brut.strip()
                if texte:
                    lignes.append(texte)
                    
        return "\n".join(lignes)
        
    except ET.ParseError as e:
        # Si le fichier est corrompu, on envoie juste un log et on retourne du vide 
        # pour éviter de crasher tout le système
        logger.error(f"Impossible de lire le XML {filepath} (fichier corrompu ou mal formé) : {e}")
        return ""

