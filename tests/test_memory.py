import re
from pathlib import Path
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

import pytest

import reachy_duck.memory as memory_mod
import reachy_duck.prompts as prompts_mod
from reachy_duck.notes import add_note, read_notes, notes_path_for_instance
from reachy_duck.memory import (
    remember,
    list_memory_facts,
    forget_memory_fact,
    memory_path_for_instance,
    persistent_data_directory,
    data_directory_for_instance,
)
from reachy_duck.tools.forget import Forget
from reachy_duck.tools.add_note import AddNote
from reachy_duck.tools.remember import Remember
from reachy_duck.tools.core_tools import ToolDependencies
from reachy_duck.tools.read_notes import ReadNotes


def tool_dependencies(instance_path: Path) -> ToolDependencies:
    """Build storage-tool dependencies without a robot or daemon."""
    return ToolDependencies(
        reachy_mini=MagicMock(),
        movement_manager=MagicMock(),
        instance_path=instance_path,
    )


@pytest.mark.asyncio
async def test_remember_persists_markdown_memory(tmp_path: Path) -> None:
    """Remember should append persistent context to MEMORY.md."""
    result = await Remember()(tool_dependencies(tmp_path), text="This project uses pytest.")

    assert result == {"saved": "This project uses pytest."}
    assert memory_path_for_instance(tmp_path).read_text(encoding="utf-8") == (
        "# Memory\n\n- This project uses pytest.\n"
    )
    assert list_memory_facts(tmp_path) == ["This project uses pytest."]


def test_direct_storage_apis_work_without_runtime_dependencies(tmp_path: Path) -> None:
    """Public storage APIs should match the no-daemon manual verification path."""
    assert remember("I use pytest for this project", instance_path=tmp_path) == "I use pytest for this project"
    assert add_note("Buy milk tomorrow", instance_path=tmp_path) == "Buy milk tomorrow"
    assert "Buy milk tomorrow" in read_notes(tmp_path)


def test_direct_storage_apis_use_default_data_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented one-argument calls should use the default data directory."""
    monkeypatch.setattr(memory_mod, "PROJECT_ROOT", tmp_path)
    (tmp_path / "pyproject.toml").touch()

    assert remember("I use pytest for this project") == "I use pytest for this project"
    assert add_note("Buy milk tomorrow") == "Buy milk tomorrow"
    assert "Buy milk tomorrow" in read_notes()
    assert (tmp_path / "data" / "MEMORY.md").is_file()
    assert (tmp_path / "data" / "NOTES.md").is_file()


def test_installed_app_uses_persistent_user_data_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An installed app should keep data outside replaceable site-packages."""
    monkeypatch.setattr(memory_mod, "PROJECT_ROOT", tmp_path / "site-packages")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))

    assert data_directory_for_instance() == tmp_path / "user-data" / "reachy_duck" / "data"


