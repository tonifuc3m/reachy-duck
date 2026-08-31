# Reachy Duck — First Deployment to Reachy Mini Wireless

This runbook deploys the current `reachy_duck` application from your laptop to a **Reachy Mini Wireless** and verifies voice conversation, persistent memory, and notes.

## Important: credentials

The current official Reachy Mini conversation app defaults to the **Hugging Face deployed realtime backend**.

For the first test:

- **Do not configure `OPENAI_API_KEY`.**
- **Try without `HF_TOKEN` first.**
- `HF_REALTIME_CONNECTION_MODE=deployed` is the normal/default mode.
- Add `HF_TOKEN` only if the robot logs show that Hugging Face authentication is required.
- Never put real credentials in the repository `.env`.

The Python package may contain the OpenAI SDK internally, but that does **not** mean your current default deployment requires your own OpenAI API key.

---

# 1. Go to the project and define the robot

On your laptop:

```bash
cd ~/personal/reachy/reachy-duck/reachy_duck
export ROBOT_HOST=reachy-mini.local
```

Check the variable:

```bash
echo "$ROBOT_HOST"
```

Expected:

```text
reachy-mini.local
```

If `reachy-mini.local` does not resolve on your network, replace it with Reachy's IP address:

```bash
export ROBOT_HOST=192.168.x.x
```

---

# 2. Check network and SSH access

Check that the robot is reachable:

```bash
ping -c 3 "$ROBOT_HOST"
```

Check SSH:

```bash
ssh "pollen@${ROBOT_HOST}" 'echo "SSH OK on $(hostname)"'
```

You should get an `SSH OK` message from the robot.

---

# 3. Check the Reachy daemon and media services

The Wireless robot already runs its own Reachy daemon. Do **not** start `reachy-mini-daemon` on your laptop for this deployment.

Run:

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/daemon/status"
```

Then:

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/media/status"
```

Check speaker volume:

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/volume/current"
```

Check microphone volume:

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/volume/microphone/current"
```

For the real Wireless robot, media should be available and `no_media` should be `false`.

If the daemon itself is unavailable, fix that before deploying the app.

---

# 4. Optional: inspect current app state

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

It is fine if no app is currently running.

---

# 5. Deploy the source code to Reachy

Create a deployment directory on the robot:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "mkdir -p /home/pollen/reachy_duck"
```

Copy the repository:

```bash
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '__pycache__/' \
  --exclude 'build/' \
  --exclude '*.egg-info/' \
  ./ "pollen@${ROBOT_HOST}:/home/pollen/reachy_duck/"
```

Important:

- `.env` is deliberately excluded.
- Your laptop virtual environment is deliberately excluded.
- Persistent user data is **not** stored in `/home/pollen/reachy_duck`, so later `rsync --delete` deployments will not erase Reachy's memories or notes.

---

# 6. Install Reachy Duck into the robot app environment

Run:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -m pip install -e /home/pollen/reachy_duck"
```

Then verify that the app is registered with the Reachy app system:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -c \"from importlib.metadata import entry_points; print([e.name for e in entry_points(group='reachy_mini_apps') if e.name == 'reachy_duck'])\""
```

Expected:

```text
['reachy_duck']
```

If you do not get `['reachy_duck']`, do not continue until installation/registration is fixed.

---

# 7. Configure the realtime backend

## Recommended first attempt: no credentials

The default Hugging Face deployed realtime backend normally works without setting an API key.

Create the app data directory if needed:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "mkdir -p /home/pollen/.local/share/reachy_duck"
```

For the first attempt, you may create a minimal `.env` containing only the explicit deployed mode:

```bash
printf 'HF_REALTIME_CONNECTION_MODE=deployed\n' | \
  ssh "pollen@${ROBOT_HOST}" \
  "umask 077; cat > /home/pollen/.local/share/reachy_duck/.env"
```

This is optional because `deployed` is already the default, but making it explicit is useful for the first deployment.

## If Hugging Face authentication fails

Only if the daemon/app logs show an authentication problem, add your Hugging Face token securely.

On your laptop:

```bash
read -rsp "Hugging Face token: " HF_TOKEN
printf '\n'
```

Then write it directly to the robot:

```bash
printf 'HF_REALTIME_CONNECTION_MODE=deployed\nHF_TOKEN=%s\n' "${HF_TOKEN}" | \
  ssh "pollen@${ROBOT_HOST}" \
  "umask 077; cat > /home/pollen/.local/share/reachy_duck/.env"
```

Immediately remove it from your laptop shell variable:

```bash
unset HF_TOKEN
```

Check permissions:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "ls -l /home/pollen/.local/share/reachy_duck/.env"
```

It should not be world-readable.

## Do I need `OPENAI_API_KEY`?

**No, not for this first deployment with the current default Hugging Face backend.**

Do not add an OpenAI key unless you intentionally change the application to use an OpenAI-hosted backend that explicitly requires `OPENAI_API_KEY`.

---

# 8. Start a log terminal

Open a **second laptop terminal** and run:

```bash
export ROBOT_HOST=reachy-mini.local
```

Or use the robot IP if necessary.

Then:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "sudo journalctl -u reachy-mini-daemon -f"
```

Keep this terminal open.

You will use it to see:

- app startup
- realtime connection
- authentication errors
- microphone/media issues
- tool calls or application exceptions

You eventually want to see successful realtime-session initialization.

---

# 9. Start Reachy Duck

Back in the **first terminal**:

```bash
cd ~/personal/reachy/reachy-duck/reachy_duck
export ROBOT_HOST=reachy-mini.local
```

