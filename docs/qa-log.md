# QA Log: Clipping Final Boss (`clipping-final-boss`)

This file records exact command outputs, ffprobe results, and evidence for every verification run.

## Stage A run 1 (2026-11-20)

### Step 1: YouTube 429 Diagnostic Ladder
- **Target URL**: `https://youtu.be/CsWOUBuokjo`
- **1a. Installed Versions**:
  - Python: 3.14.4 (tags/v3.14.4:23116f9, Apr 7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]
  - yt-dlp: 2026.10.26
  - FFmpeg: version 9.0.2-full_build-www.gyan.dev
  - Node.js: v24.15.0
  - Deno: Not installed
- **1b. yt-dlp Update**:
  - `pip install -U yt-dlp` -> Verified requirement already satisfied at `2026.10.26` (latest release).
- **1c. JS Runtime Verification**:
  - Command: `.\.venv\Scripts\yt-dlp.exe --js-runtimes node -v`
  - Output: `[debug] JS runtimes: node-24.15.0`
  - Confirmed: yt-dlp successfully discovers and binds Node.js v24.15.0.
- **1d. Bare Test on Target URL**:
  - Command: `yt-dlp -v --skip-download --print title https://youtu.be/CsWOUBuokjo`
  - Output: `[debug] [youtube] CsWOUBuokjo: visionos player response playability status: ERROR`
  - Error: `ERROR: [youtube] CsWOUBuokjo: This video is unavailable`
- **1e. Diagnostic Ladder Iterations**:
  1. Sleep arguments (`--sleep-requests 1 --sleep-interval 3 --max-sleep-interval 8`):
     - Result: `ERROR: [youtube] CsWOUBuokjo: This video is unavailable`
  2. Second public video (`https://www.youtube.com/watch?v=jNQXAC9IVRw` - Me at the zoo):
     - Result: **SUCCESS** (Exit code 0). Extracted title: `Me at the zoo` (Duration: 19s). Solved JS challenges with Node.js (`[youtube] [jsc:node] Solving JS challenges using node`).
     - Finding: The local IP is NOT blocked by YouTube.
  3. Extractor client variations on target (`player_client=web,android`, `ios`, `tv`):
     - Result: All player clients return `playability status: ERROR` -> `ERROR: [youtube] CsWOUBuokjo: This video is unavailable`.
  4. Raw HTML inspection of target:
     - URL: `https://www.youtube.com/watch?v=CsWOUBuokjo`
     - Response: HTTP 200, Title: ` - YouTube`, Playability: `{"status":"ERROR","reason":"This video is unavailable","errorScreen":{"playerInterstitialRenderer":{"content":{"interstitialViewModel":{"title":{"content":"Video unavailable"}}}}}`.
     - Confirmed Root Cause: Target video `CsWOUBuokjo` has been deleted or marked private by its uploader on YouTube.
  5. Browser cookies extraction:
     - Chrome & Edge cookie databases were locked by active browser instances (`PermissionError: [Errno 13] Permission denied`).
- **1f. Permanent Defaults Added in Downloader**:
  - File: `clipper/downloader.py` and `clipper/config.py`
  - Integrated automatic Node JS challenge runtime detection (`js_runtimes = {'node': {}}`).
  - Added configurable settings: `YTDLP_COOKIE_BROWSER`, `YTDLP_SLEEP_INTERVAL`, `YTDLP_PLAYER_CLIENT`, `YTDLP_JS_RUNTIME`.
  - Added real yt-dlp error text logging and plain-language rate-limiting / unavailable hints.

### Step 2: /healthz and Startup Health Checks
- **Endpoint**: `GET /healthz` and `GET /api/health`
- **Specification Met**:
  - `status`: 'ok' / 'degraded' / 'failing'
  - `app_version`: "1.0.0"
  - `python_version`: "3.14.4"
  - `ffmpeg`: Found (version 9.0.2-full_build-www.gyan.dev)
  - `ffprobe`: Found (version 9.0.2-full_build-www.gyan.dev)
  - `yt_dlp_version`: "2026.10.26"
  - `js_runtime`: Node.js (v24.15.0)
  - `data_folder`: Writable (real file write and readback test), free space > 150 GB
  - `project_path`: Path length 47 chars (safe, < 100)
  - `time`: ISO 8601 UTC
  - HTTP 200 on all required pass; HTTP 503 with `failing` list otherwise
