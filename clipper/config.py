"""Configuration and directory management for Clipper."""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_IN_DIR = DATA_DIR / "in"
DATA_OUT_DIR = DATA_DIR / "out"
DATA_BUFFER_DIR = DATA_DIR / "buffer"
STATE_FILE = DATA_DIR / "state.json"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"

_CACHED_FFMPEG: Optional[str] = None
_CACHED_FFPROBE: Optional[str] = None

def ensure_directories() -> None:
    """Create data directories if they do not exist."""
    DATA_IN_DIR.mkdir(parents=True, exist_ok=True)
    DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_BUFFER_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text("{}", encoding="utf-8")

def find_ffmpeg() -> str:
    """Find the path to the ffmpeg executable with caching."""
    global _CACHED_FFMPEG
    if _CACHED_FFMPEG and os.path.exists(_CACHED_FFMPEG):
        return _CACHED_FFMPEG

    found = shutil.which("ffmpeg")
    if found:
        _CACHED_FFMPEG = found
        return found

    # Refresh PATH on Windows from registry or winget folder
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for p in winget_pkgs.glob("**/ffmpeg.exe"):
                if p.exists():
                    os.environ["PATH"] = f"{p.parent};{os.environ.get('PATH', '')}"
                    _CACHED_FFMPEG = str(p)
                    return _CACHED_FFMPEG

    _CACHED_FFMPEG = "ffmpeg"
    return "ffmpeg"

def find_ffprobe() -> str:
    """Find the path to the ffprobe executable with caching."""
    global _CACHED_FFPROBE
    if _CACHED_FFPROBE and os.path.exists(_CACHED_FFPROBE):
        return _CACHED_FFPROBE

    found = shutil.which("ffprobe")
    if found:
        _CACHED_FFPROBE = found
        return found

    ffmpeg = find_ffmpeg()
    if ffmpeg and ffmpeg != "ffmpeg":
        probe = Path(ffmpeg).parent / "ffprobe.exe"
        if probe.exists():
            _CACHED_FFPROBE = str(probe)
            return _CACHED_FFPROBE

    _CACHED_FFPROBE = "ffprobe"
    return "ffprobe"

