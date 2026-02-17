from typing import Any, Dict, List
import chromadb


def stocker_dans_chromadb(chunks_avec_meta: List[Dict[str, Any]]) -> Any:
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection("lore")
    except:
        pass
    collection = client.create_collection("lore")

    for i, chunk in enumerate(chunks_avec_meta):
        collection.add(
            ids=[f"chunk_{i}"],
            documents=[chunk["texte"]],
            metadatas=[{"fichier": chunk["fichier"]}]
        )

    print(f"{len(chunks_avec_meta)} chunks stockés dans ChromaDB.")
    return collection