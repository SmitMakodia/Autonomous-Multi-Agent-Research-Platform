"""Behaviour under concurrent load.

llama-server runs with -np 1, a single decode slot, so concurrent queries queue behind one
another rather than running in parallel. This measures what that costs: success rate and
latency at 1, 2, 4 and 8 simultaneous requests.

The expected and honest result is near-linear latency growth with no throughput gain. It is
measured rather than assumed, and it is the main reason the system is described as
single-user.

Requires the backend on :8081.

    venv\\Scripts\\python.exe benchmarks\\bench_concurrency.py
"""

import asyncio
import json
import time
import uuid

import httpx

from _common import API_BASE, require_service, summarise, write_evidence

LEVELS = [1, 2, 4, 8]
PROMPT = "In one sentence, explain what a database index does."


async def one_query(client, index):
    session_id = f"bench_conc_{uuid.uuid4().hex[:8]}"
    started = time.perf_counter()
    try:
        r = await client.post(f"{API_BASE}/api/query",
                              data={"prompt": PROMPT, "session_id": session_id}, timeout=120)
        r.raise_for_status()
        query_id = r.json()["query_id"]

        first_token = None
        answer_chars = 0
        error = None
        async with client.stream("GET", f"{API_BASE}/api/stream/{query_id}", timeout=600) as s:
            async for line in s.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    p = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if p.get("event") == "token":
                    answer_chars += len(p["data"])
                    if first_token is None:
                        first_token = round((time.perf_counter() - started) * 1000, 2)
                elif p.get("event") == "error":
                    error = p["data"]

        return {
            "index": index,
            "session_id": session_id,
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
            "first_answer_token_ms": first_token,
            "answer_chars": answer_chars,
            "error": error,
            "ok": error is None and answer_chars > 0,
        }
    except Exception as e:
        return {
            "index": index,
            "session_id": session_id,
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": f"{type(e).__name__}: {e}",
            "ok": False,
        }


async def cleanup(client, sessions):
    for sid in sessions:
        try:
            await client.delete(f"{API_BASE}/api/sessions/{sid}", timeout=30)
        except Exception:
            pass


async def main():
    print("=" * 70)
    print("Concurrency benchmark")
    print("=" * 70)

    if not require_service(f"{API_BASE}/", "AgentForge backend"):
        write_evidence("bench_concurrency", {
            "benchmark": "concurrency",
            "status": "skipped",
            "reason": "backend not reachable on :8081 - no measurements taken",
        })
        return

    results = {}
    async with httpx.AsyncClient() as client:
        for level in LEVELS:
            print(f"\n  [{level} concurrent]")
            wall_start = time.perf_counter()
            runs = await asyncio.gather(*(one_query(client, i) for i in range(level)))
            wall = round(time.perf_counter() - wall_start, 2)

            ok = [r for r in runs if r["ok"]]
            latencies = [r["total_ms"] for r in ok]
            results[str(level)] = {
                "requests": level,
                "succeeded": len(ok),
                "success_rate": round(len(ok) / level, 4),
                "wall_clock_s": wall,
                "throughput_qps": round(len(ok) / wall, 4) if wall else None,
                "total_ms": summarise(latencies),
                "first_answer_token_ms": summarise([r.get("first_answer_token_ms") for r in ok]),
                "runs": runs,
            }
            print(f"    {len(ok)}/{level} ok   wall {wall}s   "
                  f"median {results[str(level)]['total_ms']['median']} ms   "
                  f"throughput {results[str(level)]['throughput_qps']} q/s")
            await cleanup(client, [r["session_id"] for r in runs])

    write_evidence("bench_concurrency", {
        "benchmark": "concurrency",
        "method": {
            "levels": LEVELS,
            "prompt": PROMPT,
            "constraint": "llama-server runs with -np 1 (single decode slot), so requests serialise "
                          "at the model regardless of FastAPI's async concurrency",
            "note": "One fresh session per request, all deleted afterwards.",
        },
        "results": results,
    })

    print("\n  " + "-" * 64)
    print(f"  {'concurrent':<12}{'ok':>6}{'median ms':>13}{'p95 ms':>11}{'q/s':>10}")
    print("  " + "-" * 64)
    for level, d in results.items():
        print(f"  {level:<12}{d['succeeded']:>6}{d['total_ms']['median']:>13}"
              f"{d['total_ms']['p95']:>11}{d['throughput_qps']:>10}")
    print("  " + "-" * 64)


if __name__ == "__main__":
    asyncio.run(main())