Stop any currently running Reachy app:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/stop-current-app" || true
```

Start Reachy Duck:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/start-app/reachy_duck"
```

Check its status:

```bash
curl --fail --silent --show-error \
  "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

Watch the log terminal.

You want the application to initialize without exceptions and establish the realtime conversation session.

---

# 10. Optional web UI

While Reachy Duck is running, try:

```text
http://reachy-mini.local:7860/
```

If you are using the IP address:

```text
http://<REACHY-IP>:7860/
```

The voice interaction itself should happen directly through Reachy's microphone and speaker.

---

# 11. Test the speaker and microphone

Say something simple near Reachy:

> Hello Reachy. Can you hear me?

Confirm:

1. Reachy hears you.
2. Speech is transcribed/processed.
3. Reachy answers.
4. The answer comes from Reachy's speaker.

If speaker volume is too low:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/volume/set" \
  -H 'Content-Type: application/json' \
  -d '{"volume":75}'
```

If microphone sensitivity/volume needs adjustment:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/volume/microphone/set" \
  -H 'Content-Type: application/json' \
  -d '{"volume":75}'
```

Then retry the voice interaction.

---

# 12. Test persistent memory

Say to Reachy:

> Remember that my favorite programming language is Python.

Give it a moment to execute the tool.

Inspect persistent memory directly:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "cat /home/pollen/.local/share/reachy_duck/data/MEMORY.md"
```

You should see the stored information.

---

# 13. Verify memory survives a restart

Restart the currently running app:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/restart-current-app"
```

Watch the daemon logs until the realtime session is ready again.

Then ask:

> What is my favorite programming language?

Expected answer:

> Python.

This is the important end-to-end persistence test: the information must survive a new application/conversation session.

---

# 14. Test user-facing notes

Say:

> Write down that tomorrow I need to buy milk.

Then ask:

> What notes do I have?

Reachy should mention the saved note.

Inspect the Markdown file directly:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "cat /home/pollen/.local/share/reachy_duck/data/NOTES.md"
```

You should see a timestamped Markdown note.

---

# 15. Confirm the actual persistence paths

The implementation accounts for `XDG_DATA_HOME`, so ask the installed app itself where it resolves its persistent data directory:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -c \"from reachy_duck.memory import persistent_data_directory; root = persistent_data_directory(); print(root / 'MEMORY.md'); print(root / 'NOTES.md')\""
```

On a normal Reachy Mini Wireless installation, expected paths are approximately:

```text
/home/pollen/.local/share/reachy_duck/data/MEMORY.md
/home/pollen/.local/share/reachy_duck/data/NOTES.md
```

These files should survive application code redeployments.

---

# 16. Test `forget`

If you want to verify the retained `forget` tool, first store something harmless:

> Remember that my temporary test word is banana.

Then ask:

> Forget that my temporary test word is banana.

Inspect:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "cat /home/pollen/.local/share/reachy_duck/data/MEMORY.md"
```

The temporary memory should no longer be present.

---

# 17. Stop the application

When finished:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/stop-current-app"
```

---

# 18. Subsequent deployments after code changes

After editing the app on your laptop with OpenCode, redeployment is much shorter.

From:

```bash
cd ~/personal/reachy/reachy-duck/reachy_duck
export ROBOT_HOST=reachy-mini.local
```

Sync:

```bash
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '__pycache__/' \
  --exclude 'build/' \
  --exclude '*.egg-info/' \
  ./ "pollen@${ROBOT_HOST}:/home/pollen/reachy_duck/"
```

Reinstall if Python packaging/dependencies/entry points changed:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "/venvs/apps_venv/bin/python -m pip install -e /home/pollen/reachy_duck"
```

Restart:

```bash
curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/restart-current-app"
```

Your persistent memory and notes should remain in:

```text
/home/pollen/.local/share/reachy_duck/data/
```

and therefore should not be removed by `rsync --delete`.

---

# 19. Quick deployment checklist

A successful first deployment means all of these work:

- [ ] `reachy-mini.local` or the robot IP is reachable
- [ ] SSH as `pollen` works
- [ ] Reachy daemon status endpoint works
- [ ] Media status reports media enabled
- [ ] `reachy_duck` installs into `/venvs/apps_venv`
- [ ] `reachy_duck` appears in the `reachy_mini_apps` entry-point list
- [ ] App starts from `/api/apps/start-app/reachy_duck`
- [ ] Realtime session initializes
- [ ] Reachy hears you
- [ ] Reachy answers through its speaker
- [ ] `remember()` writes persistent memory
- [ ] Memory survives app restart
- [ ] `add_note()` writes a timestamped note
- [ ] `read_notes()` can retrieve it conversationally
- [ ] Memory and notes live outside the replaceable source/app installation

---

# 20. If the app fails to start

Keep the daemon logs open:

```bash
ssh "pollen@${ROBOT_HOST}" \
  "sudo journalctl -u reachy-mini-daemon -f"
```

The first things to classify are:

1. **Hugging Face authentication error**
   - Add `HF_TOKEN` as described above.

2. **No internet / DNS from Reachy**
   - Verify the Wireless robot itself can reach the internet.

3. **App registration/import error**
   - Re-run the editable install in `/venvs/apps_venv`.
   - Re-run the entry-point check.

4. **Audio/media error**
   - Check `/api/media/status`.
   - Check microphone and speaker volume.
   - Look for media-specific daemon errors.

5. **Reachy Duck Python exception**
   - Capture the traceback from `journalctl`.
   - Fix locally with OpenCode, redeploy, and restart.

Do not add random credentials or change backends until the logs identify the actual failure.
