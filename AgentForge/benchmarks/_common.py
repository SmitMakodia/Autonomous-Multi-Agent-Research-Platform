"""Shared helpers for the benchmark harnesses.

Every harness writes a single JSON file into rework-proof/evidence/ containing both its
results and the machine/software context they were produced on, so a reviewer can see what
the numbers apply to. Nothing here fabricates a value: if a measurement cannot be taken,
the field is null and the reason is recorded.
"""

import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENTFORGE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENTFORGE_DIR.parent
EVIDENCE_DIR = REPO_ROOT / "rework-proof" / "evidence"
BACKEND_DIR = AGENTFORGE_DIR / "backend"

API_BASE = "http://127.0.0.1:8081"
LLAMA_BASE = "http://127.0.0.1:8000"


def add_backend_to_path():
    """Backend modules import each other by bare name (config, metrics, ...)."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def gpu_info():
    """Return GPU name / VRAM / driver from nvidia-smi, or None if unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout.strip()
        name, mem, driver = [p.strip() for p in out.split(",")]
        return {"name": name, "memory_total": mem, "driver": driver}
    except Exception as e:
        return {"error": f"nvidia-smi unavailable: {e}"}


def environment():
    """Machine and library context recorded alongside every result set."""
    env = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "gpu": gpu_info(),
    }
    try:
        import torch
        env["torch"] = torch.__version__
        env["torch_cuda"] = torch.version.cuda
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability(0)
            env["compute_capability"] = f"sm_{cap[0]}{cap[1]}"
    except Exception:
        env["torch"] = None
    return env


def summarise(values):
    """min/median/mean/p95/max for a list of numbers. Empty list -> all null."""
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0, "min": None, "median": None, "mean": None, "p95": None, "max": None}
    ordered = sorted(clean)
    p95_index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {
        "n": len(clean),
        "min": round(ordered[0], 2),
        "median": round(statistics.median(ordered), 2),
        "mean": round(statistics.fmean(ordered), 2),
        "p95": round(ordered[p95_index], 2),
        "max": round(ordered[-1], 2),
    }


def write_evidence(name: str, payload: dict) -> Path:
    """Write one evidence file and echo where it went."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{name}.json"
    payload.setdefault("environment", environment())
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\n  -> wrote {path.relative_to(REPO_ROOT)}")
    return path


def require_service(url: str, label: str) -> bool:
    """Check a local service is up. Returns False and explains rather than crashing."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.getcode() < 500
    except Exception as e:
        print(f"  [SKIP] {label} not reachable at {url} ({e})")
        return False
