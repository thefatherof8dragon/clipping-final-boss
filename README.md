# Clipping Final Boss (`clipping-final-boss`)

**Clipping Final Boss** is a free, local-only, open-source tool that turns long videos and live streams into ranked 9:16 short clips with burned animated captions, virality scoring, and thumbnails.

Everything runs on your local hardware (`127.0.0.1:8000`). No cloud subscriptions, no watermarks, and zero mandatory API keys.

---

## 5-Step Quickstart

1. **Clone or move the repository into a short path:**
   ```bash
   git clone https://github.com/your-username/clipping-final-boss.git C:\clipper
   cd C:\clipper
   ```
   > ⚠️ **Windows Path Limit (MAX_PATH = 260)**: Always run in a directory under 100 characters (e.g. `C:\clipper`). Clipper automatically stages intermediate FFmpeg rendering and ASS subtitle files in `%TEMP%\clp_tmp` before moving them into `data/out/` to eliminate path truncation errors.

2. **Install Python 3.10+ and FFmpeg:**
   - **Python**: Download and install Python 3.10 to 3.14 from [python.org](https://www.python.org/).
   - **FFmpeg**:
     - *Windows*: `winget install Gyan.FFmpeg`
     - *macOS*: `brew install ffmpeg`
     - *Linux*: `sudo apt update && sudo apt install ffmpeg`
   - **Node.js** (Optional/Recommended for YouTube challenge solving): `winget install OpenJS.NodeJS.LTS`

3. **Run the single entrypoint runner:**
   ```bash
   python run.py
   ```
   *(This script automatically creates a `.venv` virtual environment, installs all pinned requirements, verifies FFmpeg, and launches the FastAPI server at `http://127.0.0.1:8000`).*

4. **Open in your web browser:**
   ```
   http://127.0.0.1:8000
   ```

5. **Optional: Add API keys or Presets in Settings:**
   - Navigate to the **Settings** tab in the web UI.
   - You can optionally paste your Google Gemini, OpenAI, Groq, Anthropic, or Ollama endpoint keys.
   - Zero-key mode works 100% locally out of the box (faster-whisper + RMS loudness + local heuristic generator).
   - Gaming & GTA VI Launch presets prioritize clutch moments, boss fights, hype spikes, and Vice City triggers.

---

## YouTube Setup & Scheduling

1. **Google Cloud Console**: Create a project in [Google Cloud Console](https://console.cloud.google.com/projectcreate).
2. **Enable YouTube Data API v3**: Under APIs & Services, enable **YouTube Data API v3**.
3. **OAuth Consent Screen**: Choose **External**, add your Google email under **Test Users**.
4. **Create Credentials**: Create credentials of type **OAuth client ID** → **Desktop app**.
5. **Connect**: Copy the Client ID and Client Secret into the Settings wizard or run:
   ```bash
   python run.py youtube-login
   ```

### Responsible Use & Creator Permissions
> ⚠️ **Creator Permission Required**: Re-uploading other creators' content without permission can lead to copyright strikes or account termination. Always obtain written consent or clip strictly within official streamer clipping programs.
>
> 🔒 **Daily Upload Quota Limit**: YouTube Data API accounts have a default quota of 10,000 units/day. Each video upload requires 1,600 units (~6 uploads per day). Clipping Final Boss enforces a default safety cap of **6 uploads per day** (`DAILY_UPLOAD_CAP=6`) with auto-upload disabled by default.

---

## Multi-Platform Social Export

Each clip card features one-click copy buttons tailored for social platforms:
- **📱 TikTok**: Hook + concise caption + 4–6 high-CTR hashtags (`#fyp`, `#viral`), clamped within 2,200 characters.
- **📸 Instagram Reels**: Spaced caption structure (`hook` + `\n.\n` + tags) including `#reels` and `#reelsinstagram`.
- **▶️ YouTube Shorts**: Optimized 100-character title with `#shorts`, full description, and clean comma-separated tag strings.

---

## Zero-Key Mode vs. Optional Cloud Keys

Clipping Final Boss works **100% locally with no keys**:
- **Local Speech-to-Text**: `faster-whisper` (word-level timestamps and offline acoustic processing).
- **Candidate Picker**: Multi-modal energy scoring (audio loudness peaks via `ebur128` + sentence boundary hook detection).
- **Duration Chips**: Strictly aligns clips to **Auto (< 90s)**, **Under 30s** (15–30s), **30 to 60s**, **60 to 90s**, or **Over 90s**.
- **10 Kinetic Caption Templates**: Pop, Clean, Box, Neon, Outline, Comic, Minimal, Highlight, Gradient, Typewriter.
- **Visual Studio Editor**: Words/Lines toggle, interactive word editing, face-tracking crop (`crop`) or background blur (`blur`), trim timeline, and ASS/FFmpeg video rendering.

---

## Test Suite

Run the single unified test runner:
```bash
python tests/run.py
```

Check health status:
```bash
curl http://127.0.0.1:8000/healthz
```

---

## Credits & Acknowledgments

* **[PeakCut](https://github.com/haziqahmedqasmi/PeakCut)** (MIT License): Based on and inspired by PeakCut by Haziq Ahmed Qasmi. Special thanks for the foundational concepts in live-stream rolling buffer management, chat spike signal tracking, game detection heuristics, and kinetic subtitle rendering.


