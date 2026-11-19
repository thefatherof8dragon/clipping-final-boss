# Run Clipper with Google Antigravity (step by step)

## Before you start
1. Install **Python 3.10+** (python.org). On Windows tick "Add Python to PATH".
2. Install **git** (git-scm.com).
3. Optional: get a free **Gemini API key** at aistudio.google.com. Not needed for the first run.
4. ffmpeg: the agent can install it for you when it asks permission (Windows: `winget install Gyan.FFmpeg`, Mac: `brew install ffmpeg`).

## Steps
1. Download and install Google Antigravity from Google's Antigravity site, then sign in with your Google account.
2. Unzip `clipper-kit.zip` somewhere easy, for example `Documents/clipper`.
3. In Antigravity: **File > Open Folder** and choose that folder.
4. Open the **Agent Manager** and start a new task in this workspace.
5. Paste this prompt:

   > Read ANTIGRAVITY_PROMPT.md, docs/SPEC.md and AGENTS.md. Build the whole project in this folder, following the stages in order and running each stage's check. When it is done, run it on localhost and open it in the browser.

6. Read the **plan** the agent shows and approve it.
7. When it asks to run terminal commands (pip install, ffmpeg, pytest), read them and approve. Keep the terminal policy on "ask first" instead of automatic.
8. If it asks to set up browser control, accept and install the Chrome extension it suggests.
9. When it finishes, it should open **http://127.0.0.1:8000**. If it doesn't, run `python run.py` in the terminal and open that link yourself.
10. Test with a short public video, a few minutes long.

## If something fails
- Copy the red error text from the terminal and send it back to the agent: "Fix this and rerun."
- "ffmpeg not found": approve the install command, then reopen the terminal.
- Page won't load: check the terminal for `Uvicorn running on http://127.0.0.1:8000` and that you're opening it on the same computer.
