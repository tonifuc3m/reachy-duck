---
title: Reachy Duck
emoji: 🤖
colorFrom: purple
colorTo: gray
sdk: static
pinned: false
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# Reachy Duck

Forked from the Reachy Mini conversation app.

Customize `profiles/_reachy_duck_locked_profile/profile.md` to change the assistant instructions and enabled tools.
Add custom tools under `src/reachy_duck/tools/` by subclassing `Tool`.

Reachy is configured as a voice-first rubber-duck programming companion. Long-term internal memory is stored in
`data/MEMORY.md`, while user-facing timestamped notes are stored in `data/NOTES.md`. A Wireless daemon-launched app uses
`${XDG_DATA_HOME:-~/.local/share}/reachy_duck/data/`, outside replaceable package files. The `remember`, `forget`,
`add_note`, and `read_notes` storage behavior does not depend on a robot or daemon.

The storage layer can be verified directly from an activated development environment:

```python
from reachy_duck.memory import remember
from reachy_duck.notes import add_note, read_notes

remember("I use pytest for this project")
add_note("Buy milk tomorrow")
print(read_notes())
```

## Daily use: wake and sleep

On Reachy Mini Wireless, normal daily use does **not** shut down Linux. Power Reachy on once; the Wireless daemon
should boot with Reachy asleep. Touch either antenna to wake Reachy and start the configured startup app, then talk
normally. When you are done, say `Good night`, `Reachy, go to sleep`, `You can sleep now`, or `Stop for now`.
Reachy Duck uses the template's official `go_to_sleep` tool: it performs Reachy's sleep movement and requests that the
daemon stop the managed app. Linux, the daemon, `MEMORY.md`, and `NOTES.md` remain running/preserved. Touch an antenna
later to start a new Duck session. Use the normal device/system shutdown mechanism only when you really want to turn
the device off.

The three distinct states are:

| State | Linux | Reachy daemon | Reachy Duck | Reachy |
| --- | --- | --- | --- | --- |
| Fully powered off | off | off | off | off |
| Powered on, sleeping | on | on | off | asleep / motors limp |
| Active | on | on | on | awake and listening |

The intended daily transition is `sleeping --antenna--> active --“Good night”--> sleeping`; it is not a Linux shutdown.

### Configure the Wireless startup app

This requires the current official Wireless daemon API, which exposes `/api/apps/startup-app`. First inspect the exact
robot version and service; do not add daemon command-line flags or edit its unit file:

```bash
ROBOT_HOST=reachy-mini.local

curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/daemon/status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/list-available/installed"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/startup-app"
ssh "pollen@${ROBOT_HOST}" 'systemctl cat reachy-mini-daemon.service; systemctl is-active reachy-mini-daemon.service'
```

After `reachy_duck` appears in the installed-app list, select it persistently:

```bash
curl --fail --silent --show-error -X PUT "http://${ROBOT_HOST}:8000/api/apps/startup-app" \
  -H 'Content-Type: application/json' \
  -d '{"startup_app":"reachy_duck"}'
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/startup-app"
```

The daemon persists only its `startup_app` key in its per-user configuration (normally
`/home/pollen/.config/reachy_mini/daemon_config.json`), so this survives reboots and app updates. To disable it, set
`null`; to replace it, send the installed app's other name instead:

```bash
curl --fail --silent --show-error -X PUT "http://${ROBOT_HOST}:8000/api/apps/startup-app" \
  -H 'Content-Type: application/json' \
  -d '{"startup_app":null}'
```

If the startup-app endpoint returns 404, the installed daemon predates this Wireless feature. Do not invent a polling
loop or edit the systemd daemon arguments: update Reachy Mini through its supported update path first, then repeat the
inspection above. The current official implementation is Wireless-specific: it watches antenna joint displacement
while the managed app slot is free, uses either antenna, and treats a physical push of about 0.25 rad (about 14°) from
the idle position as a touch. It rearms after returning within about 0.10 rad (about 6°), polls at 0.1 s while idle,
and ignores commanded antenna motion. It wakes a sleeping robot first; if it is already awake, it plays the wake cue
and starts the app. If an app or remote managed session already owns the slot, the gesture does nothing and does not
restart or replace that session.

### First physical lifecycle verification

Use two terminals. In the first, observe daemon and app logs:

```bash
ROBOT_HOST=reachy-mini.local
ssh "pollen@${ROBOT_HOST}" 'sudo journalctl -u reachy-mini-daemon.service -f'
```

