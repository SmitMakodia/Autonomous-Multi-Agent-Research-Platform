import chromadb
from chromadb.config import Settings
from agentforge.config.config_loader import ConfigLoader
from agentforge.memory.embeddings import EmbeddingService
import os

class VectorStore:
    def __init__(self):
        self.config = ConfigLoader.load_model_config()
        self.db_path = self.config["vector_db"]["path"]
        self.collection_name = self.config["vector_db"]["collection_name"]
        
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
            
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.embedding_service = EmbeddingService()
        
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, documents: list, metadatas: list, ids: list):
        embeddings = self.embedding_service.get_embedding_function().embed_documents(documents)
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def query(self, query_text: str, n_results: int = 5):
        query_embedding = self.embedding_service.get_embedding_function().embed_query(query_text)
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