- **Startup Diagnostics**:
  - Implemented startup logging at server launch in `clipper/api.py`, reporting dependencies, versions, and paths at INFO or WARNING.
- **Real Curl Command & Output**:
```bash
curl -i http://127.0.0.1:8000/healthz
```
```http
HTTP/1.1 200 OK
date: Fri, 20 Nov 2026 03:46:31 GMT
server: uvicorn
content-length: 991
content-type: application/json

{"status":"ok","healthy":true,"app_version":"1.0.0","python_version":"3.14.4","ffmpeg":{"found":true,"version":"9.0.2-full_build-www.gyan.dev","path":"C:\\Users\\Durvankur\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-9.0.2-full_build\\bin\\ffmpeg.EXE"},"ffprobe":{"found":true,"version":"9.0.2-full_build-www.gyan.dev","path":"C:\\Users\\Durvankur\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-9.0.2-full_build\\bin\\ffprobe.EXE"},"yt_dlp_version":"2026.10.26","js_runtime":{"found":true,"runtime":"node","version":"v24.15.0","path":"C:\\Program Files\\nodejs\\node.EXE"},"data_folder":{"path":"Z:\\Clipping open source\\clipper-kit\\clipper-kit\\data","writable":true,"free_space_gb":156.42,"total_space_gb":270.39},"project_path":{"path":"Z:\\Clipping open source\\clipper-kit\\clipper-kit","length":47,"warning":""},"time":"2026-11-20T03:46:34.273158+00:00","failing":[]}
```
- **Test File**: `tests/test_healthz.py` (2 passed in 6.99s)

### Step 3: tests/run.py Single Entry Point
- **Script**: `tests/run.py`
- **Execution Command**: `.\.venv\Scripts\python.exe tests/run.py`
- **Full Output**:
```
============================================================
  🧪 Running Clipping Final Boss Test Suite
  👉 Python: Z:\Clipping open source\clipper-kit\clipper-kit\.venv\Scripts\python.exe
  👉 Root:   Z:\Clipping open source\clipper-kit\clipper-kit
============================================================

============================= test session starts =============================
platform win32 -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0 -- Z:\Clipping open source\clipper-kit\clipper-kit\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: Z:\Clipping open source\clipper-kit\clipper-kit
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.16.0
collected 39 items

tests/test_healthz.py::test_healthz_function_returns_200_and_expected_fields PASSED [  2%]
tests/test_healthz.py::test_healthz_returns_503_on_failing_dependency PASSED [  5%]
tests/test_priority1_and_templates.py::test_caption_templates_all_ten PASSED [  7%]
tests/test_priority1_and_templates.py::test_unique_titles_across_session PASSED [ 10%]
tests/test_priority1_and_templates.py::test_score_differentiation PASSED [ 12%]
tests/test_progress_callback.py::test_on_progress_signature_and_stages PASSED [ 15%]
tests/test_progress_callback.py::test_on_progress_default_and_legacy_arguments PASSED [ 17%]
tests/test_progress_callback.py::test_failed_job_preserves_stage_and_never_shows_ready PASSED [ 20%]
tests/test_stage1_pipeline.py::test_local_file_download_and_probe PASSED [ 23%]
tests/test_stage1_pipeline.py::test_transcription_runs PASSED            [ 25%]
tests/test_stage1_pipeline.py::test_candidate_picker PASSED              [ 28%]
tests/test_stage1_pipeline.py::test_cutter_creates_mp4 PASSED            [ 30%]
tests/test_stage1_pipeline.py::test_stage1_pipeline_generates_at_least_3_clips PASSED [ 33%]
tests/test_stage2_ranking.py::test_ranking_math_with_chat PASSED         [ 35%]
tests/test_stage2_ranking.py::test_ranking_math_without_chat_redistributed PASSED [ 38%]
tests/test_stage2_ranking.py::test_rank_ordering_and_renaming PASSED     [ 41%]
tests/test_stage2_ranking.py::test_api_get_session_clips PASSED          [ 43%]
tests/test_stage3_renderer.py::test_render_all_aspect_ratios_blur_fit[9:16] PASSED [ 46%]
tests/test_stage3_renderer.py::test_render_all_aspect_ratios_blur_fit[1:1] PASSED [ 48%]
tests/test_stage3_renderer.py::test_render_all_aspect_ratios_blur_fit[4:5] PASSED [ 51%]
tests/test_stage3_renderer.py::test_render_all_aspect_ratios_blur_fit[16:9] PASSED [ 53%]
tests/test_stage3_renderer.py::test_render_both_framing_modes[blur_fit] PASSED [ 56%]
tests/test_stage3_renderer.py::test_render_both_framing_modes[crop_to_face] PASSED [ 58%]
tests/test_stage3_renderer.py::test_render_clean_minimal_subtitles_off PASSED [ 61%]
tests/test_stage4_ai_thumbnail.py::test_no_key_metadata_generation PASSED [ 64%]
tests/test_stage4_ai_thumbnail.py::test_generate_clip_metadata_dispatcher PASSED [ 66%]
tests/test_stage4_ai_thumbnail.py::test_best_frame_extraction PASSED     [ 69%]
tests/test_stage4_ai_thumbnail.py::test_thumbnail_creation PASSED        [ 71%]
tests/test_stage5_api.py::test_static_ui_served PASSED                   [ 74%]
tests/test_stage5_api.py::test_static_css_contains_spec_theme PASSED     [ 76%]
tests/test_stage5_api.py::test_settings_api_get_and_put PASSED           [ 79%]
tests/test_stage5_api.py::test_clip_patch_and_regenerate PASSED          [ 82%]
tests/test_stage6_streamers.py::test_platform_detection PASSED           [ 84%]
tests/test_stage6_streamers.py::test_resolve_handle_and_platform PASSED  [ 87%]
tests/test_stage6_streamers.py::test_pin_and_manage_streamers PASSED     [ 89%]
tests/test_stage6_streamers.py::test_simulated_stream_spike_clipping PASSED [ 92%]
tests/test_stage7_youtube.py::test_dry_run_upload PASSED                 [ 94%]
tests/test_stage7_youtube.py::test_daily_upload_cap_enforcement PASSED   [ 97%]
tests/test_stage7_youtube.py::test_auth_status_check PASSED              [100%]

======================= 39 passed in 124.97s (0:02:04) ========================

============================================================
  ✅ TEST SUITE RESULT: ALL TESTS PASSED (EXIT CODE 0)
============================================================
```
- **Exit Code**: 0 (Clean pass, 0 failures, 0 skipped)

