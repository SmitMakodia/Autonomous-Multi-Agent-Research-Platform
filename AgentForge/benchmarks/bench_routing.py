"""Tool-selection accuracy of the LLM router.

Calls mcp_layer.tool_router.route_prompt directly with each labelled prompt and compares
the tool it chose against the expected one. Reports per-class precision/recall/F1 and a
confusion matrix.

The test set is author-written (see data/routing_testset.json) - it is not a standard
benchmark and the numbers are not comparable to published tool-calling evaluations.

Requires llama-server on :8000.

    venv\\Scripts\\python.exe benchmarks\\bench_routing.py
"""

import asyncio
import json
import time
from pathlib import Path

from _common import LLAMA_BASE, add_backend_to_path, require_service, summarise, write_evidence

add_backend_to_path()

from mcp_layer.tool_router import route_prompt  # noqa: E402

DATA = json.loads((Path(__file__).parent / "data" / "routing_testset.json").read_text(encoding="utf-8"))
CLASSES = ["web_search", "web_scrape_url", "read_local_file", "ocr_image", "none"]


async def classify(prompt: str):
    """Run the real router. Returns (predicted_label, all_tools, latency_ms)."""
    started = time.perf_counter()
    plan = await route_prompt([{"role": "user", "content": prompt}])
    latency = round((time.perf_counter() - started) * 1000, 2)
    tools = [t.name for t in plan.tools]
    # The router may emit several tools; the first is treated as its primary choice.
    predicted = tools[0] if tools else "none"
    return predicted, tools, latency


def prf(matrix, cls, totals_actual, totals_pred):
    tp = matrix[cls][cls]
    fp = totals_pred[cls] - tp
    fn = totals_actual[cls] - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "support": totals_actual[cls],
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


async def main():
    print("=" * 70)
    print("Tool routing benchmark")
    print("=" * 70)

    if not require_service(f"{LLAMA_BASE}/health", "llama-server"):
        write_evidence("bench_routing", {
            "benchmark": "routing",
            "status": "skipped",
            "reason": "llama-server not reachable on :8000 - no measurements taken",
        })
        return

    matrix = {a: {p: 0 for p in CLASSES + ["other"]} for a in CLASSES}
    per_case, latencies = [], []

    for case in DATA["cases"]:
        predicted, tools, latency = await classify(case["prompt"])
        expected = case["expected"]
        bucket = predicted if predicted in CLASSES else "other"
        matrix[expected][bucket] += 1
        latencies.append(latency)
        correct = predicted == expected
        per_case.append({
            "id": case["id"],
            "prompt": case["prompt"],
            "expected": expected,
            "predicted": predicted,
            "all_tools": tools,
            "correct": correct,
            "latency_ms": latency,
        })
        mark = "ok " if correct else "MISS"
        print(f"  {mark} {case['id']}  expected {expected:<16} got {predicted:<16} ({latency} ms)")

    total = len(per_case)
    correct_n = sum(1 for c in per_case if c["correct"])
    totals_actual = {c: sum(matrix[c].values()) for c in CLASSES}
    totals_pred = {
        c: sum(matrix[a][c] for a in CLASSES) for c in CLASSES
    }
    per_class = {c: prf(matrix, c, totals_actual, totals_pred) for c in CLASSES}
    macro_f1 = round(sum(v["f1"] for v in per_class.values()) / len(per_class), 4)

    write_evidence("bench_routing", {
        "benchmark": "routing",
        "provenance": DATA["_provenance"],
        "method": {
            "entry_point": "mcp_layer.tool_router.route_prompt",
            "prediction_rule": "first tool in the returned plan; empty plan counts as 'none'",
            "temperature": 0.0,
            "note": "route_prompt swallows all exceptions and returns an empty plan, so an "
                    "infrastructure failure is indistinguishable from a deliberate 'none'. "
                    "Latency outliers are the signal to check for that.",
        },
        "summary": {
            "cases": total,
            "correct": correct_n,
            "accuracy": round(correct_n / total, 4),
            "macro_f1": macro_f1,
            "latency_ms": summarise(latencies),
        },
        "per_class": per_class,
        "confusion_matrix": matrix,
        "per_case": per_case,
    })

    print(f"\n  Accuracy: {correct_n}/{total} = {correct_n/total:.1%}   macro-F1 {macro_f1}")
    print(f"  Router latency: median {summarise(latencies)['median']} ms\n")
    print(f"  {'actual \\ predicted':<20}" + "".join(f"{c[:12]:>14}" for c in CLASSES + ["other"]))
    for a in CLASSES:
        print(f"  {a:<20}" + "".join(f"{matrix[a][p]:>14}" for p in CLASSES + ["other"]))


if __name__ == "__main__":
    asyncio.run(main())
