# Build brief for the coding agent

You are building **Clipper**, a free, open-source, local-only tool that turns long videos and live streams into ranked short clips. Read `docs/SPEC.md` first, then `AGENTS.md`. Build the whole project in this folder, run it, and open it in the browser on localhost. Work in the stages below. Do not skip a stage, and do not move on until the stage's check passes.

## Hard rules
- Everything runs locally. No hosted services, no paid APIs required. Users bring their own optional keys via `.env`.
- Default must work with **no keys at all** (local speech-to-text with faster-whisper, clip picking by loudness plus transcript heuristics). A Gemini key (free tier) upgrades the ranking, captions and hashtags. Ollama is the offline LLM option.
- Backend: Python 3.10+, FastAPI, uvicorn. Frontend: one plain HTML/CSS/JS app served by FastAPI. No Node, no build step.
- Bind the server to `127.0.0.1:8000` only. Never expose `data/`.
- One start command: `python run.py`. It must create a venv if missing, install requirements, check that ffmpeg exists (print a clear install hint if not), start the server, print `Open http://127.0.0.1:8000`, and open the browser.
- Auto-scheduling to YouTube is **off by default**. The UI and README must say: get the creator's permission or use their clipping program, and note YouTube's upload quota (about 6 uploads per day on the default quota) and that unaudited API projects upload as private.
- Write a test for every stage (pytest). Put a tiny generated test video (ffmpeg testsrc) in the tests, never copyrighted media.

## Stage 1: core pipeline (CLI + API)
1. Download any URL supported by yt-dlp (YouTube, Kick, Twitch, TikTok, X, Rumble, Vimeo, Facebook) or a local file.
2. Transcribe locally with faster-whisper, word-level timestamps.
3. Find candidate moments: loudness peaks, transcript hook phrases, optional chat spikes.
4. Cut clips of 20 to 60 seconds with ffmpeg.
Check: run on a short public video or generated test file and get at least 3 mp4 clips in `data/out/session_N/`.

## Stage 2: ranking
Score every clip 0 to 100 with a weighted sum: hook 30%, chat craze 25%, emotion 20%, story 15%, trend 10%. Without chat data, redistribute the chat weight. Output a ranked list (#1 to #N) with the per-clip score breakdown and a one-line reason. Files are named `01_*.mp4`, `02_*.mp4`.
Check: unit tests for the math; API `GET /api/sessions/{id}/clips` returns ranked clips.

## Stage 3: render and edit
Render options per clip: aspect ratio 9:16, 1:1, 4:5, 16:9; framing "crop to face" (face tracking with a lightweight detector) or "blur fit"; word-by-word burned captions with 3 styles; a hook text overlay; trim start and end; editable caption text; captions on/off.
Check: render one clip in all four ratios and both framing modes without errors.

## Stage 4: AI text and thumbnail
Per clip: title, caption, hashtags (Gemini or Ollama; with no key, simple template from the transcript). Thumbnail: best frame plus title text; AI image thumbnail only if an image-capable key is set.

## Stage 5: web UI
Build the UI described in `docs/SPEC.md` (Clips screen with ranked list and editor, Streamers screen, Settings screen to paste keys into `.env` through the UI). Clean, light look, orange-red accent `#C93A18`, ground `#F6F5F1`, Inter font via system fallback. Real buttons, labels on every input, keyboard accessible.
Check: open it in the browser, paste a link, make clips, edit clip #1, download it. Take screenshots as proof.

## Stage 6: pinned streamers and live watcher
Pin channels (Kick, Twitch, YouTube). A background watcher polls for live status. When live: record into a rolling ~15 minute buffer (ffmpeg stream copy), detect chat-rate spikes (YouTube and Twitch via chat-downloader; Kick via its chat websocket, best effort; fall back to audio loudness spikes), cut a clip shortly after each spike. When the stream ends: rank all clips, keep the best N, and optionally schedule them.
Check: a simulated stream (a local looping file served as a fake live source plus a fake chat generator) produces spike clips. Say clearly in the README which live parts are untested against real platforms.

## Stage 7: YouTube scheduling (opt-in)
OAuth desktop flow, `python run.py youtube-login`, upload with scheduled publish time, daily cap setting, dry-run mode that only prints what it would upload.

## Stage 8: ship it
Write `README.md` (what it is, 60-second quick start, no-key mode, keys, limits, responsible use), `.env.example`, `requirements.txt`, `LICENSE` (MIT), a `Dockerfile`, and `CLAUDE.md`/`AGENTS.md` kept in sync. Finish with the exact command to run and the local URL.

## When you finish
Run `python run.py`, open `http://127.0.0.1:8000` in the browser, process one test video end to end, and report: what works, what you could not test, and what the user must do (keys, ffmpeg, OAuth).
