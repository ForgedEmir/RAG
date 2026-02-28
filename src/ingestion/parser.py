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

    # Et si on croise d'autres variables magiques genre %NP_NAME% ou %QUEST_24%, on les supprime carrément.
    text = re.sub(r'%[A-Z_]+%', '', text)

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

        # --- Fichiers lourd (Excel) ---
        elif extension == '.xlsx':
            return _extraire_texte_excel(filepath)

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
    Petite bidouille pour lire les fichiers Excel fournis par le professeur.
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
