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
