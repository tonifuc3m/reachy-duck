# Reachy Duck — Editable notes v1

## Goal

Extend the existing plain-Markdown notes feature so the user can update or delete a previously saved note through
normal voice conversation.

Support requests such as:

```text
"Change my milk note to say that I need oat milk."
"Add that I should also buy coffee to the shopping note."
"Delete the note about calling the garage."
```

Keep the existing distinction between user-facing notes and internal long-term memory. Editing or deleting a note must
never modify `MEMORY.md`, and `forget` must remain the tool for removing internal memory facts.

This milestone extends the current `add_note` and `read_notes` behavior. Do not add a database, synchronization, note
folders, tags, search indexing, version history, or a general file-editing tool.

---

## User-visible operations

The complete v1 note lifecycle is:

```text
add_note(text)
read_notes()
edit_note(note_id, text, mode)
delete_note(note_id)
```

`add_note` and `read_notes` remain available and backward compatible. Add one LLM tool module for `edit_note` and one
for `delete_note`, following the existing adapter boundary under `src/reachy_duck/tools/`.

The user should refer to notes naturally by their content or context. They must not need to know or speak a note ID.
Reachy uses `read_notes` to resolve the user's description to an ID before calling a mutating tool.

---

## Stable note identity

Every note needs a stable, opaque ID because timestamps and note text are not guaranteed to be unique. Generate IDs
locally with the standard library. An ID should be safe to pass unchanged through an LLM tool call and sufficiently
collision-resistant, for example:

```text
note_550e8400e29b41d4a716446655440000
```

Do not derive identity from the note's current text, its position in the file, or a timestamp. Editing a note must
preserve its ID and original creation timestamp.

Keep `NOTES.md` valid, readable plain Markdown. Store machine metadata in a minimal, deterministic representation such
as HTML comments associated with each note:

```markdown
# Notes

## 2026-09-02 17:15:00 UTC
<!-- note-id: note_550e8400e29b41d4a716446655440000 -->

Buy milk tomorrow.
```

After an edit, retain the heading as the creation time and add or update an edit timestamp:

```markdown
# Notes

## 2026-09-02 17:15:00 UTC
<!-- note-id: note_550e8400e29b41d4a716446655440000 -->
<!-- updated-at: 2026-09-03 08:30:00 UTC -->

Buy oat milk and coffee tomorrow.
```

The exact private parser/model is an implementation choice, but storage must not depend on Reachy hardware, the daemon,
or the realtime conversation layer.

---

## Existing-file compatibility

Existing `NOTES.md` files contain timestamp headings and bodies but no IDs. Preserve every existing note and its
creation timestamp.

On the first operation that needs structured entries, assign an ID to each legacy note and rewrite the document in the
new format under the storage lock. The migration must be idempotent: subsequent reads keep the same IDs. A malformed or
unparseable document must produce a clear error and remain byte-for-byte unchanged rather than being partially
rewritten.

Do not silently discard text outside recognized note entries. If preserving it safely is not possible, stop and return
an error.

---

## Reading and note selection

Extend the `read_notes` tool result with structured entries while retaining the existing complete Markdown result for
compatibility. Conceptually:

```json
{
  "notes": "# Notes\n\n...",
  "entries": [
    {
      "id": "note_550e8400e29b41d4a716446655440000",
      "created_at": "2026-09-02T17:15:00Z",
      "updated_at": null,
      "text": "Buy milk tomorrow."
    }
  ]
}
```

The storage layer may expose a typed `Note` representation and a `list_notes(...)` function rather than requiring tool
adapters to parse Markdown themselves. Markdown parsing, migration, serialization, locking, and atomic persistence all
belong in `src/reachy_duck/notes.py`.

Before an edit or deletion, Reachy must call `read_notes` in the current conversation unless it already has a current
successful result that unambiguously identifies the requested note.

Selection rules:

- If exactly one note clearly matches the user's description, use its ID.
- If multiple notes plausibly match, ask one short clarification question and do not mutate anything yet.
- If no note matches, say so; do not guess an ID or claim success.
- Never ask the user to dictate an opaque ID unless needed for developer diagnostics.

Do not implement fuzzy-search infrastructure in v1. The LLM can select among the bounded structured entries returned by
`read_notes`.

---

## Editing

Add a storage operation conceptually equivalent to:

```python
edit_note(
    note_id: str,
    text: str,
    mode: Literal["replace", "append"] = "replace",
    *,
    instance_path: str | Path | None = None,
) -> Note | None
```

and expose it through an `edit_note` LLM tool.

Supported modes:

- `replace`: replace the complete note body with the normalized new text.
- `append`: preserve the existing body and add the normalized new text after it, separated by one blank line.

Use `append` for requests such as "add this to the note" and `replace` for requests such as "change the note to say".
Do not expose arbitrary search-and-replace, patches, regexes, or Markdown file offsets.

Both modes must:

- reject an empty `note_id` or empty `text`;
- affect exactly one note;
- preserve the note ID and `created_at` value;
- set `updated_at` to the current UTC time;
- leave all other notes unchanged and in their existing order;
- persist the complete update atomically before reporting success.

