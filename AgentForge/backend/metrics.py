"""Per-stage timing, written as JSONL to logs/metrics.jsonl.

The pipeline had no instrumentation at all: no latency, no throughput, no correlation.
query_id was minted in main.py and then never logged, so concurrent runs were
indistinguishable in log.log. Every record here carries query_id and session_id so a run
can be reconstructed end to end.

Deliberately not a metrics framework - one append-only file that the benchmark scripts
read back. No Prometheus, no OpenTelemetry, nothing to run alongside the app.

    with stage("retrieve") as f:
        chunks = retriever.retrieve_and_rerank(...)
        f["chunks"] = len(chunks)
"""

import json
import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from config import BASE_DIR

METRICS_PATH = BASE_DIR / "logs" / "metrics.jsonl"

_run: ContextVar[dict] = ContextVar("agentforge_run", default={})
_write_lock = threading.Lock()


def set_run(query_id: str = "", session_id: str = "") -> None:
    """Tag every stage recorded on this task with the run it belongs to."""
    _run.set({"query_id": query_id, "session_id": session_id})


def emit(event: str, **fields) -> None:
    """Append one record. Never raises - instrumentation must not break a query."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **_run.get({}),
        **fields,
    }
    try:
        os.makedirs(METRICS_PATH.parent, exist_ok=True)
        line = json.dumps(record, default=str)
        with _write_lock, open(METRICS_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as e:  # pragma: no cover - diagnostics only
        print(f"[metrics] failed to write record: {e}")


@contextmanager
def stage(name: str, **fields):
    """Time a block and record it. The yielded dict is merged into the record."""
    extra = dict(fields)
    started = time.perf_counter()
    status = "ok"
    try:
        yield extra
    except Exception as e:
        status = "error"
        extra["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        emit(
            "stage",
            stage=name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            status=status,
            **extra,
        )
