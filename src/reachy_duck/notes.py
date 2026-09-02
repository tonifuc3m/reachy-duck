"""Plain-Markdown storage for user-facing notes."""

import os
import re
import uuid
import logging
import tempfile
import threading
from typing import Any, Literal
from pathlib import Path
from datetime import UTC, datetime
from dataclasses import replace, dataclass

from reachy_duck.memory import data_directory_for_instance


logger = logging.getLogger(__name__)

NOTES_FILENAME = "NOTES.md"
NOTES_HEADER = "# Notes\n\n"
MAX_SEARCH_RESULTS = 20
_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\n$")
_NOTE_ID_RE = re.compile(r"^<!-- note-id: (note_[0-9a-f]{32}) -->\n$")
_UPDATED_AT_RE = re.compile(r"^<!-- updated-at: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC) -->\n$")

_STORE_LOCK = threading.Lock()


class NoteFormatError(ValueError):
    """Raised when NOTES.md cannot be safely parsed and preserved."""


@dataclass(frozen=True)
class Note:
    """One user-facing note with stable storage metadata."""

    id: str
    created_at: str
    updated_at: str | None
    text: str


def notes_path_for_instance(instance_path: str | Path | None = None) -> Path:
    """Return the user-facing notes Markdown path for this app instance."""
    return data_directory_for_instance(instance_path) / NOTES_FILENAME


def _ensure_notes_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(NOTES_HEADER, encoding="utf-8")


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _as_iso8601(timestamp: str) -> str:
    parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    return parsed.isoformat().replace("+00:00", "Z")


