Implement and document the complete daily lifecycle for Reachy Duck on Reachy Mini Wireless.

# Goal

I want Reachy Duck to behave like an always-available desk companion.

The intended user experience is:

1. I press the physical power button on Reachy Mini Wireless.
2. Linux boots.
3. The Reachy daemon starts.
4. Reachy remains asleep / inactive.
5. I touch an antenna.
6. Reachy wakes up.
7. Reachy Duck starts automatically as the configured startup app.
8. I use Reachy normally for conversation and programming.
9. When I am done, I say:

   * "Reachy, go to sleep."
   * "Good night."
   * "You can sleep now."
   * "Stop for now."
10. Reachy performs its normal sleep behavior and Reachy Duck stops cleanly.
11. Linux and the Reachy daemon remain running.
12. Later, touching an antenna wakes Reachy again and automatically starts Reachy Duck.
13. When I really want to turn the device off, I use the normal physical/system shutdown mechanism separately.

The key UX is therefore:

```
power on
    -> daemon running, Reachy asleep
    -> touch antenna
    -> wake
    -> Reachy Duck starts
    -> use normally
    -> say "good night"
    -> Reachy Duck stops / Reachy sleeps
    -> touch antenna later
    -> Reachy Duck starts again
```

Do NOT confuse this feature with shutting down Linux.

# Part 1 — Voice-controlled sleep

Inspect whether the current generated Reachy conversation app already contains or inherits the official `go_to_sleep` tool.

Prefer the existing official implementation.

Requirements:

* Explicit requests such as:
  "Reachy, go to sleep."
  "Good night."
  "You can sleep now."
  "Stop for now."
  should map to `go_to_sleep`.

* Do NOT trigger sleep merely because the user mentions the word "sleep".

* The intent must clearly be to stop/rest the current Reachy session.

* Keep the spoken acknowledgement short and natural.

* Preserve persistent memory and notes.

* Do not manually kill processes if the official app lifecycle/tool already provides the correct stop mechanism.

* Add focused tests for this profile/tool behavior where practical.

# Part 2 — Antenna wake

Investigate the official Reachy Mini Wireless implementation for antenna-triggered wake.

I want to use the official daemon/platform mechanism, not a custom polling loop inside Reachy Duck.

Determine:

1. how antenna touch/wake is detected,
2. whether one or both antennas can trigger wake,
3. the exact gesture expected:

   * touch,
   * movement,
   * press/hold,
   * duration/debounce if relevant,
4. what state the robot must be in,
5. what happens if Reachy is already awake,
6. what happens if an app is already running,
7. whether this behavior is specific to Reachy Mini Wireless.

Do not implement custom antenna monitoring unless the official daemon mechanism is insufficient.

# Part 3 — Configure Reachy Duck as startup app

Determine the current official way to configure:

```
reachy_duck
```

as the startup app on Reachy Mini Wireless.

The desired daemon behavior is conceptually:

```
daemon starts
Reachy remains asleep
antenna interaction
Reachy wakes
startup app reachy_duck launches
```

Use the official configuration/API/service mechanism supported by the installed Reachy version.

Do NOT blindly hardcode command-line daemon arguments if startup configuration is managed elsewhere on the Wireless installation.

Inspect the actual installed/system configuration and document exactly what is being changed.

Requirements:

* Reachy Duck startup configuration should persist across robot reboots.
* It must be easy to disable or replace the startup app later.
* Do not modify more of the system daemon configuration than necessary.
* Preserve normal Reachy Mini Wireless functionality.

# Part 4 — Lifecycle correctness

Clearly distinguish these states:

## Fully powered off

```
Linux: OFF
Reachy daemon: OFF
Reachy Duck: OFF
```

## Powered on but sleeping

```
Linux: ON
Reachy daemon: ON
Reachy Duck: OFF
Reachy: sleeping/inactive
```

## Active

```
Linux: ON
Reachy daemon: ON
Reachy Duck: ON
Reachy: awake/listening
```

The feature should transition:

```
powered on but sleeping
    --antenna-->
active
    --"good night"-->
powered on but sleeping
```

It should NOT shut down Linux.

# Part 5 — Reboot behavior

Verify the intended sequence after a full reboot:

```
physical power button
    -> Linux boots
    -> Reachy daemon starts
    -> Reachy does NOT immediately start talking
    -> Reachy waits asleep
    -> antenna touch
    -> Reachy wakes
    -> Reachy Duck starts
```

If the currently installed Reachy daemon does not support exactly this behavior, explain the closest officially supported behavior rather than inventing a workaround.

# Part 6 — Persistence

Verify that:

```
MEMORY.md
NOTES.md
```

remain untouched across:

* Reachy Duck stop/start,
* antenna wake cycles,
* app restart,
* daemon restart,
* normal robot reboot.

The current persistent data location should remain outside replaceable application installation files.

Do not change the storage architecture unless there is a genuine problem.

# Part 7 — First physical verification

Provide an exact physical test procedure.

It should look approximately like:

1. Configure `reachy_duck` as startup app.
2. Reboot Reachy Mini Wireless.
3. Confirm that Linux/daemon are up but Reachy Duck is not actively conversing.
4. Touch the correct antenna.
5. Confirm Reachy wakes.
6. Confirm Reachy Duck starts automatically.
7. Say:
   "Hello Reachy."
8. Confirm voice interaction works.
9. Say:
   "Remember that my test word is pineapple."
10. Say:
    "Good night."
11. Confirm Reachy sleeps and Reachy Duck stops.
12. Touch the antenna again.
13. Confirm Duck starts again.
14. Ask:
    "What is my test word?"
15. Confirm it answers:
    "pineapple."
16. Perform a full reboot.
17. Touch the antenna.
18. Verify the memory still exists.

Include exact commands to inspect:

* current app,
* daemon state,
* logs,
* startup-app configuration,
* persistent files.

# Part 8 — README

Update README.md with a concise section:

```
Daily use: wake and sleep
```

It should explain the normal workflow for me as the user:

```
Power Reachy on once.
Touch an antenna when I want to use Reachy Duck.
Talk normally.
Say "Good night" when I am done.
Reachy sleeps but remains powered on.
Touch an antenna later to resume.
Use the normal device shutdown mechanism only when I want to power Reachy off completely.
```

Also document:

* how to configure Reachy Duck as startup app,
* how to disable that configuration,
* how to inspect the current startup app,
* how to manually start/stop Reachy Duck for debugging.

# Constraints

Do NOT add:

* repo-awareness,
* Google Calendar,
* note synchronization,
* custom antenna polling,
* new databases,
* LangGraph,
* embeddings,
* autonomous background agents.

This milestone is ONLY about the clean wake/use/sleep lifecycle.

Prefer official Reachy Mini mechanisms.

# Before changing anything

First inspect the current project and the installed/current Reachy Mini mechanisms.

Explain:

1. whether `go_to_sleep` already exists,
2. exactly how it stops the current app,
3. how antenna wake works officially,
4. how startup apps are configured officially,
5. whether the expected lifecycle above is fully supported,
6. exactly what project files and robot/system configuration you intend to modify.

Then implement only the necessary changes.

# At the end

Report:

* what Reachy already provided,
* what you changed in Reachy Duck,
* what configuration changed on the robot,
* exact commands used,
* tests run,
* exact physical test procedure,
* any limitations or differences between the desired lifecycle and what the current Reachy Mini Wireless firmware/daemon actually supports.