def test_launcher_data_directory_ignores_editable_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Daemon-launched apps should persist outside an editable checkout."""
    monkeypatch.setattr(memory_mod, "PROJECT_ROOT", tmp_path / "checkout")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user-data"))
    (tmp_path / "checkout").mkdir()
    (tmp_path / "checkout" / "pyproject.toml").touch()

    assert data_directory_for_instance() == tmp_path / "checkout" / "data"
    assert persistent_data_directory() == tmp_path / "user-data" / "reachy_duck" / "data"


def test_forget_removes_matching_markdown_memory(tmp_path: Path) -> None:
    """The existing forget behavior should continue to work with Markdown storage."""
    remember("Uses pytest", instance_path=tmp_path)
    remember("Prefers concise explanations", instance_path=tmp_path)
    memory_path_for_instance(tmp_path).write_text(
        "# Memory\n\nProject context stays here.\n\n- Uses pytest\n- Prefers concise explanations\n",
        encoding="utf-8",
    )

    result = forget_memory_fact(tmp_path, query="pytest")

    assert result.removed == "Uses pytest"
    assert list_memory_facts(tmp_path) == ["Prefers concise explanations"]
    assert "Project context stays here." in memory_path_for_instance(tmp_path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_forget_tool_removes_persistent_memory(tmp_path: Path) -> None:
    """Forget should intentionally remove a matching persistent memory entry."""
    remember("Uses pytest", instance_path=tmp_path)

    result = await Forget()(tool_dependencies(tmp_path), query="pytest")

    assert result == {"removed": "Uses pytest"}
    assert list_memory_facts(tmp_path) == []


@pytest.mark.asyncio
async def test_add_note_appends_timestamped_markdown(tmp_path: Path) -> None:
    """AddNote should append a timestamped entry to NOTES.md."""
    result = await AddNote()(tool_dependencies(tmp_path), text="Tomorrow I am going grocery shopping.")
    notes = notes_path_for_instance(tmp_path).read_text(encoding="utf-8")

    assert result == {"saved": "Tomorrow I am going grocery shopping."}
    assert re.fullmatch(
        r"# Notes\n\n## \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC\n"
        r"<!-- note-id: note_[0-9a-f]{32} -->\n\n"
        r"Tomorrow I am going grocery shopping\.\n\n",
        notes,
    )


@pytest.mark.asyncio
async def test_read_notes_returns_persistent_notes(tmp_path: Path) -> None:
    """ReadNotes should return all notes from storage."""
    add_note("First note", instance_path=tmp_path)
    add_note("Second note", instance_path=tmp_path)

    result = await ReadNotes()(tool_dependencies(tmp_path))

    assert result["notes"] == read_notes(tmp_path)
    assert "First note" in result["notes"]
    assert "Second note" in result["notes"]


def test_notes_append_and_survive_a_new_read(tmp_path: Path) -> None:
    """Separate storage calls should preserve every timestamped note."""
    add_note("First note", instance_path=tmp_path)
    add_note("Second note", instance_path=tmp_path)

    persisted = notes_path_for_instance(tmp_path).read_text(encoding="utf-8")

    assert persisted.count("## ") == 2
    assert persisted.index("First note") < persisted.index("Second note")
    assert read_notes(tmp_path) == persisted


def test_concurrent_note_writes_remain_complete(tmp_path: Path) -> None:
    """Concurrent in-process writes should not overwrite or interleave notes."""
    note_texts = [f"Note {index}" for index in range(10)]

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(lambda text: add_note(text, instance_path=tmp_path), note_texts))

    persisted = read_notes(tmp_path)
    assert persisted.count("## ") == len(note_texts)
    assert all(text in persisted for text in note_texts)


def test_storage_creates_missing_data_directory_and_files(tmp_path: Path) -> None:
    """Storage operations should safely initialize an absent data directory."""
    instance_path = tmp_path / "missing" / "instance"

    assert read_notes(instance_path) == "# Notes\n\n"
    assert remember("Prefers concise explanations.", instance_path=instance_path) == "Prefers concise explanations."
    assert memory_path_for_instance(instance_path).is_file()
    assert notes_path_for_instance(instance_path).is_file()


def test_prompt_includes_memory_document(tmp_path: Path) -> None:
    """Session instructions should prepend MEMORY.md for the active app instance."""
    remember("Prefers concise answers", instance_path=tmp_path)

    instructions = prompts_mod.get_session_instructions(instance_path=tmp_path)

    assert instructions.startswith("Long-term internal memory follows")
    assert "# Memory\n\n- Prefers concise answers" in instructions
    assert "voice-first rubber-duck programming companion" in instructions


def test_memory_changes_apply_when_session_instructions_are_rebuilt(tmp_path: Path) -> None:
    """New sessions should reload memory while existing instructions remain unchanged."""
    first_instructions = prompts_mod.get_session_instructions(instance_path=tmp_path)

    remember("Uses pytest", instance_path=tmp_path)
    second_instructions = prompts_mod.get_session_instructions(instance_path=tmp_path)

    assert "Uses pytest" not in first_instructions
    assert "Uses pytest" in second_instructions
