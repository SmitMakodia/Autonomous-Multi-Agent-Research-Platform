import sqlite3
import json
import uuid
import numpy as np
from typing import List, Dict, Any
from agents.base_agent import ContextChunk
from .embedder import embedder
from llm.memory_manager import get_connection
import metrics

class VectorStore:
    def add_chunks(self, session_id: str, chunks: List[ContextChunk]):
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        with metrics.stage("embed", n=len(texts), chars=sum(len(t) for t in texts)):
            embeddings = embedder.embed_texts(texts)

        conn = get_connection()
        c = conn.cursor()

        # Ensure session exists
        c.execute("INSERT OR IGNORE INTO sessions (id, title) VALUES (?, ?)", (session_id, "New Session"))

        for i, chunk in enumerate(chunks):
            chunk_id = f"{session_id}_{chunk.timestamp}_{i}_{uuid.uuid4().hex[:8]}"
            # Store embedding as JSON string or bytes. JSON is easier for simple retrieval.
            emb_json = json.dumps(embeddings[i])
            c.execute(
                "INSERT INTO chunks (id, session_id, text, source, agent_name, timestamp, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chunk_id, session_id, chunk.text, chunk.source, chunk.agent_name, chunk.timestamp, emb_json)
            )

        conn.commit()
        conn.close()
        print(f"[VectorStore] Added {len(chunks)} chunks to session '{session_id}' in SQLite.")

    def query(self, session_id: str, query_text: str, n_results: int = 20) -> List[Dict[str, Any]]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, text, source, agent_name, timestamp, embedding FROM chunks WHERE session_id=?", (session_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            return []

        with metrics.stage("embed.query"):
            query_embedding = np.array(embedder.embed_query(query_text))

        scored_chunks = []
        for row in rows:
            chunk_emb = np.array(json.loads(row['embedding']))
            # Compute cosine similarity
            norm_q = np.linalg.norm(query_embedding)
            norm_c = np.linalg.norm(chunk_emb)
            if norm_q == 0 or norm_c == 0:
                similarity = 0.0
            else:
                similarity = np.dot(query_embedding, chunk_emb) / (norm_q * norm_c)

            scored_chunks.append({
                "id": row['id'],
                "text": row['text'],
                "metadata": {
                    "source": row['source'],
                    "agent_name": row['agent_name'],
                    "timestamp": row['timestamp']
                },
                "distance": float(1.0 - similarity) # Lower distance means higher similarity
            })

        # Sort by distance ascending (lowest distance first)
        scored_chunks.sort(key=lambda x: x["distance"])
        return scored_chunks[:n_results]

vector_store = VectorStore()