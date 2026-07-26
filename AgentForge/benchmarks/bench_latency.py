"""End-to-end latency through the real HTTP API, with a per-stage breakdown.

Drives POST /api/query + GET /api/stream exactly as the browser does, then reads back the
stage records that backend/metrics.py wrote for those query_ids, so the waterfall is the
pipeline's own instrumentation rather than an external estimate.

Two prompt classes are measured separately because they exercise different paths:
  - local  : answerable without tools (router returns no tools)
  - search : triggers web_search, so it includes DuckDuckGo + Crawl4AI + embedding

Requires the backend running on :8081.

    venv\\Scripts\\python.exe benchmarks\\bench_latency.py
"""

import json
import time
import uuid
from pathlib import Path

import httpx

from _common import API_BASE, AGENTFORGE_DIR, require_service, summarise, write_evidence

METRICS_PATH = AGENTFORGE_DIR / "logs" / "metrics.jsonl"

PROMPTS = {
    "local": [
        "Explain the difference between a list and a tuple in Python.",
        "What is 128 multiplied by 47?",
        "Write two sentences about why unit tests matter.",
        "Define idempotency in one sentence.",
    ],
    "search": [
        "What is the current stable version of Python?",
        "Summarise what SQLite is used for.",
        "What is retrieval-augmented generation?",
    ],
}
REPEATS = 2


def run_one(prompt: str, session_id: str):
    """One full query. Returns wall-clock milestones and the query_id for stage lookup."""
    r = httpx.post(f"{API_BASE}/api/query",
                   data={"prompt": prompt, "session_id": session_id}, timeout=60)
    r.raise_for_status()
    query_id = r.json()["query_id"]

    started = time.perf_counter()
    first_reasoning = first_token = None
    reasoning_chars = answer_chars = 0
    statuses = []
    error = None

    with httpx.Client(timeout=600) as client:
        with client.stream("GET", f"{API_BASE}/api/stream/{query_id}") as s:
            for line in s.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    p = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                ev = p.get("event")
                now = round((time.perf_counter() - started) * 1000, 2)
                if ev == "status":
                    statuses.append({"at_ms": now, "text": p["data"]})
                elif ev == "reasoning":
                    reasoning_chars += len(p["data"])
                    if first_reasoning is None:
                        first_reasoning = now
                elif ev == "token":
                    answer_chars += len(p["data"])
                    if first_token is None:
                        first_token = now
                elif ev == "error":
                    error = p["data"]
                elif ev == "done":
                    pass

    return {
        "query_id": query_id,
        "prompt": prompt,
        "total_ms": round((time.perf_counter() - started) * 1000, 2),
        "first_reasoning_ms": first_reasoning,
        "first_answer_token_ms": first_token,
        "reasoning_chars": reasoning_chars,
        "answer_chars": answer_chars,
        "statuses": statuses,
        "error": error,
    }


def read_stages(query_ids):
    """Pull this run's stage records out of the metrics log."""
    if not METRICS_PATH.exists():
        return {}
    wanted = set(query_ids)
    by_query = {}
    for line in METRICS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("query_id") in wanted:
            by_query.setdefault(rec["query_id"], []).append(rec)
    return by_query


def main():
    print("=" * 70)
    print("End-to-end latency benchmark")
    print("=" * 70)

    if not require_service(f"{API_BASE}/", "AgentForge backend"):
        write_evidence("bench_latency", {
            "benchmark": "latency",
            "status": "skipped",
            "reason": "backend not reachable on :8081 - no measurements taken",
        })
        return

    results = {}
    all_query_ids = []
    sessions = []

    for klass, prompts in PROMPTS.items():
        print(f"\n  [{klass}] {len(prompts)} prompts x {REPEATS} repeats")
        runs = []
        for prompt in prompts:
            for rep in range(REPEATS):
                # Fresh session each run so retrieval never sees a previous run's chunks.
                session_id = f"bench_lat_{uuid.uuid4().hex[:8]}"
                sessions.append(session_id)
                r = run_one(prompt, session_id)
                runs.append(r)
                all_query_ids.append(r["query_id"])
                status = "ERROR" if r["error"] else "ok"
                print(f"    {status:>5}  {r['total_ms']:>9.0f} ms  "
                      f"first-token {r['first_answer_token_ms']}  \"{prompt[:42]}\"")
        results[klass] = {
            "runs": runs,
            "total_ms": summarise([r["total_ms"] for r in runs]),
            "first_reasoning_ms": summarise([r["first_reasoning_ms"] for r in runs]),
            "first_answer_token_ms": summarise([r["first_answer_token_ms"] for r in runs]),
            "errors": sum(1 for r in runs if r["error"]),
        }

    print("\n  Reading stage breakdown from metrics.jsonl ...")
    stages_by_query = read_stages(all_query_ids)

    # Aggregate stage durations per prompt class.
    stage_summary = {}
    for klass, data in results.items():
        per_stage = {}
        for run in data["runs"]:
            for rec in stages_by_query.get(run["query_id"], []):
                key = rec.get("stage") or rec.get("event")
                if rec.get("duration_ms") is None:
                    continue
                per_stage.setdefault(key, []).append(rec["duration_ms"])
        stage_summary[klass] = {k: summarise(v) for k, v in sorted(per_stage.items())}

    print("\n  Cleaning up benchmark sessions ...")
    for session_id in sessions:
        try:
            httpx.delete(f"{API_BASE}/api/sessions/{session_id}", timeout=30)
        except Exception:
            pass

    write_evidence("bench_latency", {
        "benchmark": "latency",
        "method": {
            "transport": "real HTTP: POST /api/query then GET /api/stream/{query_id} (SSE)",
            "stage_source": "backend/metrics.py records, matched by query_id",
            "sessions": "one fresh session per run, deleted afterwards",
            "repeats": REPEATS,
            "note": "search-class runs depend on live DuckDuckGo and target sites, so their "
                    "variance reflects the open internet, not just this machine.",
        },
        "results": results,
        "stage_breakdown_ms": stage_summary,
    })

    print("\n  " + "-" * 64)
    print(f"  {'class':<10}{'n':>4}{'median ms':>13}{'p95 ms':>11}{'first tok':>12}{'errors':>9}")
    print("  " + "-" * 64)
    for klass, d in results.items():
        print(f"  {klass:<10}{d['total_ms']['n']:>4}{d['total_ms']['median']:>13}"
              f"{d['total_ms']['p95']:>11}{str(d['first_answer_token_ms']['median']):>12}"
              f"{d['errors']:>9}")
    print("  " + "-" * 64)

    for klass, stages in stage_summary.items():
        print(f"\n  [{klass}] stage medians (ms)")
        for name, s in stages.items():
            print(f"    {name:<28}{s['median']:>10}   (n={s['n']})")


if __name__ == "__main__":
    main()
