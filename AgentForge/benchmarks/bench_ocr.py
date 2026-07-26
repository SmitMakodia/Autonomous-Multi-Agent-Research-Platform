"""Vision OCR accuracy: character and word error rate against exact ground truth.

Test images are generated here with PIL rather than hand-transcribed, for three reasons:
the ground truth is exact rather than a human's reading of a scan, the set is fully
reproducible by anyone running this script, and it contains no personal data.

The trade-off is honest and must be stated wherever these numbers appear: cleanly rendered
text is easier than a photographed or scanned document, so these figures are an upper bound
on real-world accuracy. Difficulty tiers (small type, low contrast, rotation, noise) show
how quality degrades, but none of them reproduce camera optics or paper texture.

Runs the OCR agent directly, which performs the real VRAM hot-swap each time.

    venv\\Scripts\\python.exe benchmarks\\bench_ocr.py
"""

import asyncio
import random
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from _common import add_backend_to_path, summarise, write_evidence

add_backend_to_path()

from agents.ocr_agent import OCRAgent  # noqa: E402
from config import UPLOADS_DIR         # noqa: E402

GROUND_TRUTH = [
    "The quick brown fox jumps over the lazy dog.",
    "Invoice Number: INV-2026-00841",
    "Total Amount Due: 14,250.00",
    "Retrieval augmented generation grounds answers in retrieved evidence.",
    "Contact: support at example dot com",
    "Order 7734 shipped on 12 March 2026 via express courier.",
]


def load_font(size):
    for name in ["arial.ttf", "segoeui.ttf", "calibri.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(text, out_path, *, size=40, contrast="high", rotate=0, noise=0):
    """Render one line of text into an image under a named difficulty condition."""
    font = load_font(size)
    pad = 40
    tmp = Image.new("RGB", (10, 10), "white")
    box = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0] + pad * 2, box[3] - box[1] + pad * 2

    bg, fg = ("white", "black") if contrast == "high" else ((200, 200, 200), (130, 130, 130))
    img = Image.new("RGB", (w, h), bg)
    ImageDraw.Draw(img).text((pad, pad), text, font=font, fill=fg)

    if rotate:
        img = img.rotate(rotate, expand=True, fillcolor=bg)
    if noise:
        rng = random.Random(0)  # fixed seed so the benchmark is reproducible
        px = img.load()
        for _ in range(int(img.width * img.height * noise)):
            x, y = rng.randrange(img.width), rng.randrange(img.height)
            v = rng.randrange(256)
            px[x, y] = (v, v, v)
        img = img.filter(ImageFilter.GaussianBlur(0.4))

    img.save(out_path)
    return out_path


CONDITIONS = [
    ("clean_large",    dict(size=40, contrast="high")),
    ("small_type",     dict(size=16, contrast="high")),
    ("low_contrast",   dict(size=40, contrast="low")),
    ("rotated_5deg",   dict(size=40, contrast="high", rotate=5)),
    ("noisy",          dict(size=40, contrast="high", noise=0.04)),
]


def levenshtein(a, b):
    """Standard edit distance. Iterative two-row form to stay O(min(len)) in memory."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,        # deletion
                current[j - 1] + 1,     # insertion
                previous[j - 1] + (ca != cb),  # substitution
            ))
        previous = current
    return previous[-1]


def normalise(s):
    """Collapse whitespace and lowercase. Layout differences are not recognition errors."""
    return " ".join(s.split()).lower()


def error_rates(truth, hypothesis):
    t, h = normalise(truth), normalise(hypothesis)
    cer = levenshtein(t, h) / max(len(t), 1)
    tw, hw = t.split(), h.split()
    wer = levenshtein(tw, hw) / max(len(tw), 1)
    return round(min(cer, 1.0), 4), round(min(wer, 1.0), 4)


def strip_heading(text):
    """The agent prefixes a markdown heading onto every extraction."""
    marker = "**Vision Extract: GLM-OCR Analysis of User-Provided Image**"
    return text.replace(marker, "").strip()


async def main():
    print("=" * 70)
    print("Vision OCR accuracy benchmark")
    print("=" * 70)

    agent = OCRAgent()
    # Images must live inside uploads/ - the path guard confines the agent to it.
    work_dir = Path(UPLOADS_DIR) / "_bench_ocr"
    work_dir.mkdir(parents=True, exist_ok=True)

    per_condition = {}
    all_rows = []

    try:
        for cond_name, opts in CONDITIONS:
            print(f"\n  [{cond_name}]")
            rows = []
            for i, truth in enumerate(GROUND_TRUTH):
                path = work_dir / f"{cond_name}_{i}.png"
                render(truth, path, **opts)

                chunks = await agent.run(file_path=str(path))
                got = strip_heading(chunks[0].text) if chunks else ""
                cer, wer = error_rates(truth, got)
                exact = normalise(truth) == normalise(got)

                rows.append({
                    "index": i,
                    "ground_truth": truth,
                    "extracted": got,
                    "cer": cer,
                    "wer": wer,
                    "exact_match": exact,
                })
                print(f"    CER {cer:<8} WER {wer:<8} {'EXACT' if exact else '     '}  "
                      f"{got[:48]!r}")
                path.unlink(missing_ok=True)

            per_condition[cond_name] = {
                "samples": len(rows),
                "cer": summarise([r["cer"] for r in rows]),
                "wer": summarise([r["wer"] for r in rows]),
                "exact_match_rate": round(sum(r["exact_match"] for r in rows) / len(rows), 4),
                "rows": rows,
            }
            all_rows.extend(rows)
    finally:
        for leftover in work_dir.glob("*"):
            leftover.unlink(missing_ok=True)
        work_dir.rmdir()

    write_evidence("bench_ocr", {
        "benchmark": "ocr",
        "provenance": {
            "author": "Ground truth is the exact string rendered into each image by this script. "
                      "Not a public OCR benchmark.",
            "test_images": "generated with PIL at run time, fixed random seed, deleted afterwards",
            "known_limitations": [
                "Rendered text is substantially easier than photographed or scanned documents, "
                "so these rates are an upper bound on real-world accuracy.",
                "6 short single-line strings per condition - a small sample.",
                "English, Latin script, common sans-serif faces only.",
                "No tables, multi-column layout, handwriting, or curved/warped text.",
                "Comparison is whitespace-normalised and case-insensitive; layout fidelity is not scored.",
            ],
        },
        "method": {
            "entry_point": "agents.ocr_agent.OCRAgent.run (performs the real VRAM hot-swap per image)",
            "model": "GLM-OCR, bfloat16, device_map=cuda, max_new_tokens=2048",
            "cer": "Levenshtein distance over characters / length of ground truth",
            "wer": "Levenshtein distance over whitespace-split tokens / word count of ground truth",
            "conditions": [c[0] for c in CONDITIONS],
        },
        "overall": {
            "samples": len(all_rows),
            "cer": summarise([r["cer"] for r in all_rows]),
            "wer": summarise([r["wer"] for r in all_rows]),
            "exact_match_rate": round(sum(r["exact_match"] for r in all_rows) / len(all_rows), 4),
        },
        "per_condition": per_condition,
    })

    print("\n  " + "-" * 60)
    print(f"  {'condition':<18}{'median CER':>13}{'median WER':>13}{'exact':>10}")
    print("  " + "-" * 60)
    for name, d in per_condition.items():
        print(f"  {name:<18}{d['cer']['median']:>13}{d['wer']['median']:>13}"
              f"{d['exact_match_rate']:>10.0%}")
    print("  " + "-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
