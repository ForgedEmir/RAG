import os
import chromadb


def rechercher_passages(question: str) -> tuple[list[str], str]:
    """
    Fonction qui cherche les passages pertinents dans la base de données
    """
    # Connexion à ChromaDB (chemin base sur l'emplacement du fichier)
    base_dir = os.path.dirname(__file__)
    db_path = os.path.normpath(os.path.join(base_dir, "..", "ingestion", "chroma_db"))
    client_db = chromadb.PersistentClient(path=db_path)

    # Récupérer la collection
    collection = client_db.get_or_create_collection(name="lore")

    # Envoyer la question
    results = collection.query(
        query_texts=[question],
        n_results=3 # les 3 meilleurs résultats
    )

    documents = results.get("documents", [[]])
    passages = documents[0] if documents else []
    return passages, question