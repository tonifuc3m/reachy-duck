"""Storage and tool tests for editable user-facing notes."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import reachy_duck.notes as notes_mod
from reachy_duck.notes import (
    NOTES_HEADER,
    NoteFormatError,
    add_note,
    edit_note,
    list_notes,
    read_notes,
    delete_note,
    notes_path_for_instance,
)
from reachy_duck.tools.edit_note import EditNote
from reachy_duck.tools.core_tools import ToolDependencies
from reachy_duck.tools.read_notes import ReadNotes
from reachy_duck.tools.delete_note import DeleteNote


def tool_dependencies(instance_path: Path) -> ToolDependencies:
    """Build storage tool dependencies without a robot or daemon."""
    return ToolDependencies(reachy_mini=MagicMock(), movement_manager=MagicMock(), instance_path=instance_path)


def test_structured_reads_assign_stable_distinct_ids(tmp_path: Path) -> None:
    """New notes retain opaque IDs alongside their complete Markdown document."""
    add_note("Buy milk", instance_path=tmp_path)
    add_note("Call garage", instance_path=tmp_path)

    entries = list_notes(tmp_path)

    assert len({entry.id for entry in entries}) == 2
    assert all(entry.id.startswith("note_") for entry in entries)
    assert all(entry.created_at.endswith("Z") for entry in entries)
    assert all(entry.updated_at is None for entry in entries)
    assert "Buy milk" in read_notes(tmp_path)


def test_legacy_migration_preserves_order_and_is_idempotent(tmp_path: Path) -> None:
    """A legacy document receives IDs exactly once without losing note text."""
    path = notes_path_for_instance(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        "# Notes\n\n## 2026-09-01 10:00:00 UTC\n\nFirst note.\n\n## 2026-09-02 11:00:00 UTC\n\nSecond note.\n\n",
        encoding="utf-8",
    )

    first_read = list_notes(tmp_path)
    first_document = read_notes(tmp_path)
    second_read = list_notes(tmp_path)

    assert [entry.text for entry in first_read] == ["First note.", "Second note."]
    assert [entry.id for entry in first_read] == [entry.id for entry in second_read]
    assert read_notes(tmp_path) == first_document
    assert first_document.index("First note.") < first_document.index("Second note.")


def test_malformed_notes_fail_without_rewriting_bytes(tmp_path: Path) -> None:
    """Unsafe documents remain exactly untouched when structured parsing fails."""
    path = notes_path_for_instance(tmp_path)
    path.parent.mkdir(parents=True)
    original = "# Notes\n\nunrecognized text\n"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(NoteFormatError):
        list_notes(tmp_path)

    assert path.read_text(encoding="utf-8") == original


def test_replace_append_and_delete_affect_only_selected_note(tmp_path: Path) -> None:
    """Mutations preserve identity/order and produce a canonical empty document."""
    add_note("Buy milk", instance_path=tmp_path)
    add_note("Call garage", instance_path=tmp_path)
    milk, garage = list_notes(tmp_path)

    replaced = edit_note(milk.id, "Buy oat milk", instance_path=tmp_path)
    appended = edit_note(garage.id, "Ask about tyres", "append", instance_path=tmp_path)

    assert replaced is not None
    assert replaced.id == milk.id
    assert replaced.created_at == milk.created_at
    assert replaced.updated_at is not None
    assert appended is not None
    assert appended.text == "Call garage\n\nAsk about tyres"
    assert [entry.id for entry in list_notes(tmp_path)] == [milk.id, garage.id]
    assert delete_note(milk.id, instance_path=tmp_path) is not None
    assert delete_note(garage.id, instance_path=tmp_path) is not None
    assert read_notes(tmp_path) == NOTES_HEADER


def test_invalid_or_unknown_mutations_leave_document_unchanged(tmp_path: Path) -> None:
    """Invalid inputs and missing IDs never create or alter notes."""
    add_note("Buy milk", instance_path=tmp_path)
    path = notes_path_for_instance(tmp_path)
    original = path.read_text(encoding="utf-8")

    assert edit_note("", "new text", instance_path=tmp_path) is None
    assert edit_note("unknown", "new text", instance_path=tmp_path) is None
    assert delete_note("unknown", instance_path=tmp_path) is None
    with pytest.raises(ValueError, match="mode"):
        edit_note(list_notes(tmp_path)[0].id, "new text", "merge", instance_path=tmp_path)  # type: ignore[arg-type]

    assert path.read_text(encoding="utf-8") == original


def test_failed_atomic_write_leaves_existing_document_intact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A persistence failure reports no mutation and leaves the prior document in place."""
    add_note("Buy milk", instance_path=tmp_path)
    note = list_notes(tmp_path)[0]
    path = notes_path_for_instance(tmp_path)
    original = path.read_text(encoding="utf-8")

    def fail_write(path: Path, document: str) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(notes_mod, "_atomic_write", fail_write)
    with pytest.raises(OSError, match="simulated"):
        edit_note(note.id, "Buy oat milk", instance_path=tmp_path)

    assert path.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_note_tools_return_structured_results_and_expected_errors(tmp_path: Path) -> None:
    """Tool adapters keep expected validation and missing-note failures in-band."""
    add_note("Buy milk", instance_path=tmp_path)
    dependencies = tool_dependencies(tmp_path)
    entry = (await ReadNotes()(dependencies))["entries"][0]

    updated = await EditNote()(dependencies, note_id=entry["id"], text="Buy oat milk", mode="replace")
    deleted = await DeleteNote()(dependencies, note_id=entry["id"])

    assert updated["updated"]["id"] == entry["id"]
    assert updated["updated"]["text"] == "Buy oat milk"
    assert deleted == {"deleted": {"id": entry["id"], "text": "Buy oat milk"}}
    assert await EditNote()(dependencies, note_id="missing", text="Nope") == {"error": "note not found"}
    assert await DeleteNote()(dependencies, note_id="") == {"error": "note_id must be a non-empty string"}
