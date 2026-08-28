# Reachy Duck — Project Instructions

## Goal

This repository is for a **Reachy Mini Wireless** app that turns Reachy into a persistent, voice-first rubber-duck programming companion.

The intended experience is:

* I can talk to Reachy while programming.
* Reachy helps me reason through problems rather than immediately taking over.
* Reachy can remember durable information across sessions.
* Reachy can save explicit user-facing notes when I ask it to.
* Eventually Reachy should be aware of the coding repository I am working in and help me reason about it.
* Later I also want notes to be easily accessible from my laptop and phone.

The current priority is to make the core architecture correct, simple, testable, and suitable for later deployment on a Reachy Mini Wireless.

---

## Current development environment

I am currently developing on my laptop without the physical Reachy connected.

The project was generated with the official Reachy Mini conversation app scaffolder.

Repository:

```
~/personal/reachy/reachy-duck/reachy_duck
```

The working Python environment is:

```
~/personal/reachy/.reachy-env
```

Activate it with:

```
source ~/personal/reachy/.reachy-env/bin/activate
```

The Reachy SDK installation in that environment is working.

The generated application passes:

```
reachy-mini-app-assistant check .
```

For laptop development, a real Reachy is not required. When robot connectivity is needed, use the lightweight mock/simulation setup rather than assuming hardware is present.

Do not introduce changes that make basic storage/tool tests depend on a Reachy daemon.

---

## Important Git state

The scaffolder initialized a fresh Git repository, but there are currently no commits.

Therefore:

```
git diff
```

does not show the implementation changes because all repository files are still untracked.

Before creating an initial commit:

1. inspect the repository,
2. verify the current implementation,
3. confirm that no secrets or inappropriate generated files will be committed,
4. inspect `.gitignore`,
5. only then create a sensible initial commit.

Do not commit `.env` or credentials.

`.env.example` is expected and may be committed.

---

## What has already been implemented

A first v0 implementation has already been produced.

Reported changes include:

### Persistent memory

```
data/MEMORY.md
```

This is intended to hold Reachy's durable internal memory.

Examples:

* "Remember that this project uses pytest."
* "Remember that I prefer concise explanations."

### User-facing notes

```
data/NOTES.md
```

This is intended for explicit notes I ask Reachy to save.

Example:

* "Tomorrow I am going grocery shopping, write that down."

### Intended LLM tools

The app is intended to expose:

```
remember(text)
add_note(text)
read_notes()
```

The previous implementation also retained an existing `forget` tool.

### Prompt behavior

The current implementation reportedly:

* loads persistent memory into the instructions for new conversations,
* updates the locked Reachy profile with rubber-duck behavior,
* guides the model on when to use memory and notes tools.

### Storage implementation

The previous implementation reportedly changed:

```
src/reachy_duck/memory.py
```

to Markdown-backed persistent storage.

It also added:

```
src/reachy_duck/notes.py
```

for notes storage.

The official scaffolder identified these as important customization points:

```
profiles/_reachy_duck_locked_profile/profile.md
src/reachy_duck/tools/
```

Inspect those carefully.

---

## Verification already reported

The previous implementation reported:

* feature tests: 6 passed
* Ruff check: passed
* Ruff format check: passed
* mypy strict: passed
* tool registry loaded the requested schemas
* Python compilation passed
* `git diff --check` passed

The complete upstream suite reportedly produced:

```
257 passed
65 failed
```

The claim was that the 65 failures are pre-existing mismatches in the generated template because the generated app only contains a locked profile while upstream tests expect bundled profiles, avatars, and unlocked behavior.

Do not blindly trust this claim.

Verify it where practical and determine whether any failing tests are actually related to our changes.

---

## Important issue discovered during manual testing

I manually tried:

```
from reachy_duck.memory import remember
from reachy_duck.notes import add_note, read_notes
```

Results:

* `remember` could not be imported from `reachy_duck.memory`
* `add_note("Buy milk tomorrow")` raised a missing positional argument error
* `read_notes()` worked and returned the current notes file

This does NOT necessarily mean the implementation is broken.

It may mean the LLM tool functions are wrappers defined elsewhere and the storage modules have lower-level APIs.

Your first job is to understand the actual architecture rather than assuming the intended API.

---

# Immediate tasks

## 1. Inspect the current implementation

Before modifying code, determine:

1. where `remember` is actually defined,
2. where `add_note` is actually defined,
3. where `read_notes` is actually defined,
4. the exact signatures of all three,
5. what the extra argument to `add_note` is,
6. where each tool is registered,
7. how the locked profile enables the tools,
8. how `MEMORY.md` is injected into session instructions,
9. how storage paths are resolved,
10. how source-checkout, launcher-instance, and installed-app storage differ.

Explain the architecture concisely.

---

## 2. Verify the v0 behavior

Verify the implementation with tests and direct Python calls.

I want a simple manual verification path that does not require a Reachy daemon.

The equivalent behaviors must work:

```
remember("I use pytest for this project")

add_note("Buy milk tomorrow")

read_notes()
```

If the public tool functions require runtime/tool context arguments, explain that clearly and provide the correct manual invocation.

If appropriate, expose or use lower-level storage APIs for direct testing instead of changing the tool architecture unnecessarily.

Do not redesign working code merely to make an interactive Python example prettier.

---

## 3. Inspect storage contents

Verify that:

```
data/MEMORY.md
data/NOTES.md
```

