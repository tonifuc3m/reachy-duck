# Reachy Duck — Robot Status v1

## Goal

Give Reachy Duck reliable read-only awareness of its own current Reachy Mini Wireless status.

The user should be able to ask things such as:

```text
"Are you working correctly?"
"What app is running?"
"Are your motors ready?"
"What's your volume?"
"What's your microphone volume?"
"What IP do you have?"
"What Reachy version are you running?"
"How much battery do you have?"
```

The implementation must use official Reachy Mini daemon APIs where available and must never invent status information.

This milestone is read-only.

---

# 1. Platform assumptions

Reachy Duck runs locally on Reachy Mini Wireless.

The Reachy Mini daemon exposes its REST API on port 8000.

From another computer, the Wireless daemon is normally available at:

```text
http://reachy-mini.local:8000/api
```

From Reachy Duck itself, prefer:

```text
http://127.0.0.1:8000/api
```

or the equivalent localhost address already used by the app.

Do not resolve `reachy-mini.local` from the robot itself unless necessary.

The base URL should be centralized/configurable rather than duplicated across the codebase.

---

# 2. Implementation strategy

Implement one high-level LLM tool:

```python
get_robot_status()
```

Internally, compose the result from several official daemon endpoints.

Do not expose one LLM tool per HTTP endpoint.

Conceptually:

```text
get_robot_status()
        |
        +-- daemon status
        +-- robot app lock
        +-- speaker volume
        +-- microphone volume
        +-- optional DoA/speech status
```

Each query must fail independently.

A failure in one endpoint must not make the entire status request fail if useful information can still be returned.

This mirrors the pattern used by the Reachy Mini Home Assistant integration.

---

# 3. Daemon status

Use the official daemon status endpoint corresponding to:

```text
GET /api/daemon/status
```

The current Reachy Mini daemon status model exposes fields including:

```text
state
wireless_version
backend_status
error
wlan_ip
version
hardware_id
no_media
media_released
```

Use these documented fields only.

The exact response model may evolve between Reachy Mini versions, so parsing should tolerate missing optional fields.

Do not require every field to exist.

---

# 4. Daemon readiness

Expose a concise distinction between:

```text
daemon reachable
backend ready
daemon/backend error
```

Use:

```text
daemon_status.state
daemon_status.backend_status.ready
daemon_status.error
daemon_status.backend_status.error
```

when available in the installed version.

Conceptual normalized fields:

```python
daemon_reachable: bool
daemon_state: str | None
robot_ready: bool | None
daemon_error: str | None
backend_error: str | None
```

Do not collapse all of these into one boolean.

Example:

```json
{
  "daemon_reachable": true,
  "daemon_state": "running",
  "robot_ready": true,
  "daemon_error": null,
  "backend_error": null
}
```

If the daemon cannot be reached:

```json
{
  "daemon_reachable": false,
  "robot_ready": null,
  "problems": [
    "Reachy Mini daemon is not reachable."
  ]
}
```

Do not fabricate the rest of the fields.

---

# 5. Motor / awake state

Use the documented:

```text
backend_status.motor_control_mode
```

when available.

The existing Reachy Home Assistant integration derives `awake` from motor mode using:

```text
enabled
gravity_compensation
```

as awake states.

Follow the installed SDK/daemon semantics rather than inferring wake state from head position or movement.

Normalize to something similar to:

```python
motor_control_mode: str | None
awake: bool | None
```

Do not invent additional motor-health data unless exposed by a documented API.

---

# 6. Active app

Use:

```text
GET /api/daemon/robot-app-lock-status
```

This endpoint is the daemon's source of truth for the managed-app lock.

The documented lock states include:

```text
free
local_app
remote_session
```

and:

```text
holder_name
```

Normalize this into:

```python
app_lock_state: str | None
active_app: str | None
```

Examples:

```json
{
  "app_lock_state": "local_app",
  "active_app": "reachy_duck"
}
```

or:

```json
{
  "app_lock_state": "free",
  "active_app": null
}
```

Important limitation:

The robot app lock only tracks managed local apps and managed remote WebRTC sessions.

SDK clients connecting directly to the daemon can bypass this lock.

Therefore do not describe `active_app` as an absolute list of every possible process controlling the robot.

Use wording such as:

```text
"managed app currently holding the robot"
```

internally/documentationally.

Do not inspect `ps`, PID files, or process names to infer the current app.

---

# 7. Speaker volume

Use the official volume endpoint corresponding to:

```text
GET /api/volume/current
```

Return the value exactly as represented by the current API, then normalize it only if the unit/range is clearly documented or observable from the response model.

Conceptually expose:

```python
speaker_volume: float | int | None
```

Do not modify the volume.

This tool is read-only.

---

# 8. Microphone volume

Use:

```text
GET /api/volume/microphone/current
```

Expose:

```python
microphone_volume: float | int | None
```

Do not infer whether the microphone is "good", "bad", muted, or broken merely from its configured volume.

