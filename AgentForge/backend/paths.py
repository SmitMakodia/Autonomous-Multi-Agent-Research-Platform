"""Filesystem confinement for untrusted paths.

Two different untrusted sources reach the filesystem:

1. Multipart upload filenames from the browser (``main.py``).
2. ``file_path`` tool arguments produced by the LLM. ``mcp_server.execute_tool_plan``
   splats model-generated arguments straight into the agents, so a prompt-injected web
   page can otherwise steer ``read_local_file`` or ``ocr_image`` at any file the process
   can read, and the contents come back in the answer.

Both funnel through here so the guard lives in one place instead of at every caller.
"""

from pathlib import Path

# Extensions the pipeline can actually parse: file_read_agent.py dispatches on the first
# group, orchestrator.py routes the second group to the OCR agent. Anything else is
# written to disk and then dropped, so there is no reason to accept it.
ALLOWED_UPLOAD_EXTENSIONS = frozenset({
    ".txt", ".md", ".json", ".csv", ".docx", ".pptx", ".xlsx", ".pdf",
    ".png", ".jpg", ".jpeg", ".webp",
})

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MiB


class UnsafePathError(ValueError):
    """A supplied path escaped its allowed root or is otherwise not accepted."""


def safe_upload_name(filename: str) -> str:
    """Reduce a client-supplied upload filename to a bare, allowlisted basename.

    Strips any directory component (both separators, so this holds on POSIX too) and
    rejects absolute paths, drive letters, and traversal segments rather than silently
    rewriting them.
    """
    if not filename or not filename.strip():
        raise UnsafePathError("empty filename")

    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    if not name or name in {".", ".."}:
        raise UnsafePathError(f"invalid filename: {filename!r}")
    if ":" in name:  # C:file.txt is drive-relative on Windows
        raise UnsafePathError(f"invalid filename: {filename!r}")

    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UnsafePathError(f"unsupported file type: {suffix or '(none)'}")

    return name


def resolve_within(root, candidate: str) -> Path:
    """Resolve ``candidate`` and require the result to sit inside ``root``.

    Relative paths and bare filenames are interpreted against ``root``. Symlinks and
    ``..`` are collapsed by ``resolve()`` before the containment check, so neither can be
    used to climb out.
    """
    root_path = Path(root).resolve()

    if not candidate or not str(candidate).strip():
        raise UnsafePathError("empty path")

    path = Path(candidate)
    if not path.is_absolute():
        path = root_path / path
    path = path.resolve()

    if path != root_path and not path.is_relative_to(root_path):
        raise UnsafePathError(f"path escapes {root_path}: {candidate!r}")

    return path


def resolve_upload(root, candidate: str) -> Path:
    """``resolve_within``, but falling back to the basename inside ``root``.

    Preserves the recovery the file agent already relied on: the LLM frequently echoes a
    path from a previous turn or invents a plausible-looking directory. Retrying the bare
    filename inside uploads keeps that working without allowing an escape.
    """
    try:
        resolved = resolve_within(root, candidate)
        if resolved.exists():
            return resolved
    except UnsafePathError:
        pass

    bare = str(candidate).replace("\\", "/").rsplit("/", 1)[-1]
    return resolve_within(root, bare)
