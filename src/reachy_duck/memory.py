import os
import logging
import threading
from pathlib import Path
from dataclasses import dataclass

from reachy_duck.config import PROJECT_ROOT


logger = logging.getLogger(__name__)

DATA_DIRECTORY_NAME = "data"
MEMORY_FILENAME = "MEMORY.md"
MEMORY_HEADER = "# Memory\n\n"

_STORE_LOCK = threading.Lock()


@dataclass(frozen=True)
class ForgetMemoryResult:
    """Result of removing one memory entry."""

    removed: str | None
    candidates: tuple[str, ...]


def persistent_data_directory() -> Path:
    """Return the install-independent user data directory."""
    data_home = os.getenv("XDG_DATA_HOME")
    data_root = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return data_root / "reachy_duck" / DATA_DIRECTORY_NAME


def data_directory_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the writable Markdown data directory for this app instance."""
    if instance_path is not None:
        return Path(instance_path).expanduser() / DATA_DIRECTORY_NAME

    if (PROJECT_ROOT / "pyproject.toml").is_file():
        return PROJECT_ROOT / DATA_DIRECTORY_NAME

    return persistent_data_directory()


def memory_path_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the long-term memory Markdown path for this app instance."""
    return data_directory_for_instance(instance_path) / MEMORY_FILENAME


def normalize_memory_text(text: str) -> str:
    """Collapse an entry to one non-empty Markdown bullet line."""
    return " ".join(text.split()).strip()


def _ensure_memory_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(MEMORY_HEADER, encoding="utf-8")


def _read_memory_entries(path: Path) -> list[str]:
    _ensure_memory_file(path)
    entries: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- ") and line[2:].strip():
            entries.append(line[2:].strip())
    return entries


def list_memory_facts(instance_path: str | Path | None = None) -> list[str]:
    """Return the stored long-term memory entries."""
    with _STORE_LOCK:
        return _read_memory_entries(memory_path_for_instance(instance_path))


def add_memory_fact(instance_path: str | Path | None, text: str) -> str | None:
    """Append one long-term memory entry, avoiding exact duplicates."""
    normalized = normalize_memory_text(text)
    if not normalized:
        return None

    path = memory_path_for_instance(instance_path)
    with _STORE_LOCK:
        entries = _read_memory_entries(path)
        existing = next((entry for entry in entries if entry.casefold() == normalized.casefold()), None)
        if existing is not None:
            return existing
        separator = "" if path.read_text(encoding="utf-8").endswith("\n") else "\n"
        with path.open("a", encoding="utf-8") as memory_file:
            memory_file.write(f"{separator}- {normalized}\n")
    return normalized


def remember(text: str, *, instance_path: str | Path | None = None) -> str | None:
    """Persist one long-term memory entry."""
    return add_memory_fact(instance_path, text)


def forget_memory_fact(instance_path: str | Path | None, *, query: str | None = None) -> ForgetMemoryResult:
    """Remove the first memory entry containing a case-insensitive query."""
    normalized_query = normalize_memory_text(query or "").casefold()
    if not normalized_query:
        return ForgetMemoryResult(removed=None, candidates=())

    path = memory_path_for_instance(instance_path)
    with _STORE_LOCK:
        _ensure_memory_file(path)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        entries = [line.removeprefix("- ").strip() for line in lines if line.startswith("- ") and line[2:].strip()]
        candidates = tuple(entry for entry in entries if normalized_query in entry.casefold())
        if not candidates:
            return ForgetMemoryResult(removed=None, candidates=())

        removed = candidates[0]
        removed_line = next(line for line in lines if line.startswith("- ") and line[2:].strip() == removed)
        lines.remove(removed_line)
        temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            temporary_path.write_text("".join(lines), encoding="utf-8")
            temporary_path.replace(path)
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to remove temporary memory file %s: %s", temporary_path, exc)
        return ForgetMemoryResult(removed=removed, candidates=candidates)


def clear_memory_facts(instance_path: str | Path | None = None) -> None:
    """Replace long-term memory with an empty Markdown document."""
    path = memory_path_for_instance(instance_path)
    with _STORE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(MEMORY_HEADER, encoding="utf-8")


def format_memory_for_prompt(instance_path: str | Path | None = None) -> str:
    """Return the MEMORY.md content as an assistant context fragment."""
    path = memory_path_for_instance(instance_path)
    try:
        with _STORE_LOCK:
            _ensure_memory_file(path)
            memory_document = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        logger.warning("Failed to load memory context from %s: %s", path, exc)
        return ""
    if not memory_document or memory_document == MEMORY_HEADER.strip():
        return ""

    return "\n".join(
        [
            "Long-term internal memory follows. Use it naturally and do not recite it unless relevant:",
            memory_document,
        ]
    )