### Step 4: Real Pipeline Proof
- **Target URL Status**: `https://youtu.be/CsWOUBuokjo` is unavailable/deleted on YouTube.
- **Verification Run**: **local file, does NOT verify YouTube download**
- **Source**: `data/in/session_1_source.mp4` (Duration: 3029.23s)
- **Output Clip**: `data/out/session_1/01_wait_what_did_you_just_say.mp4`
- **ffprobe Results**:
  - Resolution: `1080x1920` (9:16 vertical)
  - Duration: `16.92s`
  - Video Codec: `h264` (High Profile)
  - Audio Codec: `aac` (LC)
  - Bitrate: `1464 kbps`
- **Viewed Frames**:
  - Frame 1 (t=2.0s): Extracted to `scratch/frame_2s.jpg`. Mean BGR: `[24.36, 25.51, 29.73]`, Std: `[45.24, 47.01, 52.08]`. Real podcast conversational scene showing speaker speaking with blurred vertical background fill. `is_black=False`.
  - Frame 2 (t=8.0s): Extracted to `scratch/frame_8s.jpg`. Mean BGR: `[25.06, 25.22, 27.53]`, Std: `[47.46, 48.38, 51.59]`. Speaker in mid-sentence with animated word-highlighted subtitle text rendered clearly in lower third. `is_black=False`.
- **Word-Level Caption Synchronization**:
  - Sample 1 (t=357.08s): Spoken word `"Family?"` (start: 357.08s, end: 357.62s)
  - Sample 2 (t=359.36s): Spoken word `"shit!"` (start: 359.36s, end: 359.78s)
  - Sample 3 (t=361.04s): Spoken word `"nice"` (start: 361.04s, end: 361.44s)
- **Server Log Review**:
  - Zero fatal server errors.
  - Startup health logged cleanly: `[Startup Health] Status: OK (Healthy: True)`.

