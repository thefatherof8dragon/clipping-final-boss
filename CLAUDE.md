# Agent instructions

Project: Clipping Final Boss (`clipping-final-boss`), a local open-source clipping tool. Spec: `docs/SPEC.md`. Build plan: `ANTIGRAVITY_PROMPT.md`. Redesign: `UI_REDESIGN_PROMPT.md`.

## Setup and run
- Needs Python 3.10+ and ffmpeg.
- Start: `python run.py` (creates a venv, installs requirements, starts the server).
- URL: http://127.0.0.1:8000
- Tests: `pytest`

## Rules
- Local only. Bind to 127.0.0.1. Never commit `.env` or `data/`.
- Must work with no API keys (local whisper + loudness picking).
- YouTube auto-scheduling is off by default; keep the permission and quota notes.
- Ask before installing system software (ffmpeg) or running destructive commands.
- After any change, run the tests and say what you could not test.
