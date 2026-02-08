from typing import Any, List
try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    from langchain_community.embeddings import OllamaEmbeddings
from agentforge.config.config_loader import ConfigLoader

class EmbeddingService:
    def __init__(self):
        self.config = ConfigLoader.load_model_config()
        self.embeddings = self._setup_embeddings()

    def _setup_embeddings(self):
        embed_config = self.config.get("embeddings", {})
        return OllamaEmbeddings(
            model=embed_config.get("model", "nomic-embed-text"),
            base_url=embed_config.get("base_url", "http://localhost:11434")
        )

    def get_embedding_function(self):
        return self.embeddings