In the second, configure and inspect the startup app as above, then reboot through the normal device/system procedure.
After the robot returns to the network, verify that the daemon is up but no app is running:

```bash
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/daemon/status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/startup-app"
ssh "pollen@${ROBOT_HOST}" 'cat /home/pollen/.config/reachy_mini/daemon_config.json; ls -l /home/pollen/.local/share/reachy_duck/data/'
```

1. Confirm Reachy is quiet/asleep after the physical power-on and daemon boot.
2. Push either antenna away from its resting position once, then let it return; do not hold it or move both repeatedly.
3. Confirm Reachy wakes, `reachy_duck` becomes `running`, and the logs show its realtime session starting.
4. Say: `Hello Reachy.` Confirm a normal voice response.
5. Say: `Remember that my test word is pineapple.` Confirm the save acknowledgement.
6. Say: `Good night.` Confirm the short acknowledgement (if audible), sleep pose, and that `current-app-status` becomes
   `null`/not running. Linux and `reachy-mini-daemon` must still be active.
7. Touch either antenna again. Confirm Duck starts again, then ask: `What is my test word?` It should answer
   `pineapple`.
8. Perform a full normal reboot. Once the daemon is up and Reachy is asleep, touch an antenna, wait for Duck to start,
   and ask the same question again.

At every stop/start, antenna wake, daemon restart, and normal reboot, confirm the persistent files remain intact:

```bash
ssh "pollen@${ROBOT_HOST}" 'cat /home/pollen/.local/share/reachy_duck/data/MEMORY.md; printf "\\n--- NOTES ---\\n"; cat /home/pollen/.local/share/reachy_duck/data/NOTES.md'
```

If the daemon launcher sets `XDG_DATA_HOME`, resolve rather than guess the paths:

```bash
ssh "pollen@${ROBOT_HOST}" '/venvs/apps_venv/bin/python -c "from reachy_duck.memory import persistent_data_directory; p = persistent_data_directory(); print(p / '\''MEMORY.md'\''); print(p / '\''NOTES.md'\'')"'
```

### Manual app control for debugging

For debugging only, manually start or stop the managed app; this bypasses neither the daemon nor its single-app lock:

```bash
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/start-app/reachy_duck"
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/stop-current-app"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

## First Reachy Mini Wireless Test

### Recommended architecture

Run the installed app directly on Reachy Mini Wireless and control it through the robot daemon. The daemon launches the
`reachy_duck` entry point as a local app process, and the SDK uses its local media backend for the onboard microphone and
speaker. This is the shortest and most reliable end-to-end test.

Running `reachy-duck` on a laptop is also supported. `ReachyMini()` first checks for a local daemon and then falls back
to `reachy-mini.local:8000`; a remote connection uses WebRTC for microphone and speaker media. In that mode, memory and
notes stay in this checkout's `data/` directory on the laptop. Use it for development, not for the first persistence
acceptance test.

### Prerequisites

- Reachy Mini Wireless and the laptop are on the same network.
- Reachy Mini is updated and its system daemon is already running. Do not start a second daemon on the laptop.
- SSH resolves at `pollen@reachy-mini.local`. Substitute the robot's IP address everywhere if mDNS does not resolve.
- The robot has internet access for the built-in Hugging Face realtime service.
- The built-in deployed backend needs no API key by default. `HF_TOKEN` is optional and only needed if allocation or
  private Hugging Face access requires authentication.

### Deploy from this checkout

Run these commands on the laptop from the repository root:

```bash
ROBOT_HOST=reachy-mini.local

curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/daemon/status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/media/status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/volume/current"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/volume/microphone/current"

ssh "pollen@${ROBOT_HOST}" "mkdir -p /home/pollen/reachy_duck"
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '__pycache__/' \
  --exclude 'build/' \
  --exclude '*.egg-info/' \
  ./ "pollen@${ROBOT_HOST}:/home/pollen/reachy_duck/"

ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -m pip install -e /home/pollen/reachy_duck"
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -c \"from importlib.metadata import entry_points; print([e.name for e in entry_points(group='reachy_mini_apps') if e.name == 'reachy_duck'])\""
```

The final command must print `['reachy_duck']`.

If `rsync` is unavailable, copy the checkout with `scp`, then run the same `pip install -e` command. Do not copy a real
`.env` file from the laptop.

### Optional Hugging Face authentication

Skip this for the first attempt. If the app logs show an authentication error, save a token in the app's private
instance configuration on Reachy. Do not commit the token:

```bash
ssh "pollen@${ROBOT_HOST}" "mkdir -p /home/pollen/.local/share/reachy_duck"
read -rsp "Hugging Face token: " HF_TOKEN && printf '\n'
printf 'HF_REALTIME_CONNECTION_MODE=deployed\nHF_TOKEN=%s\n' "${HF_TOKEN}" | \
  ssh "pollen@${ROBOT_HOST}" "umask 077; cat > /home/pollen/.local/share/reachy_duck/.env"