### Step 5: Background Jobs Disk Persistence and Recovery
- **Storage**: `data/jobs.json` with atomic `.tmp` replace writing.
- **Fields Persisted**: `id`, `type`, `status` (`pending`/`running`/`completed`/`failed`), `stage`, `progress`, `message`, `error`, `result`, `created_at`, `updated_at`, `completed_at`, `metadata`.
- **Interruption Reconciliation**: On restart, any in-flight job with status `running` or `pending` (and not `complete`) is reconciled and marked failed with error: `"interrupted by restart"`.
- **Test File**: `tests/test_jobs_persistence.py` (1 passed in 0.13s).
- **Restart Demonstration Output**:
```
--- 1. Server Process A Starts ---
Created Job: ID=job_5e072a8a364f, Status=pending, Stage=queued
Job Running: ID=job_5e072a8a364f, Status=running, Stage=downloading, Progress=25%

--- 2. Server Crash / Termination Mid-Job ---
Process A terminated abruptly.

--- 3. Server Process B Restarts and Loads Disk State ---
[Job job_5e072a8a364f] Failed: interrupted by restart
[Jobs Recovery] Reconciled 1 in-flight job(s) as 'interrupted by restart'
Recovered Job: ID=job_5e072a8a364f
Status:        failed
Stage:         downloading
Error:         interrupted by restart
Message:       Failed: interrupted by restart
Progress:      25%
```

### Step 6: Architectural Gap Analysis
- **Deliverable**: `docs/gap-analysis.md`
- **Methodology**: Evaluated our active codebase (`clipper/`) against PeakCut reference architecture (`scratch/PeakCut/`, MIT License).
- **Scope**: 11 core architectural rows (live recording, rolling buffer, spike detection, ranking with score breakdown, per-clip editor, streamer pinning with name/avatar, AI title/caption/hashtags/thumbnail, scheduling and posting, health checks, gaming/GTA mode, job persistence).
- **Core Recommendation**: Retain our modernized, zero-key offline-first modules (ranking, ASS kinetic templates, healthz, jobs), and port gaming presets from `PeakCut/GAMING.md`.

### Step 7: Path Move Condition
- **Evaluation**: Project full path is `Z:\Clipping open source\clipper-kit\clipper-kit` (length: 47 characters).
- **Condition Check**: `path_len <= 100` and path is on external workspace drive Z: (not in nested AppData/IDE temp folder).
- **Status**: **SKIPPED** per specification ("only if Step 0 flagged a long or IDE-workspace path").


## Stage B run 1 (2026-11-20)

### Step 1: Real Path Check
- **Commands Executed**:
  - `subst`: No virtual drive subst mappings found.
  - `net use`: No network connections mapped (`There are no entries in the list`).
  - `Win32_LogicalDisk (DeviceID='Z:')`: `DriveType = 3` (`DRIVE_FIXED`, local physical NTFS partition), 167 GB free.
- **Resolved Real Path**: `Z:\Clipping open source\clipper-kit\clipper-kit`
- **True Path Length**: 47 characters (well under 100-character threshold).
- **Move to `C:\clipper`**: Not required per criteria (`path_len <= 100`).

### Step 2: Short Render Staging (clipper/renderer.py)
- **Staging Directory Function**: `get_render_staging_dir()` resolving to `%TEMP%\clp_tmp` (length: 44 chars) or `C:\clipper_tmp`.
- **Implementation**:
  - Subtitle generation and FFmpeg filter graph write exclusively to `staging_dir / f"clp_{id}.ass"` and `staging_dir / f"clp_{id}.mp4"`.
  - On render completion, `shutil.move()` atomically relocates the output MP4 to the target path `output_video`.
  - All staging files are automatically cleaned up in `finally` blocks.
- **Long Path Test**: `tests/test_short_render_staging.py`
  - Created test destination with 5-level nested directories and filename totaling **387 characters** (exceeding Windows 260 MAX_PATH limit).
  - Test Result: **2 passed in 3.28s**. Clip rendered and moved successfully into 387-character path.