are created safely if missing.

Verify that:

* notes are appended rather than overwritten,
* notes include a useful timestamp,
* memory survives process restarts,
* concurrent writes are handled safely enough for this application,
* Markdown remains human-readable.

Do not introduce a database.

---

## 4. Verify prompt injection

Confirm that stored memory is actually made available to the assistant on a NEW conversation/session.

Check:

* where the base instructions are built,
* when memory is loaded,
* whether memory updates affect subsequent sessions,
* whether every tool call unnecessarily rebuilds context,
* whether missing or empty `MEMORY.md` is handled cleanly.

Keep this architecture simple.

---

## 5. Verify tool-selection behavior

The desired semantics are:

### remember

Use only for durable information that may be useful later.

Examples:

```
"Remember that this project uses pytest."

"Remember that I prefer short explanations."
```

Do NOT call `remember` for normal conversation.

### add_note

Use when I explicitly ask Reachy to save/write something down.

Examples:

```
"Write down that I need milk tomorrow."

"Make a note that I have to email Alice."
```

Do NOT silently treat ordinary conversation as a note.

### read_notes

Use when I ask for my saved notes.

Examples:

```
"What notes do I have?"

"What did I write down?"
```

### forget

If retained, it should remove persistent memory intentionally and safely.

Verify that existing behavior still works.

---

## 6. Rubber-duck personality

Reachy should behave like a programming rubber duck, not like an aggressive autonomous coding agent.

Preferred behavior:

* concise spoken responses,
* asks useful questions,
* helps me articulate assumptions,
* helps compare working vs failing behavior,
* helps narrow hypotheses,
* does not immediately dump a giant solution,
* can still give a direct answer when I explicitly ask for one.

Example:

Instead of immediately saying:

```
"The bug is caused by X. Replace Y with Z."
```

Prefer something like:

```
"What changed between the working case and the failing case?"
```

or:

```
"Is that fixture async in the working test too?"
```

The profile should encourage reasoning dialogue suitable for voice interaction.

Do not make responses overly verbose.

---

## 7. Tests

Ensure there are focused tests for at least:

* memory persistence,
* note persistence,
* note timestamps,
* missing directory creation,
* missing file creation,
* read_notes,
* remember behavior,
* forget behavior if retained,
* memory injection into new session instructions.

Prefer focused feature tests over trying to make all inherited upstream template tests pass if those tests genuinely do not apply to this generated locked-profile app.

However, investigate the 65 upstream failures enough to establish whether they are unrelated.

Report representative failing test names/categories.

Do not spend substantial time "fixing" unrelated template tests.

---

## 8. Git baseline

Once the current state has been inspected and validated:

1. run:

   ```
   git status
   ```

2. inspect `.gitignore`

3. confirm there are no secrets, credentials, `.env`, caches, virtual environments, or inappropriate generated artifacts staged

4. show me the intended initial commit contents

5. create an initial commit only if the repository looks clean

Suggested commit message:

```
Initial Reachy Duck app with persistent memory and notes
```

Do not push anywhere unless explicitly asked.

---

# Architecture constraints

Keep the project deliberately simple.

DO NOT introduce:

* LangGraph
* vector databases
* embeddings
* RAG frameworks
* memory frameworks
* Redis
* SQL databases
* autonomous agent loops
* shell execution tools
* code-writing tools

Not yet.

For now, plain Python + Markdown is preferred.

Keep these concerns separated:

* storage
* LLM/tool interfaces
* conversation/profile behavior
* Reachy hardware/audio integration

The persistence layer should be independently testable.

---

# Next milestone after v0 is verified

Once memory and notes are confirmed working, the next major feature should be **read-only coding repository awareness**.

Do NOT implement it yet unless explicitly asked.

The likely future tools are:

```
get_git_status()
get_git_diff()
list_files(path)
read_file(path)
```

The purpose will be to let Reachy understand what I am currently working on without giving it autonomous write/execute capabilities.

Example future interaction:

```
Me:
"I changed something and now this test fails."

Reachy:
"I see three modified files. Want to walk through the diff?"
```

That is the direction of the project.

---

# Later milestones

Do not implement these yet, but preserve an architecture that can support them:

## Shared notes

I want `NOTES.md` accessible from laptop and phone.

Possible future mechanisms:

* simple local web UI
* Syncthing
* another lightweight sync mechanism

Do not couple storage to the sync mechanism.

## Reachy physical behavior

Eventually Reachy should:

* orient toward me while listening,
* nod/react during rubber-duck reasoning,
* use subtle movement for thinking/listening/speaking states,
* remain useful even when motion is unavailable.

## Real Reachy Mini Wireless deployment

Development is currently on a laptop.

Later the application will run with a real Reachy Mini Wireless.

Avoid hardcoding laptop-specific paths or assumptions.

---

# What I want you to do now

Work through the repository autonomously.

First:

1. inspect the current code,
2. explain the architecture,
3. verify the implemented v0,
4. fix only genuine issues you find,
5. run the focused tests and static checks,
6. investigate the upstream failures enough to classify them,
7. make the repository ready for a clean initial Git commit.

Do not add new product features yet.

At the end, give me:

* what you found,
* what you changed,
* exact tests/checks run,
* results,
* whether memory and notes work end-to-end,
* whether the upstream failures are related,
* whether the repository is ready for the initial commit,
* any remaining risks or TODOs.
