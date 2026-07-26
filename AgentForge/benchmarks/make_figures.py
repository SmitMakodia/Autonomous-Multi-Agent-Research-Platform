"""Render every figure from the evidence JSON files.

Each chart is generated from rework-proof/evidence/*.json, so no figure contains a number
that is not also in the raw evidence. A missing evidence file skips its figure rather than
inventing data.

Palette is the validated three-slot categorical set (all-pairs CVD-safe) plus the status
colours; every chart carries direct value labels, so the one sub-3:1 slot still reads.

    venv\\Scripts\\python.exe benchmarks\\make_figures.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from _common import EVIDENCE_DIR, REPO_ROOT  # noqa: E402

FIG_DIR = REPO_ROOT / "rework-proof" / "assets" / "figures"

# Validated palette (see references/palette.md; checked with validate_palette.js)
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"     # categorical slots 1-3
GOOD, WARN, CRIT = "#0ca30c", "#fab219", "#d03b3b"
SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "grid.color": GRID,
    "axes.grid": True,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "figure.dpi": 140,
})


def load(name):
    path = EVIDENCE_DIR / f"{name}.json"
    if not path.exists():
        print(f"  [skip] {name}.json not found")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") == "skipped":
        print(f"  [skip] {name} was skipped: {data.get('reason')}")
        return None
    return data


def finish(fig, ax_or_axes, name, subtitle=None):
    axes = ax_or_axes if isinstance(ax_or_axes, (list, tuple)) else [ax_or_axes]
    for ax in axes:
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(BASELINE)
        ax.spines["bottom"].set_color(BASELINE)
    if subtitle:
        # Below the axis label, not on top of it.
        fig.text(0.5, -0.06, subtitle, ha="center", va="top", fontsize=7.5,
                 color=MUTED, wrap=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"{name}.png"
    fig.savefig(out, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"  wrote {out.name}")


# ------------------------------------------------------------------ 1. latency

def fig_latency():
    d = load("bench_latency")
    if not d:
        return
    stages = ["route", "tools", "embed", "index", "retrieve", "generate"]
    labels = {"route": "LLM tool routing", "tools": "Agent execution (search+scrape)",
              "embed": "Embedding", "index": "SQLite insert",
              "retrieve": "Retrieval", "generate": "LLM generation"}
    colours = [S2, S3, SEQ[2], SEQ[1], SEQ[4], S1]

    classes = [c for c in ("local", "search") if c in d["stage_breakdown_ms"]]
    fig, ax = plt.subplots(figsize=(9, 2.6 + 0.5 * len(classes)))

    for row, klass in enumerate(classes):
        sb = d["stage_breakdown_ms"][klass]
        left = 0
        for stage, colour in zip(stages, colours):
            if stage not in sb or sb[stage]["median"] is None:
                continue
            val = sb[stage]["median"]
            ax.barh(row, val, left=left, height=0.52, color=colour,
                    edgecolor=SURFACE, linewidth=2,
                    label=labels[stage] if row == 0 or stage not in ("route", "generate") else None)
            if val > 900:
                ax.text(left + val / 2, row, f"{val/1000:.1f}s", ha="center", va="center",
                        fontsize=8.5, color="white", fontweight="bold")
            left += val
        total = d["results"][klass]["total_ms"]["median"]
        ax.text(left + total * 0.015, row, f"end-to-end {total/1000:.1f}s",
                va="center", fontsize=9, color=INK, fontweight="bold")

    ax.set_yticks(range(len(classes)))
    ax.set_yticklabels([{"local": "No tools\n(direct answer)",
                         "search": "With web search\n(DuckDuckGo + Crawl4AI)"}[c]
                        for c in classes], fontsize=9, color=INK)
    ax.set_xlabel("milliseconds (median of measured runs)")
    ax.set_title("Where the time goes in one query", fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(d["results"][c]["total_ms"]["median"] for c in classes) * 1.28)

    handles, lbls = ax.get_legend_handles_labels()
    seen, h2, l2 = set(), [], []
    for h, l in zip(handles, lbls):
        if l and l not in seen:
            seen.add(l); h2.append(h); l2.append(l)
    ax.legend(h2, l2, loc="lower right", frameon=False, fontsize=8, ncol=2)
    finish(fig, ax, "fig_latency_waterfall",
           "Source: rework-proof/evidence/bench_latency.json - stage timings from the "
           "pipeline's own instrumentation, matched by query_id")


# --------------------------------------------------------------- 2. throughput

def fig_throughput():
    d = load("bench_throughput")
    if not d:
        return
    order = [k for k in ("short", "medium", "long") if k in d["results"]]
    gen = [d["results"][k]["generation_tokens_per_second"]["median"] for k in order]
    ttft = [d["results"][k]["ttft_ms"]["median"] for k in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6))

    bars = ax1.bar(order, gen, color=S1, width=0.55)
    for b, v in zip(bars, gen):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}",
                 ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax1.set_ylabel("tokens / second")
    ax1.set_title("Generation throughput", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, max(gen) * 1.22)
    ax1.grid(axis="x", visible=False)

    bars = ax2.bar(order, ttft, color=S2, width=0.55)
    for b, v in zip(bars, ttft):
        ax2.text(b.get_x() + b.get_width() / 2, v + max(ttft) * 0.03, f"{v:.0f} ms",
                 ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax2.set_ylabel("milliseconds")
    ax2.set_title("Time to first token", fontsize=11, fontweight="bold")
    ax2.set_ylim(0, max(ttft) * 1.25)
    ax2.grid(axis="x", visible=False)

    fig.suptitle("Qwen3.5-4B Q4_K_M on RTX 5060 Laptop, measured at llama-server",
                 fontsize=12.5, fontweight="bold", y=1.04)
    finish(fig, [ax1, ax2], "fig_throughput",
           "Source: rework-proof/evidence/bench_throughput.json - medians of 5 runs per prompt "
           "size; rates reported by llama-server's own timings block")


# --------------------------------------------------------------------- 3. VRAM

def fig_vram():
    d = load("bench_vram")
    if not d:
        return
    xs = [s["t_s"] for s in d["samples"]]
    ys = [s["used_mib"] for s in d["samples"]]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(xs, ys, color=S1, linewidth=2, zorder=3)
    ax.fill_between(xs, 0, ys, color=S1, alpha=0.10, zorder=2)

    total = d["gpu"]["total_mib"]
    ax.axhline(total, color=CRIT, linewidth=1.4, linestyle="--", zorder=4)
    ax.text(xs[-1], total - total * 0.045, f"  GPU capacity {total:,.0f} MiB",
            ha="right", fontsize=8.5, color=CRIT, fontweight="bold")

    interesting = {
        "llama-server ready": "LLM resident",
        "OCR request begins (triggers hot-swap)": "OCR requested",
        "OCR complete, llama-server restored": "LLM restored",
    }
    for m in d["marks"]:
        if m["label"] in interesting:
            ax.axvline(m["t_s"], color=MUTED, linewidth=1, linestyle=":", zorder=1)
            ax.text(m["t_s"] + 0.15, total * 0.94, interesting[m["label"]],
                    rotation=90, va="top", fontsize=8, color=INK2)

    # Place each window's label over the span it describes, not all at x=0.
    marks = {m["label"]: m["t_s"] for m in d["marks"]}
    ready = marks.get("llama-server ready", 6)
    swap_start = marks.get("OCR request begins (triggers hot-swap)", 8)
    swap_end = marks.get("OCR complete, llama-server restored", 20)
    w = d["windows"]
    for key, colour, x in [("baseline", MUTED, 1.4),
                           ("llm_resident", S1, (ready + swap_start) / 2),
                           ("after_restore", S3, (swap_end + xs[-1]) / 2)]:
        val = w[key]["mean_mib"]
        if val:
            ax.annotate(f"{val:,.0f} MiB", xy=(x, val), xytext=(0, 9),
                        textcoords="offset points", ha="center", fontsize=9,
                        color=colour, fontweight="bold")

    ax.set_xlabel("seconds", labelpad=8)
    ax.set_ylabel("GPU memory in use (MiB)")
    ax.set_ylim(0, total * 1.06)
    ax.set_xlim(0, xs[-1])
    ax.set_title(f"Model hot-swap on an 8 GB GPU  -  full cycle {d['swap_total_s']} s",
                 fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="x", visible=False)
    finish(fig, ax, "fig_vram_timeline",
           "Source: rework-proof/evidence/bench_vram.json - pynvml sampled every 100 ms. "
           "Whole-GPU usage, so the ~1 GiB floor is the desktop and browser, not AgentForge")


# ------------------------------------------------------------------ 4. routing

def fig_routing():
    d = load("bench_routing")
    if not d:
        return
    classes = list(d["per_class"].keys())
    cols = classes + ["other"]
    m = d["confusion_matrix"]
    grid = [[m[a][p] for p in cols] for a in classes]
    vmax = max(max(r) for r in grid) or 1

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.imshow(grid, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQ),
              vmin=0, vmax=vmax, aspect="auto")

    for i in range(len(classes)):
        for j in range(len(cols)):
            v = grid[i][j]
            if v == 0:
                continue
            ax.text(j, i, str(v), ha="center", va="center", fontsize=11,
                    fontweight="bold", color="white" if v > vmax * 0.55 else INK)

    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=25, ha="right", fontsize=9, color=INK2)
    ax.set_yticks(range(len(classes)))
    ax.set_yticklabels(classes, fontsize=9, color=INK2)
    ax.set_xlabel("tool the router chose")
    ax.set_ylabel("tool it should have chosen")
    s = d["summary"]
    ax.set_title(f"Tool-routing confusion matrix  -  {s['correct']}/{s['cases']} correct "
                 f"({s['accuracy']:.1%}), macro-F1 {s['macro_f1']}",
                 fontsize=12, fontweight="bold", pad=12)
    ax.grid(False)
    finish(fig, ax, "fig_routing_confusion",
           "Source: rework-proof/evidence/bench_routing.json - author-written 40-prompt set, "
           "not a standard benchmark")


# ---------------------------------------------------------------- 5. retrieval

def fig_retrieval_quality():
    d = load("bench_retrieval")
    if not d:
        return
    q = d["quality"]
    metrics = ["recall@1", "recall@3", "recall@5", "mrr", "ndcg@10"]
    series = [("cosine only", "cosine_only", S3),
              ("BM25 only (previous behaviour)", "bm25_only", S2),
              ("RRF fusion (current)", "fused", S1)]

    fig, ax = plt.subplots(figsize=(9.5, 4))
    width = 0.26
    for k, (label, key, colour) in enumerate(series):
        xs = [i + (k - 1) * width for i in range(len(metrics))]
        vals = [q[key][m] for m in metrics]
        ax.bar(xs, vals, width=width * 0.92, color=colour, label=label,
               edgecolor=SURFACE, linewidth=1.5)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.018, f"{v:.2f}", ha="center", fontsize=7.8,
                    color=INK, fontweight="bold")

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, fontsize=9.5, color=INK2)
    ax.set_ylabel("score (1.0 = perfect)")
    ax.set_ylim(0, 1.16)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=1)
    ax.set_title("Retrieval ranking: measuring the rerank instead of assuming it",
                 fontsize=12.5, fontweight="bold", pad=12)
    finish(fig, ax, "fig_retrieval_quality",
           f"Source: rework-proof/evidence/bench_retrieval.json - {q['corpus_size']} documents, "
           f"{q['queries']} queries, author-written. Ranking BM25-only lost 0.30 Recall@1 "
           "against the cosine ordering that fed it")


def fig_retrieval_scaling():
    d = load("bench_retrieval")
    if not d:
        return
    rows = d["scaling"]
    xs = [r["corpus_chunks"] for r in rows]
    ys = [r["query_latency_ms"]["median"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.plot(xs, ys, color=S1, linewidth=2, marker="o", markersize=8,
            markerfacecolor=S1, markeredgecolor=SURFACE, markeredgewidth=2)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.0f} ms", (x, y), textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=8.5, color=INK, fontweight="bold")
    ax.set_xlabel("chunks in the session")
    ax.set_ylabel("median query latency (ms)")
    ax.set_ylim(0, max(ys) * 1.28)
    ax.set_title("Retrieval latency grows linearly with session size",
                 fontsize=12, fontweight="bold", pad=12)
    ax.grid(axis="x", visible=False)
    finish(fig, ax, "fig_retrieval_scaling",
           "Source: rework-proof/evidence/bench_retrieval.json - vector_store.query loads and "
           "JSON-parses every chunk in the session on each call; there is no ANN index")


# ------------------------------------------------------------------- 6. scrape

def fig_scrape():
    d = load("bench_scrape")
    if not d:
        return
    counts = d["summary"]["by_path"]
    order = ["crawl4ai", "beautifulsoup_fallback", "failed"]
    pretty = {"crawl4ai": "Crawl4AI\n(headless Chromium)",
              "beautifulsoup_fallback": "BeautifulSoup\nfallback",
              "failed": "No content"}
    colours = {"crawl4ai": S1, "beautifulsoup_fallback": S2, "failed": CRIT}
    vals = [counts.get(k, 0) for k in order]

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    bars = ax.bar([pretty[k] for k in order], vals,
                  color=[colours[k] for k in order], width=0.5)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.15, str(v), ha="center",
                fontsize=12, fontweight="bold", color=INK)
    ax.set_ylabel("URLs")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.grid(axis="x", visible=False)
    s = d["summary"]
    ax.set_title(f"Which scraping path carried the load  -  {s['produced_content']}/"
                 f"{s['attempted']} URLs returned content",
                 fontsize=12, fontweight="bold", pad=12)
    finish(fig, ax, "fig_scrape_outcomes",
           "Source: rework-proof/evidence/bench_scrape.json - snapshot against live sites. "
           "The fallback path did not fire on this run, so it is untested here, not proven")


# ---------------------------------------------------------------------- 7. OCR

def fig_ocr():
    d = load("bench_ocr")
    if not d:
        return
    conds = list(d["per_condition"].keys())
    cer = [d["per_condition"][c]["cer"]["median"] for c in conds]
    wer = [d["per_condition"][c]["wer"]["median"] for c in conds]

    fig, ax = plt.subplots(figsize=(9.2, 4))
    width = 0.36
    xs = range(len(conds))
    b1 = ax.bar([x - width / 2 for x in xs], cer, width=width * 0.94, color=S1,
                label="Character error rate", edgecolor=SURFACE, linewidth=1.5)
    b2 = ax.bar([x + width / 2 for x in xs], wer, width=width * 0.94, color=S2,
                label="Word error rate", edgecolor=SURFACE, linewidth=1.5)
    top = max(max(cer), max(wer), 0.05)
    for bars, vals in ((b1, cer), (b2, wer)):
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + top * 0.03, f"{v:.3f}",
                    ha="center", fontsize=8, color=INK, fontweight="bold")

    ax.set_xticks(list(xs))
    ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=9, color=INK2)
    ax.set_ylabel("error rate (0 = perfect)")
    ax.set_ylim(0, top * 1.25)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9)
    o = d["overall"]
    ax.set_title(f"Vision OCR error rate by image condition  -  overall median CER "
                 f"{o['cer']['median']:.3f} over {o['samples']} samples",
                 fontsize=12, fontweight="bold", pad=12)
    finish(fig, ax, "fig_ocr_conditions",
           "Source: rework-proof/evidence/bench_ocr.json - synthetically rendered text with exact "
           "ground truth. Rendered text is easier than scans, so these are an upper bound")


# -------------------------------------------------------------- 8. concurrency

def fig_concurrency():
    d = load("bench_concurrency")
    if not d:
        return
    levels = sorted(d["results"].keys(), key=int)
    med = [d["results"][k]["total_ms"]["median"] / 1000 for k in levels]
    qps = [d["results"][k]["throughput_qps"] for k in levels]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6))

    bars = ax1.bar(levels, med, color=S2, width=0.55)
    for b, v in zip(bars, med):
        ax1.text(b.get_x() + b.get_width() / 2, v + max(med) * 0.03, f"{v:.0f}s",
                 ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax1.set_xlabel("simultaneous requests")
    ax1.set_ylabel("median latency (s)")
    ax1.set_title("Latency per request", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, max(med) * 1.25)
    ax1.grid(axis="x", visible=False)

    bars = ax2.bar(levels, qps, color=S1, width=0.55)
    for b, v in zip(bars, qps):
        ax2.text(b.get_x() + b.get_width() / 2, v + max(qps) * 0.03, f"{v:.3f}",
                 ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax2.set_xlabel("simultaneous requests")
    ax2.set_ylabel("completed queries / second")
    ax2.set_title("System throughput", fontsize=11, fontweight="bold")
    ax2.set_ylim(0, max(qps) * 1.3)
    ax2.grid(axis="x", visible=False)

    fig.suptitle("Concurrency: one decode slot, so requests queue",
                 fontsize=12.5, fontweight="bold", y=1.04)
    finish(fig, [ax1, ax2], "fig_concurrency",
           "Source: rework-proof/evidence/bench_concurrency.json - llama-server runs with -np 1, "
           "so latency scales with load while throughput stays flat")


# ---------------------------------------------------------------- 9. scorecard

def fig_summary():
    """Headline numbers as stat tiles - a table, not a chart, because these are single values."""
    tiles = []

    t = load("bench_throughput")
    if t and "short" in t["results"]:
        tiles.append(("Generation speed",
                      f"{t['results']['short']['generation_tokens_per_second']['median']:.0f}",
                      "tokens/sec", S1))
        tiles.append(("Time to first token",
                      f"{t['results']['short']['ttft_ms']['median']:.0f}", "ms", S1))
    v = load("bench_vram")
    if v:
        tiles.append(("Model hot-swap", f"{v['swap_total_s']:.1f}", "seconds, full cycle", S2))
        tiles.append(("Peak GPU memory",
                      f"{v['windows']['during_swap']['max_mib']/1024:.1f}",
                      f"GiB of {v['gpu']['total_mib']/1024:.0f} GiB", S2))
    r = load("bench_routing")
    if r:
        tiles.append(("Tool-routing accuracy", f"{r['summary']['accuracy']:.0%}",
                      f"{r['summary']['correct']}/{r['summary']['cases']} prompts", S3))
    rt = load("bench_retrieval")
    if rt:
        tiles.append(("Retrieval Recall@3", f"{rt['quality']['fused']['recall@3']:.2f}",
                      f"{rt['quality']['queries']} queries", S3))
    lat = load("bench_latency")
    if lat and "search" in lat["results"]:
        tiles.append(("Research query, end to end",
                      f"{lat['results']['search']['total_ms']['median']/1000:.0f}",
                      "seconds median", S1))
    o = load("bench_ocr")
    if o:
        tiles.append(("OCR character error rate", f"{o['overall']['cer']['median']:.3f}",
                      f"{o['overall']['samples']} rendered samples", S2))

    if not tiles:
        print("  [skip] summary - no evidence available")
        return

    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 1.85 * rows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for ax, (label, value, unit, colour) in zip(axes, tiles):
        ax.axis("off")
        ax.add_patch(Rectangle((0.02, 0.08), 0.96, 0.84, transform=ax.transAxes,
                               facecolor="white", edgecolor=GRID, linewidth=1))
        ax.add_patch(Rectangle((0.02, 0.08), 0.012, 0.84, transform=ax.transAxes,
                               facecolor=colour, edgecolor="none"))
        ax.text(0.09, 0.72, label, transform=ax.transAxes, fontsize=8.5, color=INK2)
        ax.text(0.09, 0.36, value, transform=ax.transAxes, fontsize=27,
                fontweight="bold", color=INK)
        ax.text(0.09, 0.2, unit, transform=ax.transAxes, fontsize=8, color=MUTED)

    for ax in axes[len(tiles):]:
        ax.axis("off")

    fig.suptitle("AgentForge - measured performance, RTX 5060 Laptop 8 GB",
                 fontsize=14, fontweight="bold", y=1.0)
    fig.text(0.5, -0.02,
             "Every figure is measured on this machine and traceable to a file in "
             "rework-proof/evidence/. Nothing here is estimated.",
             ha="center", fontsize=8, color=MUTED)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "fig_summary_scorecard.png", bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print("  wrote fig_summary_scorecard.png")


def main():
    print("Rendering figures from evidence ...")
    for fn in (fig_summary, fig_latency, fig_throughput, fig_vram, fig_routing,
               fig_retrieval_quality, fig_retrieval_scaling, fig_scrape,
               fig_ocr, fig_concurrency):
        try:
            fn()
        except Exception as e:
            print(f"  [error] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\nFigures in {FIG_DIR}")


if __name__ == "__main__":
    main()
