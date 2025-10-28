# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR.parent / ".env")  # load .env at project root if present

# OpenAI API key (optional). Put OPENAI_API_KEY in your .env or environment.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)

# Tesseract command override (if needed)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")

# TF-IDF / retrieval settings
TFIDF_MAX_FEATURES = int(os.getenv("TFIDF_MAX_FEATURES", 5000))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", 3))

# Paths
DATASETS_DIR = BASE_DIR / "datasets"
DATASETS_DIR.mkdir(exist_ok=True)
SAMPLE_DATASET = DATASETS_DIR / "sample_training_dataset.json"

MEMORY_STORE_DIR = BASE_DIR / "memory_store"
MEMORY_STORE_DIR.mkdir(exist_ok=True)
LONG_MEMORY_PATH = MEMORY_STORE_DIR / "long_memory.json"
VECTOR_STORE_PATH = MEMORY_STORE_DIR / "vector_store.pkl"

APP_NAME = "AI MedBot"
VERSION = "0.1"
# --- IGNORE ---