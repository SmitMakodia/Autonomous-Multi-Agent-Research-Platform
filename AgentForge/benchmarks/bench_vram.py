"""VRAM timeline across the model hot-swap.

The swap is the project's central hardware claim, and until now nothing measured it: the
logs recorded that it happened, never how much memory moved. This samples GPU memory every
100 ms through a complete cycle - LLM resident, LLM evicted, vision model loaded, inference,
vision model freed, LLM reloaded - and records the swap's sub-stage timings from
backend/metrics.py.

Needs exclusive use of the GPU. Stop the AgentForge backend before running, otherwise its
llama-server and this script's will fight over the same process name.

    venv\\Scripts\\python.exe benchmarks\\bench_vram.py
"""

import asyncio
import json
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pynvml import (
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetName,
    nvmlInit,
    nvmlShutdown,
)

from _common import AGENTFORGE_DIR, add_backend_to_path, write_evidence

add_backend_to_path()

from agents.ocr_agent import OCRAgent           # noqa: E402
from config import UPLOADS_DIR                  # noqa: E402
from llm.model_manager import model_manager     # noqa: E402

METRICS_PATH = AGENTFORGE_DIR / "logs" / "metrics.jsonl"
SAMPLE_INTERVAL = 0.1
MIB = 1024 * 1024


class Sampler(threading.Thread):
    """Polls GPU memory on its own thread and timestamps each reading."""

    def __init__(self, handle):
        super().__init__(daemon=True)
        self.handle = handle
        self.samples = []
        self.marks = []
        # Not _stop: Thread already defines a _stop() method and shadowing it breaks join().
        self._stop_event = threading.Event()
        self.t0 = None

    def mark(self, label):
        self.marks.append({"t_s": round(time.perf_counter() - self.t0, 3), "label": label})
        print(f"    [{time.perf_counter() - self.t0:6.2f}s] {label}")

    def run(self):
        self.t0 = time.perf_counter()
        while not self._stop_event.is_set():
            info = nvmlDeviceGetMemoryInfo(self.handle)
            self.samples.append({
                "t_s": round(time.perf_counter() - self.t0, 3),
                "used_mib": round(info.used / MIB, 1),
                "free_mib": round(info.free / MIB, 1),
            })
            time.sleep(SAMPLE_INTERVAL)

    def stop(self):
        self._stop_event.set()
        self.join(timeout=2)


def make_image(path):
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    img = Image.new("RGB", (1100, 200), "white")
    ImageDraw.Draw(img).text(
        (40, 70), "VRAM hot-swap benchmark: Invoice INV-2026-00841", font=font, fill="black")
    img.save(path)
    return path


def window(samples, start, end):
    vals = [s["used_mib"] for s in samples if start <= s["t_s"] <= end]
    return {
        "min_mib": round(min(vals), 1) if vals else None,
        "max_mib": round(max(vals), 1) if vals else None,
        "mean_mib": round(sum(vals) / len(vals), 1) if vals else None,
        "samples": len(vals),
    }


def read_swap_stages(since_iso):
    """Sub-stage timings the OCR agent recorded during this run."""
    if not METRICS_PATH.exists():
        return {}
    wanted = {"ocr.unload_llm", "ocr.load_vision_model", "ocr.inference",
              "ocr.unload_vision_model", "ocr.reload_llm"}
    found = {}
    for line in METRICS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("stage") in wanted and rec.get("ts", "") >= since_iso:
            found[rec["stage"]] = rec["duration_ms"]
    return found


async def main():
    from datetime import datetime, timezone
    print("=" * 70)
    print("VRAM hot-swap benchmark")
    print("=" * 70)

    nvmlInit()
    handle = nvmlDeviceGetHandleByIndex(0)
    name = nvmlDeviceGetName(handle)
    name = name.decode() if isinstance(name, bytes) else name
    total_mib = round(nvmlDeviceGetMemoryInfo(handle).total / MIB, 1)
    print(f"\n  GPU: {name}  ({total_mib} MiB total)")

    image_path = Path(UPLOADS_DIR)
    image_path.mkdir(parents=True, exist_ok=True)
    image_path = make_image(image_path / "_bench_vram.png")

    started_iso = datetime.now(timezone.utc).isoformat()
    sampler = Sampler(handle)
    sampler.start()
    time.sleep(1.0)

    try:
        sampler.mark("baseline (nothing loaded by us)")
        time.sleep(1.5)

        sampler.mark("starting llama-server")
        model_manager.start_llm()
        sampler.mark("llama-server ready")
        time.sleep(2.0)
        llm_window_start = sampler.marks[-1]["t_s"]

        sampler.mark("OCR request begins (triggers hot-swap)")
        swap_start = sampler.marks[-1]["t_s"]
        chunks = await OCRAgent().run(file_path=str(image_path))
        sampler.mark("OCR complete, llama-server restored")
        swap_end = sampler.marks[-1]["t_s"]

        time.sleep(2.0)
        sampler.mark("settled")
        settled = sampler.marks[-1]["t_s"]
    finally:
        sampler.stop()
        model_manager.stop_llm()
        image_path.unlink(missing_ok=True)
        nvmlShutdown()

    samples = sampler.samples
    baseline = window(samples, 0, 1.4)
    llm_resident = window(samples, llm_window_start, swap_start)
    during_swap = window(samples, swap_start, swap_end)
    after = window(samples, swap_end, settled)
    stages = read_swap_stages(started_iso)

    extracted = chunks[0].text if chunks else ""
    payload = {
        "benchmark": "vram",
        "method": {
            "sampler": f"pynvml nvmlDeviceGetMemoryInfo every {SAMPLE_INTERVAL}s on a separate thread",
            "measures": "whole-GPU used memory, so it includes the desktop compositor and any "
                        "browser windows open at the time - it is not process-isolated",
            "cycle": "baseline -> llama-server up -> OCR request -> vision model loaded and freed "
                     "-> llama-server restarted",
            "stage_source": "backend/metrics.py records emitted by agents/ocr_agent.py",
        },
        "gpu": {"name": name, "total_mib": total_mib},
        "windows": {
            "baseline": baseline,
            "llm_resident": llm_resident,
            "during_swap": during_swap,
            "after_restore": after,
        },
        "swap_stage_ms": stages,
        "swap_total_s": round(swap_end - swap_start, 2),
        "ocr_extracted_chars": len(extracted),
        "marks": sampler.marks,
        "samples": samples,
    }
    write_evidence("bench_vram", payload)

    print("\n  " + "-" * 58)
    print(f"  {'window':<22}{'min MiB':>11}{'max MiB':>11}{'mean MiB':>12}")
    print("  " + "-" * 58)
    for label, w in payload["windows"].items():
        print(f"  {label:<22}{w['min_mib']:>11}{w['max_mib']:>11}{w['mean_mib']:>12}")
    print("  " + "-" * 58)
    print(f"\n  Full swap cycle: {payload['swap_total_s']} s")
    for stage, ms in stages.items():
        print(f"    {stage:<28}{ms:>10} ms")


if __name__ == "__main__":
    asyncio.run(main())
