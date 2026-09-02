import threading
from typing import Any, Iterator
from pathlib import Path
from datetime import UTC, datetime

from reachy_duck.memory import data_directory_for_instance


NOTES_FILENAME = "NOTES.md"
NOTES_HEADER = "# Notes\n\n"
MAX_SEARCH_RESULTS = 20

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


def search_notes(
    query: str,
    max_results: int = 5,
    *,
    instance_path: str | Path | None = None,
) -> dict[str, Any]:
    """Search timestamped note entries case-insensitively."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return {"query": query, "results": []}
    if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
        return {"query": query, "results": []}
    limit = min(max_results, MAX_SEARCH_RESULTS)

    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        _ensure_notes_file(path)
        exact_matches: list[tuple[str, str]] = []
        token_matches: list[tuple[str, str]] = []
        tokens = normalized_query.split()
        for entry in _iter_note_entries(path):
            note_text = entry[1].casefold()
            if normalized_query in note_text:
                exact_matches.append(entry)
                if len(exact_matches) == limit:
                    break
            elif all(token in note_text for token in tokens) and len(token_matches) < limit:
                token_matches.append(entry)

    matches = exact_matches or token_matches
    return {
        "query": query,
        "results": [{"text": text, "context": context} for context, text in matches[:limit]],
    }


def _iter_note_entries(path: Path) -> Iterator[tuple[str, str]]:
    """Yield Markdown note blocks without loading the full document into memory."""
    current: list[str] = []
    with path.open(encoding="utf-8") as notes_file:
        for line in notes_file:
            if line.startswith("## "):
                if current:
                    yield _split_note_entry(current)
                current = [line]
            elif current:
                current.append(line)
    if current:
        yield _split_note_entry(current)


def _split_note_entry(lines: list[str]) -> tuple[str, str]:
    """Separate a note's timestamp heading from its original body text."""
    return lines[0].removeprefix("## ").strip(), "".join(lines[1:]).strip()