unset HF_TOKEN
```

### Start and observe the conversation

Use two laptop terminals. In terminal one, follow the Wireless daemon and app logs:

```bash
ROBOT_HOST=reachy-mini.local
ssh "pollen@${ROBOT_HOST}" "sudo journalctl -u reachy-mini-daemon -f"
```

In terminal two, stop any existing app, start Reachy Duck, and check its state:

```bash
ROBOT_HOST=reachy-mini.local
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/stop-current-app" || true
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/start-app/reachy_duck"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

Wait for logs containing `Realtime session updated successfully`. Reachy should give a short greeting. Speak near its
microphone and verify that Reachy answers through its speaker. Run with debug logging if you need the journal to include
`User transcript` and `Assistant transcript` lines; normal logs still show turn latency and tool calls. The physical
voice test does not require the generated web page.

If the speaker is too quiet or the microphone gain is too low, set either to a value from 0 to 100 before retrying:

```bash
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/volume/set" \
  -H 'Content-Type: application/json' -d '{"volume":75}'
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/volume/microphone/set" \
  -H 'Content-Type: application/json' -d '{"volume":75}'
```

### Verify memory across an app restart

Say: `Remember that my favorite programming language is Python.` Wait for Reachy to acknowledge it, then inspect the
actual Wireless file:

```bash
ssh "pollen@${ROBOT_HOST}" "cat /home/pollen/.local/share/reachy_duck/data/MEMORY.md"
```

Restart the app, which creates a new realtime session and reloads `MEMORY.md`:

```bash
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/restart-current-app"
```

Wait for `Realtime session updated successfully`, then ask: `What is my favorite programming language?` Reachy should
answer Python from persistent memory.

### Verify user-facing notes

Say: `Write down that tomorrow I need to buy milk.` Then ask: `What notes do I have?` Reachy should read the saved note.
Inspect the timestamped Markdown directly with:

```bash
ssh "pollen@${ROBOT_HOST}" "cat /home/pollen/.local/share/reachy_duck/data/NOTES.md"
```

On a normal Wireless installation running as `pollen`, persistent files are:

```text
/home/pollen/.local/share/reachy_duck/data/MEMORY.md
/home/pollen/.local/share/reachy_duck/data/NOTES.md
```

If the daemon service sets `XDG_DATA_HOME`, the root changes accordingly. Print the same persistent paths selected by
the Wireless launcher instead of guessing:

```bash
ssh "pollen@${ROBOT_HOST}" "/venvs/apps_venv/bin/python -c \"from reachy_duck.memory import persistent_data_directory; root = persistent_data_directory(); print(root / 'MEMORY.md'); print(root / 'NOTES.md')\""
```

## Google Calendar

Reachy can create and read timed events in the authenticated account's primary Google Calendar. This is deliberately
separate from Markdown memory and notes: a request to write ordinary information down remains a note, while a request
with a definite appointment or reminder time becomes a calendar event. The default timezone is `Europe/Madrid`; set
`REACHY_DUCK_TIMEZONE` in the private instance `.env` to another IANA timezone when needed.

### Google Cloud setup

