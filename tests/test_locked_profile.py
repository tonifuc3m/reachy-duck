"""Contract tests for the intentionally locked Reachy Duck profile."""

from reachy_duck.config import DEFAULT_PROFILES_DIRECTORY
from reachy_duck.profile_store import read_profile_from_directory


def test_locked_profile_exposes_explicit_sleep_tool_and_intent_guard() -> None:
    """Explicit endings sleep the session; a bare word mention must not."""
    profile = read_profile_from_directory(
        "_reachy_duck_locked_profile",
        DEFAULT_PROFILES_DIRECTORY / "_reachy_duck_locked_profile",
    )

    assert "go_to_sleep" in profile.default_tools
    assert "edit_note" in profile.default_tools
    assert "delete_note" in profile.default_tools
    assert "Good night" in profile.instructions
    assert "You can sleep now" in profile.instructions
    assert "Stop for now" in profile.instructions
    assert "Do not call it merely because" in profile.instructions
