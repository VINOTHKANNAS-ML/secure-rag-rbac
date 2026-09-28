import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")
METADATA_PATH = os.path.join(BASE_DIR, "data", "metadata.json")
USERS_PATH = os.path.join(BASE_DIR, "data", "users.json")
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_store")

COLLECTION_NAME = "enterprise_docs"

# Embedding model - small, fast, runs locally with no API key required.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Chunking
CHUNK_SIZE_CHARS = 500
CHUNK_OVERLAP_CHARS = 80

# Retrieval
TOP_K = 4

# Generation
# Groq's OpenAI-compatible API (free tier, no billing required). This
# hosts fast inference of open-source models - NOT xAI's "Grok" model,
# despite the similar name. Groq's catalog changes over time; if this
# model 404s, run `python scripts/list_groq_models.py` to see what's
# currently available on your account and update this value.
GROQ_MODEL = "openai/gpt-oss-20b"
