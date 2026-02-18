import os
from typing import Dict, List

def lire_fichiers_md(dossier: str) -> List[Dict[str, str]]:
    documents: List[Dict[str, str]] = []
    for nom in os.listdir(dossier):
        if nom.endswith(".md"):
            with open(os.path.join(dossier, nom), "r", encoding="utf-8") as f:
                documents.append({"fichier": nom, "contenu": f.read()})
    print(f"📄 {len(documents)} fichiers lus.")
    return documents