1. Create or select a project in the [Google Cloud console](https://console.cloud.google.com/).
2. Enable **Google Calendar API** for that project.
3. Configure the OAuth consent screen. For a personal Workspace account choose **Internal**; for a personal consumer
   account choose **External** and add your Google account as a test user while the app is in testing.
4. In **Google Auth platform → Clients**, create an OAuth client of type **Desktop app**, then download its JSON file.
   Do not commit this file.

The app requests only `https://www.googleapis.com/auth/calendar.events`, which permits it to create and read events.
Google's [Calendar Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python) documents
the required client libraries and desktop OAuth client; the [installed-app OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app)
documents the loopback callback flow used below.

## Time and timezone

Reachy obtains temporal context from the Wireless system clock, never from model knowledge. Set
`REACHY_DUCK_TIMEZONE` in the private instance `.env` to an IANA name such as `Europe/Madrid`. When it is unset or
invalid, Reachy uses the host's detectable IANA timezone and finally falls back to `Europe/Madrid`. This setting also
controls how Google Calendar timestamps are interpreted; a different robot OS timezone without an explicit app setting
can therefore change date boundaries and relative-date interpretation.

At each new realtime session, Reachy receives a timestamped local context. For a live time question or a relative
calendar operation, it calls its local `get_current_datetime` tool for a fresh reading before reasoning about the date.

### Verify the Wireless clock

These read-only diagnostics should show a synchronized clock and the intended OS timezone:

```bash
ROBOT_HOST=reachy-mini.local
ssh "pollen@${ROBOT_HOST}" 'date; timedatectl; systemctl status systemd-timesyncd --no-pager'
```

After a reboot, run the same command again. If the robot booted without internet, `System clock synchronized: no` can
be temporary; the app still uses its local system clock, but the answer can only be as accurate as that clock. Configure
`REACHY_DUCK_TIMEZONE=Europe/Madrid` explicitly when the desired interpretation differs from the robot OS timezone.

Physical voice checks:

- `What time is it?` — Reachy obtains a fresh local clock reading and replies naturally.
- `What day is it?` — Reachy uses the local date and weekday.
- `What day is tomorrow?` — Reachy resolves tomorrow from fresh timezone-aware time.
- `How long until 6 PM?` — Reachy obtains fresh time, resolves the next applicable 18:00 locally, and calculates the interval.

### First-time OAuth on Reachy Mini Wireless

Run these commands from the laptop. They store both the downloaded OAuth client configuration and the refreshable
token only on the robot, under `/home/pollen/.local/share/reachy_duck/google/`, with owner-only permissions. Replace
the local path with the downloaded file's actual name.

```bash
ROBOT_HOST=reachy-mini.local
GOOGLE_CLIENT_JSON="$HOME/Downloads/client_secret_desktop.json"

ssh "pollen@${ROBOT_HOST}" "install -d -m 700 /home/pollen/.local/share/reachy_duck/google"
scp "${GOOGLE_CLIENT_JSON}" "pollen@${ROBOT_HOST}:/home/pollen/.local/share/reachy_duck/google/client_secret.json"
ssh "pollen@${ROBOT_HOST}" "chmod 600 /home/pollen/.local/share/reachy_duck/google/client_secret.json"

ssh -L 8080:127.0.0.1:8080 "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/reachy-duck google-auth --port 8080"
```

The last command prints a Google authorization URL. Open it in the laptop browser, select the intended account, and
accept the Calendar permission. Keep the SSH command running until it reports that the token was stored. The browser's
`127.0.0.1:8080` callback travels through the SSH tunnel to the authorization process on the robot. Future app starts
reuse and silently refresh `token.json`; re-run this command only after revoking access, changing OAuth clients/scopes,
or an authorization failure.

After a source deployment, install the new dependencies before authorizing:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -m pip install -e /home/pollen/reachy_duck"
```

Example voice checks:

- `Remind me tomorrow at 19:00 to buy milk.`
- `I have the dentist Friday at 18:00.`
- `What do I have tomorrow?`
- `Write down that I need milk.`
- `Remember that I use pytest.`

For a materially ambiguous request, Reachy should ask one short clarification before creating an event. It should not
create an event for ordinary notes.

Stop the app when the test is complete:

```bash
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/stop-current-app"
```

### Troubleshooting

- `reachy-mini.local` does not resolve: use the Wireless IP shown in Reachy Mini Control.
- Daemon request fails: run `ssh pollen@reachy-mini.local 'reachyminios_check'`, then inspect the daemon journal.
- Media status reports `no_media: true` or `available: false`: restart the robot daemon and rerun the media check.
- App does not appear installed: rerun the editable install and confirm the `reachy_duck` entry point command above.
- No greeting or backend retries: verify robot internet access and inspect logs for allocator, token, or websocket errors.
- Memory is not used immediately after `remember`: restart the app; memory is intentionally loaded when a new realtime
  session starts rather than rebuilding the prompt after every tool call.

`README_OLD.md` is an archived copy of the upstream conversation-template documentation. It is retained for reference;
commands and storage details there may not apply to this locked Reachy Duck app.