def _as_heading_timestamp(timestamp: str) -> str:
    """Format one stored UTC ISO-8601 value for the human-readable heading."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _normalize_text(text: str) -> str:
    return text.strip()


def _parse_notes(document: str) -> tuple[list[Note], bool]:
    """Parse a complete canonical or legacy notes document without changing it."""
    if not document.startswith(NOTES_HEADER):
        raise NoteFormatError("NOTES.md must begin with '# Notes' followed by a blank line")
    remainder = document[len(NOTES_HEADER) :]
    if not remainder:
        return [], False

    lines = remainder.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if not starts or starts[0] != 0:
        raise NoteFormatError("NOTES.md contains text outside recognized note entries")

    notes: list[Note] = []
    needs_migration = False
    seen_ids: set[str] = set()
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        heading = _HEADING_RE.fullmatch(lines[start])
        if heading is None:
            raise NoteFormatError("NOTES.md contains an invalid note timestamp heading")
        created_heading = heading.group(1)
        try:
            created_at = _as_iso8601(created_heading)
        except ValueError as exc:
            raise NoteFormatError("NOTES.md contains an invalid note timestamp") from exc

        body_lines = lines[start + 1 : end]
        note_id: str | None = None
        updated_at: str | None = None
        if body_lines and (match := _NOTE_ID_RE.fullmatch(body_lines[0])):
            note_id = match.group(1)
            body_lines = body_lines[1:]
        if body_lines and (match := _UPDATED_AT_RE.fullmatch(body_lines[0])):
            updated_heading = match.group(1)
            try:
                updated_at = _as_iso8601(updated_heading)
            except ValueError as exc:
                raise NoteFormatError("NOTES.md contains an invalid update timestamp") from exc
            body_lines = body_lines[1:]
        if body_lines and body_lines[0] == "\n":
            body_lines = body_lines[1:]
        text = "".join(body_lines).strip()
        if not text:
            raise NoteFormatError("NOTES.md contains an empty note entry")
        if note_id is None:
            note_id = f"note_{uuid.uuid4().hex}"
            needs_migration = True
        elif note_id in seen_ids:
            raise NoteFormatError("NOTES.md contains duplicate note IDs")
        seen_ids.add(note_id)
        notes.append(Note(note_id, created_at, updated_at, text))
    return notes, needs_migration


def _serialize_notes(notes: list[Note]) -> str:
    """Serialize notes to the deterministic Markdown representation."""
    blocks: list[str] = []
    for note in notes:
        metadata = [f"<!-- note-id: {note.id} -->"]
        if note.updated_at is not None:
            metadata.append(f"<!-- updated-at: {_as_heading_timestamp(note.updated_at)} -->")
        blocks.append(f"## {_as_heading_timestamp(note.created_at)}\n" + "\n".join(metadata) + f"\n\n{note.text}\n\n")
    return NOTES_HEADER + "".join(blocks)


def _atomic_write(path: Path, document: str) -> None:
    """Durably write a complete document before replacing its old version."""
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temporary_file:
            temporary_name = temporary_file.name
            temporary_file.write(document)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        Path(temporary_name).replace(path)
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to remove temporary notes file %s: %s", temporary_name, exc)


def _load_structured_notes(path: Path) -> tuple[list[Note], bool]:
    """Parse notes and report whether a migration is required while holding the lock."""
    _ensure_notes_file(path)
    return _parse_notes(path.read_text(encoding="utf-8"))


def add_note(text: str, *, instance_path: str | Path | None = None) -> str | None:
    """Append one timestamped note and return its normalized text."""
    normalized = _normalize_text(text)
    if not normalized:
        return None
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        notes, _ = _load_structured_notes(path)
        notes.append(Note(f"note_{uuid.uuid4().hex}", _as_iso8601(_timestamp()), None, normalized))
        _atomic_write(path, _serialize_notes(notes))
    return normalized


def read_notes(instance_path: str | Path | None = None) -> str:
    """Return the complete user-facing notes Markdown document unchanged."""
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        _ensure_notes_file(path)
        return path.read_text(encoding="utf-8")


def list_notes(instance_path: str | Path | None = None) -> list[Note]:
    """Return structured notes, migrating legacy entries on first structured access."""
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        notes, needs_migration = _load_structured_notes(path)
        if needs_migration:
            _atomic_write(path, _serialize_notes(notes))
        return notes


def edit_note(
    note_id: str,
    text: str,
    mode: Literal["replace", "append"] = "replace",
    *,
    instance_path: str | Path | None = None,
) -> Note | None:
    """Replace or append to exactly one note, returning the saved entry."""
    normalized_id = note_id.strip()
    normalized_text = _normalize_text(text)
    if not normalized_id or not normalized_text:
        return None
    if mode not in {"replace", "append"}:
        raise ValueError("mode must be 'replace' or 'append'")
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        notes, _ = _load_structured_notes(path)
        for index, note in enumerate(notes):
            if note.id == normalized_id:
                updated_text = normalized_text if mode == "replace" else f"{note.text}\n\n{normalized_text}"
                updated = replace(note, text=updated_text, updated_at=_as_iso8601(_timestamp()))
                notes[index] = updated
                _atomic_write(path, _serialize_notes(notes))
                return updated
    return None


def delete_note(note_id: str, *, instance_path: str | Path | None = None) -> Note | None:
    """Delete exactly one note, returning the removed entry."""
    normalized_id = note_id.strip()
    if not normalized_id:
        return None
    path = notes_path_for_instance(instance_path)
    with _STORE_LOCK:
        notes, _ = _load_structured_notes(path)
        for index, note in enumerate(notes):
            if note.id == normalized_id:
                del notes[index]
                _atomic_write(path, _serialize_notes(notes))
                return note
    return None


def search_notes(
    query: str,
    max_results: int = 5,
    *,
    instance_path: str | Path | None = None,
) -> dict[str, Any]:
    """Search timestamped note entries case-insensitively."""
    normalized_query = query.strip().casefold()
    if not normalized_query or not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
        return {"query": query, "results": []}
    limit = min(max_results, MAX_SEARCH_RESULTS)
    tokens = normalized_query.split()
    exact_matches: list[Note] = []
    token_matches: list[Note] = []
    for note in list_notes(instance_path):
        note_text = note.text.casefold()
        if normalized_query in note_text:
            exact_matches.append(note)
            if len(exact_matches) == limit:
                break
        elif all(token in note_text for token in tokens) and len(token_matches) < limit:
            token_matches.append(note)
    matches = exact_matches or token_matches
    return {
        "query": query,
        "results": [
            {"text": note.text, "context": _as_heading_timestamp(note.created_at)} for note in matches[:limit]
        ],
    }
