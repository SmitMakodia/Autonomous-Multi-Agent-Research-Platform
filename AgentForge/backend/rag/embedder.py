from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL
class Embedder:
    def __init__(self):
        print(f"[Embedder] Loading model {EMBEDDING_MODEL}...")
        self.model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    def embed_query(self, query: str) -> list[float]:
        embedding = self.model.encode([query], show_progress_bar=False)
        return embedding[0].tolist()
embedder = Embedder()