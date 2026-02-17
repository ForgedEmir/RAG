from typing import Dict, List
from parser import lire_fichiers_md
from chunker import decouper_en_chunks
from loader import stocker_dans_chromadb

# Lire les fichiers
documents: List[Dict[str, str]] = lire_fichiers_md("../../data/sample")

# Découper en chunks
tous_les_chunks: List[Dict[str, str]] = []
for doc in documents:
    chunks = decouper_en_chunks(doc["contenu"])
    for chunk in chunks:
        tous_les_chunks.append({"texte": chunk, "fichier": doc["fichier"]})

# Stocker dans ChromaDB
collection = stocker_dans_chromadb(tous_les_chunks)