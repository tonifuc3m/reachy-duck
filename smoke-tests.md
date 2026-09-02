# Reachy Duck Smoke Tests

Run these checks with Reachy Duck installed as the managed Wireless app and the daemon logs visible. Each answer must
come from the live `get_robot_status` tool, not from model memory.

## Robot status

Ask Reachy:

1. `Are you working correctly?`
2. `What app is running?`
3. `Are you awake?`
4. `What's your speaker volume?`
5. `What's your microphone volume?`
6. `What IP address do you have?`
7. `What Reachy version are you running?`
8. `How much battery do you have?`

Expected results:

- The daemon/backend readiness, motor state, managed app holder, volumes, IP, and version reflect the daemon's current
  response.
- “Working correctly” means only that the daemon is reachable, the backend is ready, and neither reports an error. It
  must not claim microphone, speaker, camera, motor movement, or Internet end-to-end health.
- `enabled` and `gravity_compensation` motor modes are awake; `disabled` is not awake. A missing mode is unavailable.
- Battery level and charging are reported as unavailable unless a future daemon exposes an official source; Reachy says
  it cannot read the battery level programmatically rather than guessing.
- If one secondary endpoint fails, Reachy reports that field as unavailable while retaining the other live results.

For a direct comparison while testing, replace `ROBOT_HOST` as needed and inspect the daemon responses:

```bash
ROBOT_HOST=reachy-mini.local

curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/daemon/status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/daemon/robot-app-lock-status"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/volume/current"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/volume/microphone/current"
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/state/doa" || true
```
