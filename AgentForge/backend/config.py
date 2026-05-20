import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
UPLOADS_DIR = BASE_DIR / "uploads"
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://localhost:8000/v1")
LLM_MODEL = "Qwen3.5-4B-Q4_K_M.gguf"
MAX_CONTEXT_TOKENS = 60000
GLM_OCR_SERVER_URL = os.getenv("GLM_OCR_SERVER_URL", "http://localhost:8080/v1")
GLM_OCR_MODEL = "zai-org/GLM-OCR"
FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://localhost:3002/v1")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_COLLECTION_PREFIX = "session_"