### Step 3: Real YouTube End-to-End Proof (English & Hindi)
- **English Test Video**:
  - URL: `https://www.youtube.com/watch?v=Y6bbMQXQ180`
  - Title: *"Secrets of success in 8 words, 3 minutes | Richard St. John"*
  - Source Duration: `226.0s`
  - Session Directory: `data/out/session_1/`
  - Total Ranked Clips Generated: `3`
  - Ranked Clips Table:
    1. **Rank #1**: `"What 500 TED interviews taught me about success"` (Duration: `15.23s`, Score: `69.9`, Breakdown: Hook=80.2, Emotion=62.4, Story=59.0, Trend=70.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `4,478,693 bytes`
       - Frames: `scratch/english_clip_1_frame_1_3s.jpg` (t=3.79s, mean BGR: `[71.61, 35.85, 20.99]`, non-black) & `scratch/english_clip_1_frame_2_11s.jpg` (t=11.38s, mean BGR: `[84.68, 46.36, 29.74]`, non-black). Real stage talk footage with kinetic caption overlay.
       - Caption words: `[56.84s - 56.94s]: "So"`, `[56.94s - 57.02s]: "why"`, `[57.02s - 57.22s]: "don't"`, `[57.22s - 57.32s]: "I"`, `[57.32s - 57.58s]: "ask"`, `[57.58s - 57.80s]: "them"`.
    2. **Rank #2**: `"Do what you love and the money will follow"` (Duration: `16.70s`, Score: `64.5`, Breakdown: Hook=59.0, Emotion=74.0, Story=59.0, Trend=70.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `1,780,223 bytes`
       - Frames: `scratch/english_clip_2_frame_1_4s.jpg` (t=4.17s) & `scratch/english_clip_2_frame_2_12s.jpg` (t=12.5s). Real speaker and presentation slides. Non-black.
       - Caption words: `[76.96s - 76.98s]: "They"`, `[76.98s - 77.18s]: "don't"`, `[77.18s - 77.38s]: "do"`, `[77.38s - 77.54s]: "it"`, `[77.54s - 77.62s]: "for"`, `[77.62s - 77.90s]: "money."`.
    3. **Rank #3**: `"The Real Secret To Success (After 500 Interviews)"` (Duration: `18.30s`, Score: `63.8`, Breakdown: Hook=56.1, Emotion=75.8, Story=59.0, Trend=70.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `3,162,994 bytes`
       - Frames: `scratch/english_clip_3_frame_1_4s.jpg` (t=4.56s) & `scratch/english_clip_3_frame_2_13s.jpg` (t=13.68s). Non-black.

- **Hindi/Hinglish Test Video**:
  - URL: `https://www.youtube.com/watch?v=abI0txiZSyI`
  - Title: *"PM Modi ने Quad समिट में Trump के सामने ऐसा क्या कहा जिसकी हो रही है चर्चा?(BBC Hindi)"*
  - Source Duration: `262.0s`
  - Session Directory: `data/out/session_2/`
  - Total Ranked Clips Generated: `3`
  - Ranked Clips Table:
    1. **Rank #1**: `"Modi & Media Stress: Inside the Political Drama!"` (Duration: `28.32s`, Score: `62.5`, Breakdown: Hook=59.3, Emotion=57.2, Story=71.0, Trend=70.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `3,741,615 bytes`
       - Frames: `scratch/hindi_clip_1_frame_1_7s.jpg` (t=7.07s, mean BGR: `[36.23, 27.91, 36.74]`, non-black) & `scratch/hindi_clip_1_frame_2_21s.jpg` (t=21.21s, mean BGR: `[203.22, 198.97, 196.93]`, non-black). Real summit footage showing world leaders.
       - Caption words: `[131.16s - 131.62s]: "When"`, `[131.62s - 132.00s]: "the"`, `[132.00s - 132.18s]: "press"`, `[132.18s - 132.44s]: "didn't"`, `[132.44s - 132.64s]: "go"`, `[132.64s - 132.82s]: "out,"`.
    2. **Rank #2**: `"Trump Reveals The Truth About Modi's Leadership!"` (Duration: `30.04s`, Score: `60.6`, Breakdown: Hook=43.0, Emotion=69.0, Story=69.0, Trend=84.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `3,260,343 bytes`
       - Frames: `scratch/hindi_clip_2_frame_1_7s.jpg` (t=7.49s) & `scratch/hindi_clip_2_frame_2_22s.jpg` (t=22.47s). Non-black.
       - Caption words: `[94.54s - 94.76s]: "I"`, `[94.76s - 94.86s]: "have"`, `[94.86s - 94.90s]: "been"`, `[94.90s - 95.28s]: "with"`, `[95.28s - 95.80s]: "all"`, `[95.80s - 96.04s]: "three"`.
    3. **Rank #3**: `"PM Modi ne aisa kya bola ki sabhi hairan reh gaye?"` (Duration: `16.88s`, Score: `58.3`, Breakdown: Hook=64.1, Emotion=52.1, Story=47.0, Trend=70.0)
       - ffprobe: `1080x1920`, `h264`, `aac`, size: `3,343,541 bytes`
       - Frames: `scratch/hindi_clip_3_frame_1_4s.jpg` (t=4.21s) & `scratch/hindi_clip_3_frame_2_12s.jpg` (t=12.63s). Non-black.
       - Caption words (Hinglish): `[51.80s - 52.10s]: "Savalk"`, `[52.10s - 52.40s]: "jabab"`, `[52.40s - 52.52s]: "ka"`, `[52.52s - 52.74s]: "dhoar"`, `[52.74s - 53.12s]: "challahi"`, `[53.12s - 53.58s]: "dahata"` (*"Sawaal jawaab ka daur chal hi raha tha"*).
  - Glyph Rendering Check: Verified no missing-glyph tofu/boxes (`[?]`); ASS Arial/Inter fallback cleanly renders all alphanumeric and Devanagari romanized characters.
