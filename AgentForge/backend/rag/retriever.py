from typing import List, Dict, Any
from .vector_store import vector_store
from rank_bm25 import BM25Okapi
import metrics

# Reciprocal Rank Fusion constant. 60 is the value from the original Cormack et al. paper
# and is the usual default; it damps the influence of the very top ranks so one confident
# ranker cannot completely dominate the other.
RRF_K = 60


class Retriever:
    def retrieve_and_rerank(self, session_id: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Recall by embedding similarity, then fuse the semantic and lexical rankings.

        This used to sort the candidates by BM25 score alone, discarding the cosine
        similarity that selected them. Measured on benchmarks/data/retrieval_testset.json
        that was a substantial regression against using cosine on its own - Recall@1 0.65
        vs 0.95, MRR 0.75 vs 0.98 - because BM25 over only 20 short candidates rewards
        incidental term overlap, and a paraphrased query that shares no vocabulary with its
        answer scores near zero. Fusing the two rankings keeps the lexical signal for exact
        term matches without letting it override semantic similarity.
        """
        with metrics.stage("retrieve.vector") as f:
            initial_results = vector_store.query(session_id, query, n_results=20)
            f["candidates"] = len(initial_results)
        if not initial_results:
            return []

        with metrics.stage("retrieve.fuse", candidates=len(initial_results)):
            # Rank 1 = most similar. vector_store already returns ascending distance.
            semantic_rank = {id(res): i + 1 for i, res in enumerate(initial_results)}

            tokenized_corpus = [res['text'].split() for res in initial_results]
            bm25 = BM25Okapi(tokenized_corpus)
            doc_scores = bm25.get_scores(query.split())
            for i, res in enumerate(initial_results):
                res['bm25_score'] = float(doc_scores[i])

            by_bm25 = sorted(initial_results, key=lambda x: x['bm25_score'], reverse=True)
            lexical_rank = {id(res): i + 1 for i, res in enumerate(by_bm25)}

            for res in initial_results:
                res['rrf_score'] = (
                    1.0 / (RRF_K + semantic_rank[id(res)])
                    + 1.0 / (RRF_K + lexical_rank[id(res)])
                )

            fused = sorted(initial_results, key=lambda x: x['rrf_score'], reverse=True)

        return fused[:top_k]


retriever = Retriever()
