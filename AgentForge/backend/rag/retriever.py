from typing import List, Dict, Any
from .vector_store import vector_store
from rank_bm25 import BM25Okapi
class Retriever:
    def retrieve_and_rerank(self, session_id: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        initial_results = vector_store.query(session_id, query, n_results=20)
        if not initial_results:
            return []
        tokenized_corpus = [res['text'].split() for res in initial_results]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.split()
        doc_scores = bm25.get_scores(tokenized_query)
        for i, res in enumerate(initial_results):
            res['bm25_score'] = doc_scores[i]
        reranked = sorted(initial_results, key=lambda x: x['bm25_score'], reverse=True)
        return reranked[:top_k]
retriever = Retriever()