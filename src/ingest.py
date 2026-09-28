"""
Loads the document corpus, chunks it, embeds each chunk, and stores it in a
persistent Chroma collection with department + confidentiality_level
metadata attached to every chunk. This metadata is what the retriever later
filters on to enforce RBAC.

Run directly:
    python -m src.ingest
"""

import json
import os

import chromadb
from chromadb.utils import embedding_functions

from src.chunking import chunk_text
from src.config import (
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    METADATA_PATH,
)


def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


def get_embedding_function():
    # Runs locally via sentence-transformers - no API key needed for ingestion.
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )


def build_index(reset: bool = True) -> chromadb.Collection:
    if not os.path.exists(METADATA_PATH):
        raise FileNotFoundError(
            "data/metadata.json not found. Run `python generate_dataset.py` first."
        )

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    client = get_chroma_client()
    embed_fn = get_embedding_function()

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=embed_fn
    )

    ids, texts, metadatas = [], [], []
    for doc_id, meta in metadata.items():
        with open(meta["path"], "r", encoding="utf-8") as f:
            full_text = f.read()

        chunks = chunk_text(full_text)
        for i, chunk in enumerate(chunks):
            ids.append(f"{doc_id}__chunk{i}")
            texts.append(chunk)
            metadatas.append(
                {
                    "doc_id": doc_id,
                    "title": meta["title"],
                    "department": meta["department"],
                    # Chroma metadata values must be primitives; keep as int.
                    "confidentiality_level": int(meta["confidentiality_level"]),
                }
            )

    # Chroma upsert in batches (kept simple here; batch if corpus grows large)
    collection.add(ids=ids, documents=texts, metadatas=metadatas)

    print(f"Indexed {len(ids)} chunks from {len(metadata)} documents "
          f"into collection '{COLLECTION_NAME}'.")
    return collection


if __name__ == "__main__":
    build_index(reset=True)
