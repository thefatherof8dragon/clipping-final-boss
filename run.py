"""Clipper single entrypoint runner.

Usage:
    python run.py                 # Start server and open browser
    python run.py youtube-login   # Authorize YouTube OAuth 2.0
"""

import os
import sys
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / ".venv"

def get_venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

def ensure_venv_and_reexec() -> None:
    """Ensures a virtual environment exists and re-executes inside it if needed."""
    is_in_venv = (sys.prefix != sys.base_prefix) or ("VIRTUAL_ENV" in os.environ)
    if is_in_venv:
        return

    venv_python = get_venv_python()
    if not venv_python.exists():
        print("Creating virtual environment in .venv...")
        import venv
        venv.create(VENV_DIR, with_pip=True)
        print("Installing requirements from requirements.txt...")
        pip_cmd = [str(venv_python), "-m", "pip", "install", "-r", str(ROOT_DIR / "requirements.txt")]
        subprocess.run(pip_cmd, check=True)

    # Re-execute with venv python
    cmd = [str(venv_python)] + sys.argv
    sys.exit(subprocess.call(cmd))

def check_ffmpeg() -> bool:
    """Verify ffmpeg is installed or discoverable."""
    # Add winget package paths to PATH if on Windows
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_pkgs.exists():
                for p in winget_pkgs.glob("**/ffmpeg.exe"):
                    os.environ["PATH"] = f"{p.parent};{os.environ.get('PATH', '')}"
                    break

    found = shutil.which("ffmpeg")
    if not found:
        print("\n" + "!" * 60)
        print("WARNING: FFmpeg was not found in your system PATH.")
        print("Please install FFmpeg to process videos:")
        print("  Windows: winget install Gyan.FFmpeg")
        print("  macOS:   brew install ffmpeg")
        print("  Linux:   sudo apt install ffmpeg")
        print("!" * 60 + "\n")
        return False
    return True

def open_browser_delayed(url: str, delay: float = 1.5):
    """Opens browser after server has started listening."""
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    t = threading.Thread(target=_open, daemon=True)
    t.start()

def main():
    ensure_venv_and_reexec()

    # Subcommand: youtube-login
    if len(sys.argv) > 1 and sys.argv[1] == "youtube-login":
        from clipper.youtube import run_desktop_auth_flow
        success = run_desktop_auth_flow()
        sys.exit(0 if success else 1)

    check_ffmpeg()

    url = "http://127.0.0.1:8000"
    print("\n" + "=" * 60)
    print("  🔥 Clipping Final Boss — Local AI Video & Stream Clipper")
    print(f"  👉 Open {url}")
    print("  🔒 Local only: bound to 127.0.0.1:8000")
    print("  ⌨️  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    open_browser_delayed(url)

    import uvicorn
    uvicorn.run("clipper.api:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
