"""
Central configuration for the Clinical RAG project.
Edit these values to match your team's setup — everything else
in this repo reads from here, so you only need to change it in one place.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "clinical_guidelines"

# --- Chunking ---
# Values are in approximate tokens. The splitter uses a rough
# 4-characters-per-token estimate to convert these to character counts.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# --- Embeddings ---
# "local"  -> free, runs on your machine, lightweight, no API key needed (default)
# "openai" -> optional, requires OPENAI_API_KEY in .env
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")
LOCAL_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# --- Retrieval ---
TOP_K = 12

# --- Generation (Gemini) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# --- Retrieval-Confidence Gating ---
# Chroma's relevance score is roughly in [0, 1] (higher = more relevant).
# These thresholds cap what confidence the LLM is ALLOWED to report —
# this is what response_schema.json's "confidence" description promises
# ("insufficient: below retrieval confidence threshold") but the original
# generate.py never actually enforced it programmatically.
RETRIEVAL_CONFIDENCE_THRESHOLDS = {
    "high": 0.75,
    "medium": 0.55,
    "low": 0.35,
    # top score below "low" -> forced "insufficient" (refusal)
}