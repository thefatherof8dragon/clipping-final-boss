# PeakCut Live-Stream Clipping Design & Architecture Notes

Study of **PeakCut** (https://github.com/haziqahmedqasmi/PeakCut, MIT License) for live-stream clipping design, comparing PeakCut's approach with Clipping Final Boss and defining the adoption plan.

---

## 1. Live Detection
* **PeakCut Implementation**:
  * Files: `studio/profiles.py` (`_twitch_live`, `_fetch`, `_twitch_profile`), `studio/live.py` (`resolve`), `studio/creators.py`.
  * Polls live state on an interval (`LIVE_EVERY = 120`s; shared cache for multiple watchers `LIVE_SHARED_FOR = 75`s).
  * **Twitch**: Queries Twitch's internal GraphQL endpoint (`https://gql.twitch.tv/gql`) using public client ID `kimne78kx3ncx6brgo4mv6wki5h1ko` to retrieve live status, stream title, viewers count, and start time in ~1 second without spawning heavy processes.
  * **Kick**: Reads public API endpoint `https://kick.com/api/v2/channels/{slug}` for user metadata and follower/live status.
  * **YouTube**: Uses `yt-dlp.YoutubeDL` with `extract_info(url, download=False)` checking `info.get("is_live")`, falling back to scraping `og:title` and `og:image` from channel `/live` URL.
* **Our State**: We currently fetch platform data and metadata (`og:title`, `og:image`, public Kick API).
* **Adoption**: Adopt Twitch's lightweight GQL probe and Kick channel/livestream API for sub-second status checks; cache shared lookups for 60-90s to avoid platform rate limits.

---

## 2. Recording: Rolling Buffer Approach
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`Session._ingest_loop`, `_scan_segments`).
  * Spawns an `ffmpeg` child process consuming the live stream stream URL:
    * Video/Audio segments: `-f segment -segment_time 6 -reset_timestamps 1 -segment_format mpegts -segment_list p01.csv -segment_list_type csv p01_%05d.ts`. Each segment is 6 seconds (`SEG_SEC = 6`).
    * Parallel Audio Pipe: Simultaneously maps audio to `pipe:1` as 16kHz 16-bit mono PCM (`-vn -ac 1 -ar 16000 -f s16le pipe:1`). Python reads raw 1-second chunks (`SR * 2` bytes) directly to compute RMS loudness in real time without disk I/O.
  * Buffer Retention: `_scan_segments` reads `p*.csv` and keeps segments within `keep_from = seg_clock - buffer_min * 60` (default 20 min). Older `.ts` files are unlinked from disk.
  * Disk Cap: Enforced by buffer duration truncation.
* **Our State**: Previously relied on full post-broadcast downloads or local files.
* **Adoption**: Adopt the exact 6-second segmenting with CSV index and simultaneous `s16le` audio pipe to stdout. Configure rolling buffer for 10 minutes default with strict disk usage cap (e.g., 2 GB max per live buffer).

---

## 3. Spike Scoring (Loudness, Chat, Transcript)
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`Session._watch_spikes`, `_ai_check`), `studio/brain.py` (`judge_signals`, `judge_transcript`).
  * **Loudness**: Computed every second from PCM audio: `amp = 10 ** (db / 20)`. Compares current 5-second average against rolling 3-minute baseline (excluding last 10s): `loud_jump = cur / max(base, 1e-6) - 1`. Triggers when `loud_jump >= JUMP` (default 0.6, i.e. 60% above baseline).
  * **Chat Rate**: Tracks unique participants (`chat_users`) per second to prevent single-user emote spam from skewing metrics. Compares last 8 seconds against 3-minute baseline: `chat_now >= max(1.5, chat_base * (1 + pct))`.
  * **Transcript / Two-Judge Validation**: When a jump occurs or on schedule, Judge 1 evaluates the speech transcript, while Judge 2 evaluates audio loudness & chat density. Clips are approved when both judges agree (or if one judge has $\ge 90$ confidence).
* **Our State**: Had a static threshold (120 msg/s) and basic audio energy.
* **Adoption**: Replace static thresholds with dynamic rolling baseline ($\mu + k \cdot \sigma$, default 60% jump over 3-minute baseline). Combine loudness, chat velocity, and speech keyword density into a unified real-time score. Support no-key mode using pure loudness + chat heuristics.

---

