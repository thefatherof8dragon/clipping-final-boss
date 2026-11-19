import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\Durvankur\.gemini\antigravity\brain\ff2df382-5c95-4ef5-b8e7-084a7fc0c52a")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_EXE):
    CHROME_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PYTHON_EXE = os.path.abspath(r".venv\Scripts\python.exe")
if not os.path.exists(PYTHON_EXE):
    PYTHON_EXE = sys.executable

print("Starting Clipping Final Boss server...")
server_cmd = [
    PYTHON_EXE, "-m", "uvicorn", "clipper.api:app",
    "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"
]
server_proc = subprocess.Popen(server_cmd)

try:
    # Wait for server to be responsive
    ready = False
    for attempt in range(15):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/settings", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass

    if not ready:
        raise RuntimeError("Server failed to respond within 8 seconds")

    print("Server ready on http://127.0.0.1:8000")

    # 1. Capture Get Started Page (Black Hole WebGL Hero + Quick Free Clipping)
    shot_get_started = ARTIFACT_DIR / "screenshot_get_started.png"
    print(f"Capturing Get Started Screen to {shot_get_started}...")
    cmd_get_started = [
        CHROME_EXE,
        "--headless=new",
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--window-size=1600,1050",
        "--virtual-time-budget=4000",
        f"--screenshot={shot_get_started}",
        "http://127.0.0.1:8000/?tab=get-started",
    ]
    subprocess.run(cmd_get_started, check=True)
    print("Get Started Screen captured successfully! Size:", shot_get_started.stat().st_size)

    # 2. Capture Clips Screen (Visual 9:16 Video Grid)
    shot_clips = ARTIFACT_DIR / "screenshot_clips_grid.png"
    print(f"Capturing Clips Grid Screen to {shot_clips}...")
    cmd_clips = [
        CHROME_EXE,
        "--headless=new",
        "--disable-gpu",
        "--window-size=1600,1000",
        "--virtual-time-budget=3000",
        f"--screenshot={shot_clips}",
        "http://127.0.0.1:8000/?tab=clips",
    ]
    subprocess.run(cmd_clips, check=True)
    print("Clips Screen captured successfully! Size:", shot_clips.stat().st_size)

    # 3. Capture Studio Editor Screen (Caption list, 10 templates, live preview, timeline)
    shot_editor = ARTIFACT_DIR / "screenshot_clip_editor.png"
    print(f"Capturing Clip Studio Editor to {shot_editor}...")
    cmd_editor = [
        CHROME_EXE,
        "--headless=new",
        "--disable-gpu",
        "--window-size=1600,1000",
        "--virtual-time-budget=3500",
        f"--screenshot={shot_editor}",
        "http://127.0.0.1:8000/?editor=1",
    ]
    subprocess.run(cmd_editor, check=True)
    print("Clip Studio Editor captured successfully! Size:", shot_editor.stat().st_size)

finally:
    print("Stopping server...")
    server_proc.terminate()
    try:
        server_proc.wait(timeout=3)
    except Exception:
        server_proc.kill()
    print("Server stopped.")
