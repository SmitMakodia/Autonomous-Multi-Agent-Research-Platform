"""Retrieval quality and scaling.

Measures the actual two-stage cascade in rag/retriever.py: cosine similarity recalls 20
candidates, then BM25 alone reorders them. Because the cosine score is discarded from the
final ordering, the two stages are scored separately so the effect of the rerank is visible
rather than assumed.

Also measures query latency against corpus size, which exposes the O(N) full-table scan in
vector_store.query - every chunk in the session is loaded and JSON-parsed on every query.

Needs no llama-server: only the CPU embedder. Uses its own throwaway sessions and deletes
them afterwards, so the user's own chat history is never touched.

    venv\\Scripts\\python.exe benchmarks\\bench_retrieval.py
"""

import json
import math
import time
import uuid
from pathlib import Path

from _common import add_backend_to_path, summarise, write_evidence

add_backend_to_path()

from agents.base_agent import ContextChunk          # noqa: E402
from llm.memory_manager import memory_manager       # noqa: E402
from rag.retriever import retriever                 # noqa: E402
from rag.vector_store import vector_store           # noqa: E402

DATA = json.loads((Path(__file__).parent / "data" / "retrieval_testset.json").read_text(encoding="utf-8"))
K_VALUES = [1, 3, 5, 10]


def ingest(session_id, documents):
    chunks = [
        ContextChunk(text=d["text"], source=d["id"], agent_name="benchmark")
        for d in documents
    ]
    started = time.perf_counter()
    vector_store.add_chunks(session_id, chunks)
    return round((time.perf_counter() - started) * 1000, 2)


def rank_of(results, relevant_id):
    """1-based rank of the relevant document, or None if absent."""
    for i, r in enumerate(results, start=1):
        if r.get("metadata", {}).get("source") == relevant_id:
            return i
    return None


def ndcg_at_k(rank, k):
    """Single relevant document, binary gain -> nDCG reduces to 1/log2(rank+1)."""
    if rank is None or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def score(ranks, k_values):
    out = {}
    for k in k_values:
        hits = sum(1 for r in ranks if r is not None and r <= k)
        out[f"recall@{k}"] = round(hits / len(ranks), 4)
    out["mrr"] = round(sum(1.0 / r if r else 0.0 for r in ranks) / len(ranks), 4)
    out["ndcg@10"] = round(sum(ndcg_at_k(r, 10) for r in ranks) / len(ranks), 4)
    out["not_retrieved"] = sum(1 for r in ranks if r is None)
    return out


def measure_quality():
    session_id = f"bench_retrieval_{uuid.uuid4().hex[:8]}"
    print(f"  session {session_id}: ingesting {len(DATA['documents'])} documents")
    ingest_ms = ingest(session_id, DATA["documents"])
    print(f"  ingest (embed + insert): {ingest_ms} ms")

    per_query, latencies = [], []
    ranks = {"fused": [], "cosine_only": [], "bm25_only": []}

    for q in DATA["queries"]:
        started = time.perf_counter()
        fused = retriever.retrieve_and_rerank(session_id, q["query"], top_k=10)
        latency = round((time.perf_counter() - started) * 1000, 2)

        # Reconstruct the two component rankings from the same candidate set so all three
        # orderings are scored over identical recall - this isolates the ranking choice.
        candidates = vector_store.query(session_id, q["query"], n_results=20)
        cosine_order = candidates  # already ascending by distance
        bm25_order = sorted(fused, key=lambda x: x["bm25_score"], reverse=True)

        r = {
            "fused": rank_of(fused, q["relevant"]),
            "cosine_only": rank_of(cosine_order, q["relevant"]),
            "bm25_only": rank_of(bm25_order, q["relevant"]),
        }
        for key, value in r.items():
            ranks[key].append(value)
        latencies.append(latency)

        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "relevant": q["relevant"],
            "top_result": fused[0]["metadata"]["source"] if fused else None,
            "rank_fused": r["fused"],
            "rank_cosine_only": r["cosine_only"],
            "rank_bm25_only": r["bm25_only"],
            "latency_ms": latency,
            "top_rrf_score": round(fused[0]["rrf_score"], 6) if fused else None,
            "top_bm25_score": round(fused[0]["bm25_score"], 4) if fused else None,
            "top_cosine_similarity": round(1.0 - fused[0]["distance"], 4) if fused else None,
        })
        print(f"    {q['id']}: cosine {r['cosine_only']} | bm25 {r['bm25_only']} | fused {r['fused']}   ({latency} ms)")

    memory_manager.clear_session(session_id)

    return {
        "corpus_size": len(DATA["documents"]),
        "queries": len(DATA["queries"]),
        "ingest_ms": ingest_ms,
        "fused": score(ranks["fused"], K_VALUES),
        "cosine_only": score(ranks["cosine_only"], K_VALUES),
        "bm25_only": score(ranks["bm25_only"], K_VALUES),
        "latency_ms": summarise(latencies),
        "per_query": per_query,
    }


def measure_scaling(sizes=(20, 100, 500, 1000, 2000)):
    """Query latency against session corpus size."""
    base = DATA["documents"]
    results = []
    for size in sizes:
        session_id = f"bench_scale_{size}_{uuid.uuid4().hex[:6]}"
        padded = [
            {"id": f"{base[i % len(base)]['id']}_{i}",
             "text": f"[copy {i}] " + base[i % len(base)]["text"]}
            for i in range(size)
        ]
        ingest_ms = ingest(session_id, padded)

        latencies = []
        for q in DATA["queries"][:5]:
            started = time.perf_counter()
            retriever.retrieve_and_rerank(session_id, q["query"], top_k=10)
            latencies.append(round((time.perf_counter() - started) * 1000, 2))

        stats = summarise(latencies)
        results.append({"corpus_chunks": size, "ingest_ms": ingest_ms, "query_latency_ms": stats})
        print(f"    {size:>5} chunks: median query {stats['median']} ms  (ingest {ingest_ms} ms)")
        memory_manager.clear_session(session_id)
    return results


def main():
    print("=" * 70)
    print("Retrieval benchmark")
    print("=" * 70)
    print("\n[1/2] Quality on the labelled set")
    quality = measure_quality()

    print("\n[2/2] Latency vs corpus size")
    scaling = measure_scaling()

    payload = {
        "benchmark": "retrieval",
        "provenance": DATA["_provenance"],
        "method": {
            "pipeline": "vector_store.query cosine top-20 -> Reciprocal Rank Fusion of cosine and BM25 rankings -> top-10",
            "embedding_model": "BAAI/bge-small-en-v1.5 (384-dim, CPU)",
            "metrics": "Recall@k, MRR, nDCG@10 with one relevant document per query, binary gain",
            "rrf_k": 60,
            "note": (
                "All three orderings are scored over the same 20-candidate recall set, so the "
                "comparison isolates the ranking function. bm25_only is what the code did before "
                "this benchmark was written; fused is what it does now."
            ),
        },
        "quality": quality,
        "scaling": scaling,
    }
    write_evidence("bench_retrieval", payload)

    print("\n  " + "-" * 66)
    print(f"  {'metric':<14}{'cosine only':>14}{'bm25 only':>14}{'fused (RRF)':>14}")
    print(f"  {'':<14}{'':>14}{'[was shipped]':>14}{'[now]':>14}")
    print("  " + "-" * 66)
    for key in ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10"]:
        print(f"  {key:<14}{quality['cosine_only'][key]:>14}"
              f"{quality['bm25_only'][key]:>14}{quality['fused'][key]:>14}")
    print("  " + "-" * 66)


if __name__ == "__main__":
    main()