- **Server Logs**: Monitored `task-934.log` throughout run; zero fatal exceptions or unhandled tracebacks.

### Step 4: Real Server Restart & Job Persistence Test
- **Execution**:
  - Spawned long asynchronous background clipping job `job_4b7670b2de7d` targeting 15-minute video.
  - Progress reached: `35%` (`stage: transcribing`).
  - Active server process `PID 5312` was killed via `taskkill /F /PID 5312`.
  - Server restarted (`task-964`).
- **Disk State (`data/jobs.json`) Before Kill**:
```json
{
  "job_4b7670b2de7d": {
    "id": "job_4b7670b2de7d",
    "type": "clip_generation",
    "status": "running",
    "stage": "transcribing",
    "progress": 35,
    "message": "Transcribing long 15-minute video speech...",
    "error": null,
    "result": null,
    "metadata": {
      "url": "https://www.youtube.com/watch?v=UF8uR6Z6KLc",
      "top_n": 3
    }
  }
}
```
- **Disk State (`data/jobs.json`) After Restart**:
```json
{
  "job_4b7670b2de7d": {
    "id": "job_4b7670b2de7d",
    "type": "clip_generation",
    "status": "failed",
    "stage": "transcribing",
    "progress": 35,
    "message": "Failed: interrupted by restart",
    "error": "interrupted by restart",
    "result": null,
    "metadata": {
      "url": "https://www.youtube.com/watch?v=UF8uR6Z6KLc",
      "top_n": 3
    }
  }
}
```
- **Integrity Verification**: Job was reliably recovered from disk without duplicate entries or silent drop. Status reconciled to `failed` with explanation `"interrupted by restart"`.
- **Live Stream Recording Restart Mid-Recording**: **unverified** (streamlink dependency is not installed; simulated spike cutting is verified in test suite).

### Step 5: Frontend Contradiction Report
- **React / Tailwind Redesign Artifacts**:
  - `package.json` (665 B)
  - `components.json` (416 B)
  - `tailwind.config.js` (1,671 B)
  - `tsconfig.json` (538 B)
  - `components/final-boss-get-started.tsx` (10,982 B)
  - `components/ui/blackhole-hero-section.tsx` (46,733 B)
  - `components/ui/demo.tsx` (3,370 B)
  - `lib/utils.ts` (169 B)
- **Vanilla Frontend Artifacts**:
  - `clipper/web/static/index.html` (67,090 B)
  - `clipper/web/static/app.js` (91,916 B)
  - `clipper/web/static/style.css` (79,107 B)
  - `clipper/web/static/blackhole.js` (34,287 B)
  - `clipper/web/static/placeholder_thumb.svg` (1,322 B)
- **Active Served Frontend**:
  - The live FastAPI server strictly mounts and serves `clipper/web/static/` via `app.mount("/", StaticFiles(directory=STATIC_DIR, html=True))`.
  - The React `.tsx` components in `components/` are uncompiled and not linked to any active build pipeline.
- **Recommendation**:
  - **Keep the vanilla frontend (`clipper/web/static/`)** as the primary single-file/zero-build desktop UI for Clipper. It matches the single-command `python run.py` philosophy (Python 3.10+ and ffmpeg only, zero npm build step required for end users).
  - Retain the React artifacts in `components/` for reference if a full Vite SPA build step is introduced in a future release.