class Settings:
    """Application settings loaded from .env with fallback defaults."""

    def __init__(self):
        self.reload()

    def reload(self) -> None:
        load_dotenv(ENV_FILE, override=True)
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").strip()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip()
        self.transcription_option: str = os.getenv("TRANSCRIPTION_OPTION", "local_whisper").strip()
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "tiny").strip()
        self.youtube_client_id: str = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
        self.youtube_client_secret: str = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
        self.youtube_channel_name: str = os.getenv("YOUTUBE_CHANNEL_NAME", "").strip()
        self.record_height: int = int(os.getenv("RECORD_HEIGHT", "720"))
        self.spike_min_msgs: int = int(os.getenv("SPIKE_MIN_MSGS", "120"))
        self.auto_upload: bool = os.getenv("AUTO_UPLOAD", "false").lower() in ("true", "1", "yes")
        self.daily_upload_cap: int = int(os.getenv("DAILY_UPLOAD_CAP", "5"))
        self.ytdlp_cookie_browser: str = os.getenv("YTDLP_COOKIE_BROWSER", "").strip()
        self.ytdlp_sleep_interval: int = int(os.getenv("YTDLP_SLEEP_INTERVAL", "0"))
        self.ytdlp_player_client: str = os.getenv("YTDLP_PLAYER_CLIENT", "web,android").strip()
        self.ytdlp_js_runtime: str = os.getenv("YTDLP_JS_RUNTIME", "node").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "llm_provider": self.llm_provider,
            "gemini_api_key": self.gemini_api_key,
            "openai_api_key": self.openai_api_key,
            "groq_api_key": self.groq_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "ollama_url": self.ollama_url,
            "transcription_option": self.transcription_option,
            "whisper_model": self.whisper_model,
            "youtube_client_id": self.youtube_client_id,
            "youtube_client_secret": self.youtube_client_secret,
            "youtube_channel_name": self.youtube_channel_name,
            "record_height": self.record_height,
            "spike_min_msgs": self.spike_min_msgs,
            "auto_upload": self.auto_upload,
            "daily_upload_cap": self.daily_upload_cap,
            "ytdlp_cookie_browser": self.ytdlp_cookie_browser,
            "ytdlp_sleep_interval": self.ytdlp_sleep_interval,
            "ytdlp_player_client": self.ytdlp_player_client,
            "ytdlp_js_runtime": self.ytdlp_js_runtime,
            "ffmpeg_available": bool(shutil.which(find_ffmpeg()) or shutil.which("ffmpeg")),
        }

    def save(self, updates: Dict[str, Any]) -> None:
        """Update .env file with new settings."""
        current = {}
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    current[k.strip()] = v.strip()
        elif ENV_EXAMPLE_FILE.exists():
            for line in ENV_EXAMPLE_FILE.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    current[k.strip()] = v.strip()

        key_map = {
            "llm_provider": "LLM_PROVIDER",
            "gemini_api_key": "GEMINI_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "groq_api_key": "GROQ_API_KEY",
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "ollama_url": "OLLAMA_URL",
            "transcription_option": "TRANSCRIPTION_OPTION",
            "whisper_model": "WHISPER_MODEL",
            "youtube_client_id": "YOUTUBE_CLIENT_ID",
            "youtube_client_secret": "YOUTUBE_CLIENT_SECRET",
            "youtube_channel_name": "YOUTUBE_CHANNEL_NAME",
            "ytdlp_cookie_browser": "YTDLP_COOKIE_BROWSER",
            "ytdlp_sleep_interval": "YTDLP_SLEEP_INTERVAL",
            "ytdlp_player_client": "YTDLP_PLAYER_CLIENT",
            "ytdlp_js_runtime": "YTDLP_JS_RUNTIME",
            "record_height": "RECORD_HEIGHT",
            "spike_min_msgs": "SPIKE_MIN_MSGS",
            "auto_upload": "AUTO_UPLOAD",
            "daily_upload_cap": "DAILY_UPLOAD_CAP",
        }

        for k, v in updates.items():
            env_key = key_map.get(k, k.upper())
            if isinstance(v, bool):
                current[env_key] = "true" if v else "false"
            else:
                current[env_key] = str(v)

        lines = [
            "# All keys are stored locally on your machine. Never committed or sent anywhere.",
            f"LLM_PROVIDER={current.get('LLM_PROVIDER', 'gemini')}",
            f"GEMINI_API_KEY={current.get('GEMINI_API_KEY', '')}",
            f"OPENAI_API_KEY={current.get('OPENAI_API_KEY', '')}",
            f"GROQ_API_KEY={current.get('GROQ_API_KEY', '')}",
            f"ANTHROPIC_API_KEY={current.get('ANTHROPIC_API_KEY', '')}",
            f"OLLAMA_URL={current.get('OLLAMA_URL', 'http://127.0.0.1:11434')}",
            f"TRANSCRIPTION_OPTION={current.get('TRANSCRIPTION_OPTION', 'local_whisper')}",
            f"WHISPER_MODEL={current.get('WHISPER_MODEL', 'base')}",
            f"YOUTUBE_CLIENT_ID={current.get('YOUTUBE_CLIENT_ID', '')}",
            f"YOUTUBE_CLIENT_SECRET={current.get('YOUTUBE_CLIENT_SECRET', '')}",
            f"YOUTUBE_CHANNEL_NAME={current.get('YOUTUBE_CHANNEL_NAME', '')}",
            f"RECORD_HEIGHT={current.get('RECORD_HEIGHT', '720')}",
            f"SPIKE_MIN_MSGS={current.get('SPIKE_MIN_MSGS', '120')}",
            f"AUTO_UPLOAD={current.get('AUTO_UPLOAD', 'false')}",
            f"DAILY_UPLOAD_CAP={current.get('DAILY_UPLOAD_CAP', '5')}",
        ]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.reload()

ensure_directories()
settings = Settings()