If the API exposes an explicit mute/state field in the installed version, it may be included.

Otherwise report only the known configured volume.

Do not modify microphone volume.

---

# 9. Optional speech detection

If it is trivial with the installed version, optionally query:

```text
GET /api/state/doa
```

This may expose:

```text
speech_detected
angle
```

For v1, only `speech_detected` is potentially useful.

Expose:

```python
speech_detected: bool | None
```

Do not make this endpoint required for `get_robot_status()`.

Do not include DoA angle unless there is a concrete user-facing need.

---

# 10. IP address

Prefer the documented:

```text
wlan_ip
```

from daemon status.

Expose:

```python
wlan_ip: str | None
```

Do not scan interfaces, execute `ip addr`, or inspect the LAN unless the daemon field is unavailable and there is a compelling reason.

For v1, if `wlan_ip` is missing, return `null`.

Do not infer Internet connectivity from the presence of a WLAN IP.

These are different concepts:

```text
Wi-Fi/LAN address
Internet access
```

Internet access belongs to the web/network subsystem.

---

# 11. Reachy version

Use:

```text
daemon_status.version
```

as the Reachy Mini daemon/software version when available.

Expose:

```python
reachy_version: str | None
```

Also optionally expose:

```python
hardware_id: str | None
wireless_version: bool | None
```

Do not call the OS package manager or GitHub to determine the currently running version.

The running daemon is the source of truth for this tool.

---

# 12. Battery

Battery handling must be conservative.

Do NOT assume that Reachy Mini Wireless exposes battery percentage.

Do NOT add:

```python
battery_percent
battery_minutes_remaining
```

unless the currently installed Reachy Mini daemon/SDK exposes a documented and reliable source.

The current documented daemon status model does not contain a battery field.

Therefore the default v1 result should explicitly represent battery as unavailable.

For example:

```json
{
  "battery": {
    "available": false
  }
}
```

If, during implementation, the installed version has gained a documented battery endpoint or field:

1. verify it against the local OpenAPI/Swagger schema,
2. use that official source,
3. add tests,
4. document the Reachy version in which it is available.

Do not:

* estimate battery from uptime,
* estimate it from Linux power statistics,
* infer it from LEDs,
* parse undocumented sysfs values,
* infer remaining runtime.

If no official source exists, Reachy should answer:

```text
"I can't read my battery level programmatically."
```

rather than guessing.

---

# 13. Charging state

Treat charging state exactly like battery.

Only expose:

```python
charging: bool | None
```

if a documented API provides it.

Otherwise:

```json
{
  "charging": null
}
```

Do not infer it from power connection, uptime, USB state, or unrelated Raspberry Pi information.

---

# 14. Normalized result model

Do not return raw daemon payloads directly to the LLM.

Create a small normalized model consistent with the project's existing typing style.

Conceptually:

```python
RobotStatus(
    daemon_reachable: bool,
    daemon_state: str | None,
    robot_ready: bool | None,
    awake: bool | None,
    motor_control_mode: str | None,

    app_lock_state: str | None,
    active_app: str | None,

    speaker_volume: float | int | None,
    microphone_volume: float | int | None,
    speech_detected: bool | None,

    wlan_ip: str | None,
    reachy_version: str | None,
    hardware_id: str | None,
    wireless_version: bool | None,

    battery_available: bool,
    battery_percent: float | None,
    charging: bool | None,

    problems: list[str],
)
```

This is conceptual, not mandatory field-for-field.

Prefer the simplest representation consistent with the existing project.

---

# 15. Partial failure behavior

This is important.

Query the independent endpoints with:

* short timeouts,
* independent exception handling,
* bounded response sizes where relevant.

For example:

```text
daemon/status succeeds
app-lock succeeds
speaker volume succeeds
microphone volume fails
```

should still produce:

```json
{
  "daemon_reachable": true,
  "robot_ready": true,
  "active_app": "reachy_duck",
  "speaker_volume": 0.6,
  "microphone_volume": null,
  "problems": [
    "Microphone volume status is unavailable."
  ]
}
```

Do not fail the whole tool because a secondary endpoint returned an error.

The only special case is daemon reachability:

if `/api/daemon/status` cannot be reached, most robot-level information should be treated as unavailable.

---

# 16. Timeouts

Because the tool itself runs on the same Reachy Mini Wireless device as the daemon, requests should normally be very fast.

Use short HTTP timeouts.

Do not allow a status query to stall the LLM interaction for many seconds.

Reuse the project's existing HTTP client if one exists.

Do not introduce a large HTTP framework solely for this feature.

---

# 17. No polling

`get_robot_status()` is on-demand.

Do not add:

* background polling,
* periodic health checks,
* watchers,
* daemon subscriptions,
* WebSockets

for v1.

A fresh snapshot is taken only when the tool is invoked.

This keeps the implementation small.

---

# 18. No caching in v1

Do not cache status unless the project already has an appropriate short-lived cache.

Status data should normally be fresh because requests are local and cheap.

Avoid introducing cache invalidation logic for this milestone.

