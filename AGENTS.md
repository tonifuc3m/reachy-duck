# Reachy Duck Agent Instructions

Read this file before modifying the repository. `README.md` is the authoritative user and deployment guide.

`initial-prompt.md` is the original historical prompt. Do not rewrite it to reflect current status. `README_OLD.md` is
an archived upstream-template document and may contain stale commands; do not treat it as current guidance.

## Project

Reachy Duck is a Reachy Mini Wireless app generated from the official conversation template. It turns Reachy into a
concise, voice-first rubber-duck programming companion with plain-Markdown persistent memory and user-facing notes.

The current product scope is deliberately small:

- realtime voice conversation through the Reachy Mini microphone and speaker;
- a locked rubber-duck profile;
- durable internal memory through `remember` and `forget`;
- timestamped user-facing notes through `add_note` and `read_notes`;
- laptop development with a mock daemon and direct deployment to Reachy Mini Wireless.

Do not add repository awareness, shell/code-writing tools, autonomous agent loops, note synchronization, embeddings,
RAG, vector databases, LangGraph, memory frameworks, Redis, or SQL unless the user starts a later milestone explicitly.

## Architecture

```text
profiles/_reachy_duck_locked_profile/profile.md
    Locked system instructions and enabled LLM tool names.

src/reachy_duck/main.py
    CLI and ReachyMiniApp entry point. Wires daemon-provided hardware, audio,
    tools, realtime conversation, and persistent launcher storage together.

src/reachy_duck/huggingface_realtime.py
    Hugging Face realtime session and shared conversation loop.

src/reachy_duck/prompts.py
    Loads the locked profile and prepends MEMORY.md for each new session.

src/reachy_duck/memory.py
src/reachy_duck/notes.py
    Robot-independent Markdown persistence.

src/reachy_duck/tools/
    LLM tool adapters. One Tool subclass per module.

tests/
    Pytest tests. Storage tests do not require a daemon or robot.
```

Tools are enabled by name in the profile's `default_tools`. `core_tools.py` imports
`reachy_duck.tools.<name>`, finds the concrete `Tool` subclass, instantiates it, advertises its JSON schema to the LLM,
and dispatches calls through async `__call__`.

Keep these concerns separate:

- Markdown storage;
- LLM tool adapters;
- prompt/profile behavior;
- realtime transport;
- Reachy hardware and audio.

## Locked Profile

`config.LOCKED_PROFILE` intentionally selects `_reachy_duck_locked_profile`. Do not add profile switching or bundled
personas merely to satisfy inherited upstream tests. The profile currently enables `remember`, `forget`, `add_note`,
`read_notes`, and selected movement tools.

The assistant should help the user reason, compare working and failing cases, expose assumptions, and narrow hypotheses.
It should not act like an aggressive autonomous coding agent or default to long spoken answers.

## Persistence

`data/MEMORY.md` is internal long-term context. `data/NOTES.md` contains explicit user-facing notes.

- Direct source-checkout calls use the repository's `data/` directory.
- A daemon-launched Wireless app uses `${XDG_DATA_HOME:-~/.local/share}/reachy_duck/data/`.
- On the normal Wireless `pollen` account, the files are
  `/home/pollen/.local/share/reachy_duck/data/MEMORY.md` and `NOTES.md`.
- The Wireless path must remain outside replaceable `site-packages`, including editable installs.
- Memory is loaded when a new realtime session is built. A new fact need not alter the already-running session prompt.
- Storage must remain unit-testable without constructing `ReachyMini` or starting a daemon.

Do not couple persistence to future phone/laptop synchronization.

## Physical Deployment

For the primary acceptance path, run the installed app directly on Reachy Mini Wireless. Its system daemon launches the
registered `reachy_duck` app and supplies an already-connected robot using local media for the onboard microphone and
speaker. Follow `README.md#first-reachy-mini-wireless-test` exactly.

Laptop terminal mode is secondary. `ReachyMini()` can discover `reachy-mini.local:8000` and use WebRTC media, but state
then remains in the laptop checkout. Do not start a second laptop daemon when testing against the physical Wireless
daemon.

The built-in deployed Hugging Face realtime service is the default and normally needs no API key. `HF_TOKEN` is
optional. Never commit `.env`, credentials, or tokens.

## Engineering Rules

- Read before writing and make the smallest correct change.
- Preserve the official Reachy Mini SDK contract and use public SDK APIs.
- Do not hardcode laptop-specific paths or assume physical hardware in storage tests.
- Return `{"error": ...}` from expected tool failures instead of crashing the conversation loop.
- Log operational failures with the module logger; do not use `print` outside genuine CLI output.
- Use typed public signatures, built-in generics, and `X | None`.
- Do not add dependencies without explicit justification and user approval.
- Do not revert unrelated worktree changes.
- Update `README.md` and `.env.example` when behavior or configuration changes.
- Never commit `.env`, virtual environments, caches, build output, bytecode, credentials, or generated runtime state.

## Adding Tools

Subclass `Tool` from `src/reachy_duck/tools/core_tools.py` in a module under `src/reachy_duck/tools/`. Define `name`,
`description`, `parameters_schema`, and async `__call__(self, deps, **kwargs)`. Add the tool name to
`profiles/_reachy_duck_locked_profile/profile.md` only when the assistant should be able to call it.

Storage behavior belongs in a storage module, not directly in robot/audio/realtime code. Use `remember.py`,
`add_note.py`, and `read_notes.py` as examples of the adapter boundary.

## Validation

The existing `.reachy-env` contains the Reachy runtime but may not contain development tools. If `pytest`, `ruff`, or
`mypy` cannot be imported, install the versions declared in `pyproject.toml` into that environment before validating.

```bash
source /home/basf/personal/reachy/.reachy-env/bin/activate
python -m pytest tests/test_memory.py tests/test_main.py tests/test_huggingface_realtime.py -q
python -m ruff check .
python -m ruff format --check <changed-python-files>
python -m mypy --pretty --show-error-codes
reachy-mini-app-assistant check .
```

The generated repository omits the upstream default/persona profile bundle and intentionally locks profile/tool editing.
Consequently, inherited tests for unlocked personality management, missing bundled profiles/avatars, startup profile
selection, and editable Tool Spaces are not applicable. Do not change product behavior merely to make those tests pass.
Always report focused-test results separately from inherited-suite mismatches.

## Known Handoff Note

The generated `src/reachy_duck/static/index.html` and `static/main.js` still contain the template's obsolete OpenAI-key
screen and are not aligned with the current Hugging Face/JSON-RPC backend. This does not block the voice acceptance test,
which uses robot audio and daemon logs. Do not rely on that web page until a later, explicitly scoped UI cleanup.

## Git

The initial baseline exists. Inspect `git status`, `git diff`, and recent commits before committing. Commit or push only
when explicitly requested. Git LFS pointers are used for generated image assets; do not replace them with large binary
blobs accidentally.
