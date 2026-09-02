## Local timers — v1, minimal implementation

Add:

```python
set_timer(duration_seconds: float, label: str | None = None)
list_timers()
cancel_timer(timer_id: str)
```

### Goal

Support simple local relative timers such as:

```text
"Set a timer for 10 minutes."
"Tell me in 45 seconds to check the oven."
"What timers do I have?"
"Cancel the pasta timer."
```

This is intentionally a minimal implementation.

Do not introduce a scheduler framework, persistent storage, a second audio stack, or a new background-agent architecture.

---

## Semantics

Timers represent relative durations only.

Use local timers for:

```text
"in 10 minutes"
"in 45 seconds"
"in 2 hours"
```

Do NOT use them for absolute/calendar requests such as:

```text
"tomorrow at 8"
"next Monday"
"Friday afternoon"
```

Those belong to Google Calendar.

---

## Internal representation

Keep active timers in memory.

Each timer should contain approximately:

```text
id
label
created_at
duration_seconds
expires_at
status
```

Possible status values:

```text
active
expired
cancelled
```

Use the existing temporal context for timestamps.

No database.

No persistence across app restart.

---

## Scheduling mechanism

First inspect the current application architecture.

If the app already has an asyncio event loop, use a simple `asyncio.Task` with `asyncio.sleep()`.

Otherwise use the smallest existing standard-library mechanism compatible with the app.

Do not add APScheduler, Celery, cron, or any scheduler dependency.

`set_timer()` must return immediately after scheduling.

Do not block an LLM tool call for the duration of the timer.

---

## Timer expiration

When the timer reaches zero:

1. mark it as `expired`,
2. remove/cancel any internal scheduling task as appropriate,
3. attempt a proactive announcement ONLY if the existing conversation architecture already exposes a simple supported way to inject/send an assistant message.

Example announcement:

```text
"Your pasta timer is done."
```

### Important simplicity rule

Do NOT build a new speech/audio/conversation subsystem solely to make timers speak proactively.

If proactive speech is not already straightforward with the existing Reachy conversation architecture, use this fallback:

```text
timer expires
    -> status = expired
    -> store pending announcement in memory
```

Then, on the next normal user interaction, Reachy should announce the expired timer before or together with its response.

Example:

```text
User:
"Reachy, what time is it?"

Reachy:
"Your pasta timer finished while I was waiting. It's 4:30."
```

This fallback is acceptable for v1.

---

## Pending expired timers

Keep a simple in-memory list of expired-but-not-yet-announced timers.

For example conceptually:

```python
pending_expired_timers: list[Timer]
```

When Reachy receives a new user turn:

1. check pending expired timers,
2. expose them to the conversation layer,
3. announce them once,
4. mark/remove them as acknowledged.

Do not persist them across app restart.

---

## Tool behavior

### `set_timer`

Return concise structured data:

```json
{
  "id": "timer_3",
  "label": "pasta",
  "duration_seconds": 600,
  "expires_at": "2026-09-02T17:10:00+02:00"
}
```

### `list_timers`

Return active timers and, if useful, unannounced expired timers.

Include:

```text
id
label
remaining_seconds
expires_at
status
```

### `cancel_timer`

Cancel only active timers.

If a timer does not exist or is already expired, return a clear result rather than raising an uncaught exception.

---

## Labels

Labels are optional.

Examples:

```text
"Set a 10 minute timer."
-> label = null

"Set a 10 minute pasta timer."
-> label = "pasta"
```

Users should normally refer to timers by label.

If multiple active timers share the same label and the requested cancellation is ambiguous, ask for clarification.

Do not over-engineer natural-language timer matching in v1.

---

## Lifecycle

For v1:

```text
conversation turns       -> timer survives
IDLE/ACTIVE transitions  -> timer survives, if same app process
Reachy Duck restart      -> timer lost
daemon restart           -> timer lost
robot reboot             -> timer lost
```

Document this clearly.

When Reachy Duck exits, cleanly cancel active timer tasks.

---

## Tests

Add focused tests for:

* creating a timer
* immediate return from `set_timer`
* listing active timers
* cancelling a timer
* timer expiration
* expired status
* pending expired announcement
* announcement is consumed only once
* multiple timers
* optional labels
* duplicate labels
* cleanup on shutdown

Do not use long real waits in tests.

Use a fake clock or very short controlled timer durations.

---

## Before implementation

Inspect only these two architectural questions:

1. Does the current app already have an asyncio event loop?
2. Is there already a simple supported way to inject an assistant message / make Reachy speak without a new user turn?

If the answer to #2 is yes, reuse it.

If the answer is no, implement the pending-expired-timer fallback.

Do not redesign the conversation architecture.

---

## v1 acceptance criteria

This is enough to call v1 complete:

```text
"Set a timer for 10 seconds."
-> timer is created

10 seconds pass
-> timer becomes expired

If proactive speech is already easy:
    Reachy says "Your timer is done."

Otherwise:
    the next time the user speaks,
    Reachy first mentions that the timer finished.
```

No persistence and no new audio architecture are required for v1.

Implement in a different worktree. There will be other agent working in parallel, so dont interfere with main. 
When finished, test it. And you can inform me so we deploy to reachy and smoke test it

## Before implementation

Inspect only these two architectural questions:

1. Does the current app already have an asyncio event loop?
2. Is there already a simple supported way to inject an assistant message / make Reachy speak without a new user turn?

If the answer to #2 is yes, reuse it.

If the answer is no, implement the pending-expired-timer fallback.

Do not redesign the conversation architecture.

---

## v1 acceptance criteria

This is enough to call v1 complete:

```text
"Set a timer for 10 seconds."
-> timer is created

10 seconds pass
-> timer becomes expired

If proactive speech is already easy:
    Reachy says "Your timer is done."

Otherwise:
    the next time the user speaks,
    Reachy first mentions that the timer finished.
```

No persistence and no new audio architecture are required for v1.
