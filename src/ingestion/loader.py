"""
Le pont entre notre code et la base de données (ChromaDB).
C'est ici qu'on définit comment on traduit nos textes en "embeddings" (des vecteurs mathématiques)
et comment on sauvegarde, met à jour ou supprime des données dans notre collection.
"""
import os
import hashlib
import logging
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from typing import Any, List

logger = logging.getLogger(__name__)


class FastEmbedMultilingual(EmbeddingFunction):
    """
    On utilise le package FastEmbed pour une raison majeure : il est super léger.
    Il convertit nos textes en vecteurs en comprenant très bien le français,
    le tout sans avoir besoin d'installer des bibliothèques lourdes de 2Go comme PyTorch.
    Parfait pour un déploiement gratuit sur Railway ou Render !
    """
    def __init__(self):
        # On n'importe fastembed qu'ici pour que le reste de l'app puisse démarrer
        # même s'il y a un petit souci d'installation au boot de l'environnement.
        from fastembed import TextEmbedding
        
        # Le nom magique du modèle ultra performant en français.
        self.model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    def __call__(self, input: Documents) -> Embeddings:
        # Petite bidouille technique : FastEmbed crache des arrays numpy, mais 
        # ChromaDB attend plutôt des simples listes de nombres (float). On convertit.
        embeddings = list(self.model.embed(input))
        return [e.tolist() for e in embeddings]


# On garde une seule instance globale de notre fonction pour ne pas la recharger en boucle.
EMBEDDING_FUNCTION = FastEmbedMultilingual()


def _get_collection(force_reindex: bool = False) -> Any:
    """
    Ouvre l'accès au "coffre" (notre collection 'lore') dans ChromaDB.
    Si force_reindex est vrai, on met un coup de balai et on repart à zéro.
    """
    base_dir = os.path.dirname(__file__)
    db_path = os.path.join(base_dir, "chroma_db")

    client = chromadb.PersistentClient(path=db_path)

    if force_reindex:
        try:
            client.delete_collection("lore")
            logger.info("Ancienne base supprimée avec succès. On fait place nette.")
        except Exception:
            # Si elle n'existait pas encore, delete() va planter. On ignore tout simplement.
            pass

    # get_or_create s'assure qu'on ait toujours un conteneur dispo, même à la toute première exécution.
    return client.get_or_create_collection("lore", embedding_function=EMBEDDING_FUNCTION)


def store_in_chromadb(chunks: List[dict], force_reindex: bool = False) -> Any:
    """Raccourci bien pratique pour récupérer la collection et y injecter plein de données d'un coup."""
    collection = _get_collection(force_reindex)
    add_to_chromadb(collection, chunks)
    return collection


def add_to_chromadb(collection: Any, chunks: List[dict]) -> None:
    """
    La vraie fonction d'ajout. Elle prend nos morceaux de textes fraîchement découpés
    et leur donne un identifiant unique avant de les jeter dans la base.
    """
    if not chunks:
        return

    ids = []
    textes = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        # On invente un identifiant super unique (hash MD5) basé sur le texte lui-même + le fichier d'origine.
        # Ça évite de créer des doublons fantômes.
        text_hash = hashlib.md5(chunk["texte"].encode('utf-8')).hexdigest()[:16]
        unique_id = f"{chunk['fichier']}_{i}_{text_hash}"

        ids.append(unique_id)
        textes.append(chunk["texte"])
        metadatas.append({"fichier": chunk["fichier"]})

    # On envoie toute la liste en une seule opération vers ChromaDB.
    collection.add(ids=ids, documents=textes, metadatas=metadatas)
    logger.info(f"{len(chunks)} morceaux ont bien été indexés.")


def remove_files_from_chromadb(collection: Any, fichiers: set) -> None:
    """
    Nettoie tous les paragraphes d'un fichier en particulier.
    Super utile quand Marcus modifie juste "personnages.md" par exemple : on rase 
    tout ce qui venait de ce fichier avant d'injecter la nouvelle version.
    """
    if not fichiers:
        return

    for nom_fichier in fichiers:
        # On utilise les métadonnées ("nom_fichier") pour cibler précisément ce qu'on efface.
        collection.delete(where={"fichier": nom_fichier})

    logger.info(f"{len(fichiers)} fichier(s) évaporé(s) de la base.")