## 4. Spike to Clip Conversion (Pre-roll and Post-roll)
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`Session.AUTO_BEFORE = 30`, `AUTO_AFTER = 20`, `PAD = 8`, `_render`).
  * When a spike occurs at time $t$, window $[t - 30, t + 20]$ is selected.
  * Buffer segments covering $[t - 30 - 8, t + 20 + 8]$ (`PAD = 8` seconds on each side) are identified from `self.segments`.
  * Uses `ffmpeg -f concat -safe 0 -i list.txt -c copy` to assemble `.src.ts` instantly without re-encoding.
  * Aligns transcript clock with video stream clock using local audio fingerprinting (`_align`).
* **Our State**: Cutter took static start and end times on pre-downloaded files.
* **Adoption**: Adopt segment concatenation from the rolling buffer with default 20s pre-roll (before spike peak) and 10s post-roll (after spike peak), with $\pm 4$s padding for non-destructive re-trimming in the Clip Studio Editor.

---

## 5. End of Stream Lifecycle
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`Session._analyze`, `cleanup`).
  * When stream ends (`ffmpeg` EOF or 3 consecutive failed reconnects):
    1. Sets `self.ended = True`.
    2. Flushes any remaining audio in `pending` buffer through the transcriber.
    3. Runs final AI / heuristic evaluation over the tail of the stream.
    4. Waits for all active rendering worker jobs to finish writing clips.
    5. Calls `cleanup()`: unlinks all buffer segments (`.ts`, `.csv`), frees disk space, marks session `status="done"`.
* **Our State**: Simple stream watcher with manual clipping.
* **Adoption**: Implement automatic end-of-stream detection: drain pending audio, cut tail clips, pass all harvested clips through the virality ranking pipeline, save them into the Clips tab grid, wipe temporary buffer `.ts` files, and leave the auto-schedule toggle safely OFF.

---

## 6. Chat Connections per Platform & Fallbacks
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`Session._chat`).
  * **Twitch**: Connects directly via TLS socket to `irc.chat.twitch.tv:6697` anonymously using `NICK justinfan<random>` and `JOIN #channel`. Robust, lightweight, zero credentials, receives `PRIVMSG` in real time.
  * **Fallback**: If connection fails or platform lacks chat, catches exception, sets `chat_on = False`, and continues running on loudness and transcript without crashing.
* **Our State**: Had basic mock/spike tester and chat-downloader stub.
* **Adoption**:
  * Twitch: Anonymous IRC TLS socket (`justinfan`).
  * Kick: Direct connection or lightweight public websocket reader.
  * YouTube: Lightweight live chat replay/polling feed.
  * **Graceful Fallback**: If chat is unavailable or disconnected, automatically fall back to loudness + transcript and display `"Chat: audio-only fallback"` in the UI. Never silently show 0 msg/s.

---

## 7. Dedupe, Spacing, and Caps
* **PeakCut Implementation**:
  * Files: `studio/live.py` (`AUTO_GAP = 60`, `min_gap_min`, `live_per_hour`).
  * Minimum gap: `AUTO_GAP = 60`s between spike triggers; enforces `min_gap_min` (default 2 min) between clips.
  * Overlap dedupe: Checks `abs(c["start"] - existing["start"]) < min_gap`.
  * Rate cap: `live_per_hour` (default 4 clips/hr) to avoid flooding.
* **Our State**: Handled dedupe for VOD candidate picker, but lacked live cooldown.
* **Adoption**: Implement 60s cooldown between auto-clips, merge spikes within 15s of each other into a single clip, and cap maximum clips per stream (configurable, default 10).

---

## Summary of Adoptions vs Existing Differentiators

| Feature | PeakCut Design | Our Status | Plan for Rebuild |
|---|---|---|---|
| Rolling Buffer Recording | 6s `.ts` segments + CSV | Not in live | **Adopt**: 6s TS segments + audio pipe |
| Real-time Loudness | In-memory `s16le` pipe | Post-hoc ffmpeg | **Adopt**: Direct pipe from ffmpeg |
| Dynamic Spike Baseline | Mean + 60% over 3 min | Fixed 120 msg/s | **Adopt**: Rolling mean + k*std |
| Chat Sources | Twitch IRC | Stubs | **Adopt**: Twitch IRC + fallback UI |
| Pre/Post-roll Clipping | Concatenates buffer | File cuts | **Adopt**: 20s pre / 10s post buffer cut |
| Ranked Best-of List | Unranked queue | **Our Strength** | **Retain**: Score chips & ranking |
| Studio Editor | Basic player | **Our Strength** | **Retain**: Subtitle styles & word timing |
| Pinned Auto-Watch | Creator workspace | **Our Strength** | **Retain**: Multi-platform pinned cards |
| Local Whisper / No Key | Sherpa-onnx | Faster-whisper | **Retain & Enhance**: Local whisper no-key |
