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
