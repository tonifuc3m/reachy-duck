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

Do not forget to customize:
- this `README.md` file
- the `index.html` file (Hugging Face Spaces landing page)
- the `src/reachy_duck/static/index.html` (the web app parameters page)

The original README from the conversation app is available in `README_OLD.md`.
