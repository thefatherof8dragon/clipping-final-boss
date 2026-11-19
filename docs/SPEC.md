# Clipper spec

## Goal
Long video or live stream -> ranked short clips with captions, hashtags and thumbnails -> optional scheduling to the user's own YouTube. Free, local, bring-your-own-keys.

## UI (reference mockup: https://claude.ai/artifact/7SLDW3TkTprGq7jMxgeMUB)
Top bar: logo "Clipper", tabs Clips / Streamers / Settings, note "Local only, keys stay on your machine".

### Clips screen (two columns)
Left (420 px): card "Video or stream link" with URL input, "Top N" number input, button "Make clips". Below, "Ranked clips" list: each row shows rank (#1, #2...), title, duration and source time range, score. Selected row has an accent border.
Right: editor for the selected clip.
- 9:16 preview (250x444) with burned captions.
- Fields: Title, Caption text, Hashtags.
- Aspect ratio buttons: 9:16, 1:1, 4:5, 16:9.
- Framing: Crop to face / Blur fit.
- Trim start and trim end sliders.
- Score panel: "Why it ranked #1" with Hook, Chat craze, Emotion, Story, Trend.
- Buttons: Regenerate captions, AI thumbnail, Download, Schedule to YouTube.

### Streamers screen
Left: input "Channel link or name" + Pin button; list of pinned streamers with source platform and a LIVE / Offline badge.
Right: live panel for the live streamer: elapsed time, spike threshold, a bar graph of chat rate with spike bars highlighted, count and list of clips taken, and a "When the stream ends" panel with an Auto-schedule toggle (default Off) and the note "Needs permission from the creator".

### Settings screen
Fields for GEMINI_API_KEY, OPENAI_API_KEY (optional, thumbnails), OLLAMA_URL, record height, spike threshold, daily upload cap, YouTube login button. Saves to `.env`.

## Scoring
score = 0.30 hook + 0.25 chat + 0.20 emotion + 0.15 story + 0.10 trend (each 0 to 100). No chat data: weights renormalised over the other four.

## API (suggested)
- POST /api/clip {url, top_n}
- GET /api/sessions/{id}/clips
- PATCH /api/clips/{id} {title, caption, hashtags, aspect, framing, trim_start, trim_end, captions_on}
- POST /api/clips/{id}/render, /regenerate, /thumbnail, /schedule
- GET/POST /api/streamers, GET /api/streamers/{id}/status
- GET/PUT /api/settings

## Folders
data/in, data/out/session_N, data/buffer, data/state.json. data/ is git-ignored.
