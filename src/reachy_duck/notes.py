import threading
from pathlib import Path
from datetime import UTC, datetime

from reachy_duck.memory import data_directory_for_instance


NOTES_FILENAME = "NOTES.md"
NOTES_HEADER = "# Notes\n\n"

_STORE_LOCK = threading.Lock()


def notes_path_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the user-facing notes Markdown path for this app instance."""
    return data_directory_for_instance(instance_path) / NOTES_FILENAME


def _ensure_notes_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(NOTES_HEADER, encoding="utf-8")


def add_note(text: str, *, instance_path: str | Path | None = None) -> str | None:
    """Append one timestamped note and return the stored text."""
    normalized = text.strip()
    if not normalized:
        return None

    path = notes_path_for_instance(instance_path)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    with _STORE_LOCK:
        _ensure_notes_file(path)
        separator = "" if path.read_text(encoding="utf-8").endswith("\n") else "\n"
        with path.open("a", encoding="utf-8") as notes_file:
            notes_file.write(f"{separator}## {timestamp}\n\n{normalized}\n\n")
    return normalized


def read_notes(instance_path: str | Path | None = None) -> str:
    """Return the complete user-facing notes Markdown document."""
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        _ensure_notes_file(path)
        return path.read_text(encoding="utf-8")
