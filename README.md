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
`data/MEMORY.md`, while user-facing timestamped notes are stored in `data/NOTES.md`. App launcher instances keep the
same files under their instance-specific `data/` directory. The `remember`, `add_note`, and `read_notes` tools do not
depend on a robot or daemon.

The storage layer can be verified directly from an activated development environment:

```python
from reachy_duck.memory import remember
from reachy_duck.notes import add_note, read_notes

remember("I use pytest for this project")
add_note("Buy milk tomorrow")
print(read_notes())
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
`User transcript` and `Assistant transcript` lines; normal logs still show turn latency and tool calls. The app UI is
also available at `http://reachy-mini.local:7860/` while it runs.

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

Do not forget to customize:
- this `README.md` file
- the `index.html` file (Hugging Face Spaces landing page)
- the `src/reachy_duck/static/index.html` (the web app parameters page)

The original README from the conversation app is available in `README_OLD.md`.
