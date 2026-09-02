Extend the existing Google Calendar integration so Reachy Duck can create richer events and modify them later.

Do not redesign the calendar subsystem. Extend the existing tools and models cleanly.

## 1. Recurring events

Extend event creation with optional recurrence support.

Support common cases such as:

```
every day
every weekday
every week
every Monday
every month
every year
```

Use the official Google Calendar recurrence format (`RRULE`) internally.

Examples:

```
"Every Monday at 9, add team planning."
"Repeat this every weekday."
"Create this appointment every month."
```

Do not make the LLM construct raw RRULE strings unless unavoidable.

Prefer a structured tool schema that can represent recurrence cleanly, then convert it internally to RRULE.

Also support an optional recurrence end condition where practical:

```
until a given date
number of occurrences
```

If the recurrence is ambiguous, Reachy should ask a short clarification.

## 2. Description

Ensure event creation supports:

```
description: str | None
```

Also allow updating the description of an existing event.

Examples:

```
"Add this description to the dentist appointment..."
"Change the description of tomorrow's meeting to..."
```

Preserve existing descriptions unless the user explicitly asks to replace or clear them.

## 3. Guests / attendees

Support:

```
attendees: list[str] | None
```

where values are email addresses.

Examples:

```
"Invite alice@example.com."
"Add Bob and Carol to the meeting."
```

If the user refers to a person by name but no email address is available, do not invent one.

Return a clear clarification request or use an existing contact-resolution mechanism only if one already exists.

When creating/updating attendees, use the official Google Calendar attendees field.

Do not silently send invitations if the API requires an explicit setting; inspect the existing Google API call and use the correct `sendUpdates` behavior.

Prefer a sensible default such as:

```
send_updates = "all"
```

when the user explicitly asks to invite people.

Document this behavior.

## 4. Event color

Support an optional event color.

Do not expose opaque Google color IDs directly to the user if avoidable.

Provide a friendly mapping such as:

```
lavender
sage
grape
flamingo
banana
tangerine
peacock
graphite
blueberry
basil
tomato
```

or use the official currently-supported Google Calendar event color mapping.

Internally resolve the friendly color name to the appropriate Google Calendar color ID.

Examples:

```
"Make it red."
"Put this event in blue."
"Change tomorrow's dentist appointment to green."
```

If a requested color is unsupported, return a concise clarification/error instead of guessing.

## 5. Specific calendar

Support creating and listing events in a specific calendar.

Do not assume everything belongs in `primary`.

The tool should support something equivalent to:

```
calendar_id: str = "primary"
```

But for natural conversation, Reachy should work with human-readable calendar names when possible.

Add a helper/tool as needed to list available calendars, for example:

```
list_calendars()
```

Return at least:

* calendar name
* calendar ID
* primary flag
* access role if useful

Examples:

```
"Put this in my Work calendar."
"Add it to Personal."
"What calendars do I have?"
```

When the user specifies a calendar name:

1. resolve it against the user's available calendars,
2. use the matching calendar ID,
3. ask for clarification if multiple calendars have the same/similar name,
4. do not silently fall back to primary if a requested calendar cannot be found.

## 6. Updating existing events

Add or extend a tool equivalent to:

```
update_calendar_event(...)
```

It should support modifying at least:

* title
* description
* start/end
* reminders
* Google Meet where supported
* attendees
* color
* recurrence
* calendar where technically supported

Important:
Google Calendar may not support moving an event between calendars through a normal update call.

If moving between calendars requires a specific API operation, use the official mechanism rather than faking it.

If some properties cannot be modified safely for recurring events or individual instances, handle those cases explicitly.

## 7. Event identification

For update operations, avoid forcing the user to know an event ID.

The app should be able to locate an event from natural criteria such as:

```
"tomorrow's dentist appointment"
"my 10 AM meeting"
"the planning meeting on Friday"
```

Reuse the existing temporal context and event-listing infrastructure.

If multiple events match, Reachy should ask a concise clarification before modifying anything.

Do not guess which event the user means.

## 8. Tool schemas

Aim for clear structured schemas rather than one giant untyped dictionary.

Potential conceptual tools:

```
create_calendar_event(...)
update_calendar_event(...)
list_calendar_events(...)
list_calendars(...)
```

Do not create separate tools for every single field unless the existing architecture strongly favors that pattern.

## 9. Natural-language examples

Update the locked profile with examples such as:

```
"Every Monday at 9 add team planning."
    -> recurring event

"Put tomorrow's dentist appointment in my Personal calendar."
    -> specific calendar

"Invite alice@example.com and bob@example.com."
    -> attendees

"Make the meeting blue."
    -> event color

"Change the description to 'Discuss Q4 budget'."
    -> update existing event

"Repeat this every month until December."
    -> recurrence with end condition

"What calendars do I have?"
    -> list_calendars()
```

## 10. Safety / ambiguity

Do not modify or create events when materially ambiguous.

Especially clarify:

* which matching event to edit,
* which calendar to use,
* recurrence scope:

  * this event only,
  * this and future events,
  * entire series,
* ambiguous attendee identity,
* ambiguous date/time.

Keep clarification questions short and spoken-friendly.

## 11. Tests

Add focused tests for:

* recurrence generation
* recurrence with UNTIL
* recurrence with COUNT
* description create/update
* attendee creation/update
* invitation update behavior
* color-name-to-color-ID mapping
* invalid color
* explicit calendar ID
* calendar name resolution
* unknown calendar
* duplicate calendar names
* event updates
* ambiguous event matching
* recurring-series update behavior
* event with recurrence + attendees + Meet + reminders + color
* no live Google API calls in unit tests

Use mocks/fakes.

## 12. Constraints

Do not add:

* a database
* background polling
* LangGraph
* a separate scheduling engine
* custom reminder infrastructure

Google Calendar remains the source of truth.

Reuse the existing temporal context for all date/time interpretation.

Before editing:

1. inspect the current calendar implementation,
2. identify the minimum schema/API changes,
3. explain how recurrence, calendars, attendees, colors, and updates map to the Google Calendar API,
4. list the files you intend to change.

Then implement and run focused tests.

At the end report:

* features added
* tool signatures
* files changed
* tests run
* any Google Calendar API limitations discovered
* example voice commands for each new capability.