A successful tool result should be concise and structured:

```json
{
  "updated": {
    "id": "note_550e8400e29b41d4a716446655440000",
    "text": "Buy oat milk tomorrow.",
    "mode": "replace",
    "updated_at": "2026-09-03T08:30:00Z"
  }
}
```

If the ID no longer exists, return an expected error such as `{"error": "note not found"}`. Do not recreate the note
or append a new one implicitly.

---

## Deleting

Add a storage operation conceptually equivalent to:

```python
delete_note(
    note_id: str,
    *,
    instance_path: str | Path | None = None,
) -> Note | None
```

and expose it through a `delete_note` LLM tool.

Deletion removes exactly one complete note entry and leaves the document header and all other notes intact and ordered.
Deleting the final note produces the canonical empty document:

```markdown
# Notes

```

Only call `delete_note` when the user has intentionally asked to remove the identified note. An unambiguous command such
as "delete the milk note" does not require a second confirmation. A vague command such as "delete that note" requires
clarification when the referent is not clear from the active conversation.

Bulk deletion and "delete all notes" are out of scope for v1. Do not simulate them through an uncontrolled sequence of
tool calls. A later milestone may add an explicitly confirmed bulk operation.

A successful result should identify what was removed without returning the entire document:

```json
{
  "deleted": {
    "id": "note_550e8400e29b41d4a716446655440000",
    "text": "Call the garage."
  }
}
```

If the ID does not exist, return `{"error": "note not found"}` and do not alter the file.

---

## Persistence and failure safety

Continue using the same instance-aware `NOTES.md` path and the existing in-process storage lock.

Any operation that rewrites notes must use an atomic same-directory replacement so a crash cannot leave a partially
written document. Flush and close the temporary file before replacement. Clean up a leftover temporary file after an
expected failure where practical.

Parsing, validation, migration, edit, deletion, and serialization for one operation must occur while holding the same
lock so concurrent `add_note`, `edit_note`, and `delete_note` calls cannot lose updates.

Expected validation, parse, missing-note, filesystem, and Unicode failures must be logged through the module logger and
returned by tool adapters as `{"error": ...}` rather than escaping into the conversation loop. Never report that a note
was changed or deleted before persistence succeeds.

Do not add a dependency for Markdown parsing or file locking.

---

## Profile behavior

Enable `edit_note` and `delete_note` in the locked profile and explain the boundary among note tools:

```text
add_note     -> create a new user-facing note
read_notes  -> inspect and identify existing notes
edit_note   -> replace or append to one identified note
delete_note -> remove one identified note
remember    -> store internal long-term context
forget      -> remove internal long-term context
```

The profile must instruct Reachy to resolve the note with `read_notes`, clarify ambiguous matches, and never claim a
mutation succeeded unless the corresponding tool returns success.

---

## Documentation

Update `README.md` when implementing this spec to document natural-language examples for adding, reading, extending,
replacing, and deleting notes. Keep the documented Wireless persistence path unchanged.

No new environment variable is required, so `.env.example` should remain unchanged unless implementation reveals a
real configuration need.

---

## Focused tests

Add robot-independent storage and tool tests covering at least:

- new notes receive distinct stable IDs;
- structured reads return IDs, timestamps, and text while preserving the Markdown result;
- a legacy file receives IDs without losing or reordering notes;
- legacy migration is idempotent;
- malformed input fails without changing the original bytes;
- replace mode changes only the selected body;
- append mode preserves the old body and adds one separated block;
- edits preserve ID and creation time and set an update time;
- deletion removes only the selected note;
- deleting the final note leaves the canonical header;
- an unknown ID leaves the file unchanged;
- empty text and invalid modes are rejected;
- concurrent adds and mutations do not lose or interleave entries;
- a simulated write/replace failure leaves the original document intact;
- tool adapters return structured success and expected `{"error": ...}` failures;
- the locked profile enables both new tools.

Use a controlled clock or monkeypatch timestamps where exact values matter. Do not construct `ReachyMini`, start a
daemon, or require physical hardware in these tests.

---

## Acceptance scenarios

### Replace a note

```text
User: "Change my note about buying milk to say I need oat milk."
Reachy: calls read_notes
Reachy: finds exactly one matching entry
Reachy: calls edit_note(id, "I need oat milk.", "replace")
Reachy: confirms briefly after success
```

### Extend a note

```text
User: "Add coffee to my shopping note."
Reachy: calls read_notes
Reachy: finds exactly one shopping note
Reachy: calls edit_note(id, "Also buy coffee.", "append")
Reachy: confirms briefly after success
```

### Ambiguous deletion

```text
User: "Delete my shopping note."
Reachy: calls read_notes and finds two plausible shopping notes
Reachy: asks which of the two the user means
Reachy: does not call delete_note until clarified
```

### Missing note

```text
User: "Delete my note about the garage."
Reachy: calls read_notes and finds no matching note
Reachy: says it cannot find that note
Reachy: does not alter NOTES.md
```
