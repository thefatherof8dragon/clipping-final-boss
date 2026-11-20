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