---

# 19. LLM behavior

Update the Reachy Duck profile so it uses `get_robot_status()` for questions about its own current state.

Examples:

```text
"Are you okay?"
"Are your motors ready?"
"What app is running?"
"What's your volume?"
"What's your IP?"
"What version are you running?"
"How much battery do you have?"
```

Do not answer these from model memory.

Use the live tool.

The LLM must distinguish:

```text
known
unavailable
error
```

Example:

```text
User:
"Are you working correctly?"

Tool:
daemon_reachable=true
robot_ready=true
problems=[]

Reachy:
"Yes. The daemon and robot backend are ready."
```

Example:

```text
User:
"What's your battery?"

Tool:
battery_available=false

Reachy:
"I can't read my battery level programmatically."
```

---

# 20. "Are you working correctly?"

Do not try to invent one sophisticated health score.

For v1, interpret "working correctly" pragmatically from:

```text
daemon reachable
backend ready
no reported daemon/backend error
```

Optionally mention partial problems such as unavailable volume.

Do not claim that:

* camera works,
* microphone physically works,
* speaker physically works,
* motors physically move correctly,
* Internet works

unless those capabilities were actually tested.

Configured/reported state is not equivalent to end-to-end hardware verification.

---

# 21. Security

This feature is read-only.

Do not expose tools that:

* restart the daemon,
* stop the daemon,
* change motor mode,
* change volume,
* change microphone gain,
* stop/start apps,
* execute shell commands.

Those can be separate explicit features later if desired.

Do not return secrets, tokens, environment variables, or full internal daemon configuration.

---

# 22. Tests

All unit tests must work without physical Reachy hardware.

Use mocked HTTP responses.

Cover at least:

### Healthy Wireless robot

* daemon reachable
* backend ready
* motor mode available
* Reachy Duck holds app lock
* volumes available
* WLAN IP
* version

### Daemon/backend errors

* daemon reports error
* backend reports error
* backend not ready

### Awake state

* enabled
* gravity compensation
* sleeping/disabled equivalent from installed API
* missing motor mode

Verify against actual enum/string values used by the installed Reachy SDK rather than inventing test constants.

### App lock

* free
* local app / reachy_duck
* another local app
* remote session
* missing holder name

### Partial failures

* speaker endpoint fails
* microphone endpoint fails
* DoA endpoint fails
* app-lock endpoint fails

Other data should remain available.

### Complete daemon failure

* localhost connection refused
* timeout
* malformed response

### Optional/missing fields

* no WLAN IP
* no hardware ID
* no version
* no backend status

### Battery

* current API has no battery field
* result reports battery unavailable
* no battery estimate is generated

---

# 23. Physical verification

Before considering the milestone complete, compare Reachy Duck's normalized output with the actual Wireless daemon.

From the laptop:

```bash
ROBOT_HOST=reachy-mini.local
```

### Daemon status

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/daemon/status" | jq .
```

### Managed app lock

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/daemon/robot-app-lock-status" | jq .
```

### Speaker volume

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/volume/current" | jq .
```

### Microphone volume

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/volume/microphone/current" | jq .
```

### Optional speech detection

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/state/doa" | jq .
```

Also inspect the robot's live Swagger/OpenAPI documentation:

```text
http://reachy-mini.local:8000/docs
```

Use this installed API as the final authority if it differs from online documentation.

---

# 24. Physical voice tests

Test at least:

```text
"Are you working correctly?"

"What app is running?"

"Are you awake?"

"What's your speaker volume?"

"What's your microphone volume?"

"What IP address do you have?"

"What Reachy version are you running?"

"How much battery do you have?"
```

Responses should be concise and based only on live status.

---

# 25. Constraints

Do NOT add:

* background monitoring,
* polling loops,
* WebSocket subscriptions,
* health dashboards,
* databases,
* caches unless already present,
* arbitrary shell execution,
* OS process inspection,
* network scanning,
* guessed battery information,
* daemon control actions,
* volume-changing actions.

This milestone is:

```text
read current Reachy state
        +
normalize it
        +
answer naturally
```

Nothing more.

---

# 26. Before implementation

First inspect:

1. the installed Reachy Mini Python version,
2. the local daemon OpenAPI/Swagger schema,
3. the current Reachy Duck HTTP dependencies,
4. whether Reachy Duck already has a daemon/API client,
5. exact enum/string values for daemon and motor-control states,
6. whether the installed version exposes any battery or charging information.

Then report briefly:

* endpoints available,
* fields actually observed,
* files to modify,
* any differences from this specification.

The installed local daemon API is authoritative.

Do not adapt the implementation to assumptions from outdated online examples.

---

# 27. At the end

Report:

* files changed,
* tool signature,
* daemon endpoints used,
* normalized fields exposed,
* actual motor-mode semantics observed,
* whether battery/charging is available on this installed Reachy,
* timeout/error-handling strategy,
* tests run,
* physical verification results,
* any differences between online documentation and the installed daemon.
