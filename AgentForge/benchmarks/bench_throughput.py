"""LLM throughput and time-to-first-token, measured against llama-server directly.

Goes straight to the inference server rather than through the app, so the numbers describe
the model on this GPU without RAG, routing, or scraping mixed in. llama-server reports its
own prompt-eval and generation rates in the `timings` object; those are used rather than
wall-clock estimates because they exclude HTTP overhead.

TTFT is measured separately over a streaming request, since `timings` cannot report it.

Requires llama-server on :8000 (start_agentforge.bat starts it, or run it standalone).

    venv\\Scripts\\python.exe benchmarks\\bench_throughput.py
"""

import json
import time
import urllib.request

import httpx

from _common import LLAMA_BASE, require_service, summarise, write_evidence

# Three prompt sizes: short interactive, medium, and one large enough to make prompt
# processing visible against generation.
PROMPTS = [
    ("short", "Name three primary colours."),
    ("medium", "Explain in two paragraphs how a retrieval-augmented generation pipeline "
               "differs from fine-tuning a model on the same documents."),
    ("long", "Here is some background material.\n\n"
             + ("A vector database stores high-dimensional embeddings and supports "
                "approximate nearest-neighbour search over them. Retrieval quality depends "
                "on the embedding model, the chunking strategy, and the similarity metric. ") * 40
             + "\n\nGiven the above, summarise the three factors that determine retrieval quality."),
]

RUNS_PER_PROMPT = 5
# Qwen3.5 is a reasoning model and this llama.cpp build streams the thinking block first.
# At 256 tokens the budget is exhausted before the answer begins, so a smaller cap measures
# thinking throughput only and reports no answer at all. 1024 lets a short answer complete.
MAX_TOKENS = 1024


def one_completion(prompt: str):
    """Non-streaming call; returns llama-server's own timing block."""
    payload = {
        "model": "Qwen3.5-4B-Q4_K_M.gguf",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }
    started = time.perf_counter()
    with httpx.Client(timeout=300.0) as client:
        r = client.post(f"{LLAMA_BASE}/v1/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()
    wall_ms = round((time.perf_counter() - started) * 1000, 2)

    timings = data.get("timings", {}) or {}
    usage = data.get("usage", {}) or {}
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {}) or {}
    return {
        "wall_ms": wall_ms,
        # 'length' here means the answer was cut off by max_tokens, not that it finished.
        "finish_reason": choice.get("finish_reason"),
        "reasoning_chars": len(message.get("reasoning_content") or ""),
        "answer_chars": len(message.get("content") or ""),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_eval_per_second": timings.get("prompt_per_second"),
        "generation_per_second": timings.get("predicted_per_second"),
        "prompt_eval_ms": timings.get("prompt_ms"),
        "generation_ms": timings.get("predicted_ms"),
    }


def one_ttft(prompt: str):
    """Streaming call; returns ms to the first content delta."""
    payload = {
        "model": "Qwen3.5-4B-Q4_K_M.gguf",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }
    started = time.perf_counter()
    ttft = None            # first token of any kind - what the user sees move first
    first_answer = None    # first token of the actual answer, after the thinking block
    tokens = 0
    with httpx.Client(timeout=300.0) as client:
        with client.stream("POST", f"{LLAMA_BASE}/v1/chat/completions", json=payload) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                body = line[6:].strip()
                if body == "[DONE]":
                    break
                try:
                    delta = json.loads(body)["choices"][0].get("delta", {})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                # This llama.cpp build parses the model's thinking natively and streams it
                # as reasoning_content, separate from the answer in content.
                if delta.get("reasoning_content") or delta.get("content"):
                    tokens += 1
                    if ttft is None:
                        ttft = round((time.perf_counter() - started) * 1000, 2)
                if delta.get("content") and first_answer is None:
                    first_answer = round((time.perf_counter() - started) * 1000, 2)
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "ttft_ms": ttft,
        "first_answer_token_ms": first_answer,
        "total_ms": total_ms,
        "streamed_deltas": tokens,
    }


def main():
    print("=" * 70)
    print("LLM throughput benchmark")
    print("=" * 70)

    if not require_service(f"{LLAMA_BASE}/health", "llama-server"):
        write_evidence("bench_throughput", {
            "benchmark": "throughput",
            "status": "skipped",
            "reason": "llama-server not reachable on :8000 - no measurements taken",
        })
        return

    print("\n  Warming up (first call includes prompt-cache setup)...")
    one_completion("Say OK.")

    results = {}
    for label, prompt in PROMPTS:
        print(f"\n  [{label}] {RUNS_PER_PROMPT} runs, max_tokens={MAX_TOKENS}")
        runs, stream_runs = [], []
        for i in range(RUNS_PER_PROMPT):
            r = one_completion(prompt)
            runs.append(r)
            t = one_ttft(prompt)
            stream_runs.append(t)
            print(f"    run {i+1}: {r['generation_per_second']:.1f} tok/s gen, "
                  f"{r['prompt_eval_per_second']:.1f} tok/s prompt, "
                  f"TTFT {t['ttft_ms']} ms, first answer token {t['first_answer_token_ms']} ms")

        results[label] = {
            "prompt_chars": len(prompt),
            "prompt_tokens": runs[0]["prompt_tokens"],
            "runs": runs,
            "stream_runs": stream_runs,
            "generation_tokens_per_second": summarise([r["generation_per_second"] for r in runs]),
            "prompt_eval_tokens_per_second": summarise([r["prompt_eval_per_second"] for r in runs]),
            "ttft_ms": summarise([t["ttft_ms"] for t in stream_runs]),
            "first_answer_token_ms": summarise([t["first_answer_token_ms"] for t in stream_runs]),
            "wall_ms": summarise([r["wall_ms"] for r in runs]),
        }

    write_evidence("bench_throughput", {
        "benchmark": "throughput",
        "method": {
            "target": "llama-server /v1/chat/completions, bypassing the AgentForge pipeline",
            "source_of_rates": "llama-server's own `timings` block (excludes HTTP overhead)",
            "ttft": "measured separately over a streaming request, first content delta",
            "model": "Qwen3.5-4B-Q4_K_M.gguf, -ngl 99, -fa on, --ctx-size 10000, -np 1",
            "runs_per_prompt": RUNS_PER_PROMPT,
            "max_tokens": MAX_TOKENS,
            "warmup": "one discarded call before measurement",
        },
        "results": results,
    })

    print("\n  " + "-" * 62)
    print(f"  {'prompt':<10}{'gen tok/s':>13}{'prompt tok/s':>15}{'TTFT ms':>12}")
    print("  " + "-" * 62)
    for label, r in results.items():
        print(f"  {label:<10}{r['generation_tokens_per_second']['median']:>13}"
              f"{r['prompt_eval_tokens_per_second']['median']:>15}{r['ttft_ms']['median']:>12}")
    print("  " + "-" * 62)
    print("  (medians)")


if __name__ == "__main__":
    main()
