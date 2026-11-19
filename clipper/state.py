"""State persistence for pinned streamers, daily uploads, and active sessions."""

import json
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .config import STATE_FILE

def load_state() -> Dict[str, Any]:
    """Load application state from data/state.json."""
    if not STATE_FILE.exists():
        return {
            "streamers": [],
            "uploads": {"date": str(date.today()), "count": 0},
            "sessions": {},
        }
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if "streamers" not in data:
            data["streamers"] = []
        if "uploads" not in data:
            data["uploads"] = {"date": str(date.today()), "count": 0}
        if "sessions" not in data:
            data["sessions"] = {}
        return data
    except Exception:
        return {
            "streamers": [],
            "uploads": {"date": str(date.today()), "count": 0},
            "sessions": {},
        }

def save_state(state: Dict[str, Any]) -> None:
    """Save application state to data/state.json."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def get_pinned_streamers() -> List[Dict[str, Any]]:
    return load_state().get("streamers", [])

def add_streamer(name: str, url: str, platform: str, avatar_url: str = "") -> Dict[str, Any]:
    state = load_state()
    streamer_id = f"st_{abs(hash(url)) % 1000000:06d}"
    item = {
        "id": streamer_id,
        "name": name,
        "url": url,
        "platform": platform.lower(),
        "avatar_url": avatar_url,
        "is_live": False,
        "elapsed_time": "00:00:00",
        "chat_status": "disconnected",
        "chat_rate_history": [10, 15, 12, 18, 22, 15, 30, 45, 110, 140, 60, 35],
        "clips_count": 0,
        "clips": [],
        "auto_schedule": False,
    }
    # Avoid duplicate URLs
    state["streamers"] = [s for s in state["streamers"] if s["url"] != url]
    state["streamers"].append(item)
    save_state(state)
    return item

def update_streamer(streamer_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    state = load_state()
    for s in state["streamers"]:
        if s["id"] == streamer_id:
            s.update(updates)
            save_state(state)
            return s
    return None

def remove_streamer(streamer_id: str) -> bool:
    state = load_state()
    initial_len = len(state["streamers"])
    state["streamers"] = [s for s in state["streamers"] if s["id"] != streamer_id]
    if len(state["streamers"]) != initial_len:
        save_state(state)
        return True
    return False

def check_and_increment_upload() -> Tuple[bool, int, str]:
    """
    Checks if daily upload cap has been reached.
    If not, increments count and returns (True, count, message).
    """
    from .config import settings
    state = load_state()
    today_str = str(date.today())
    uploads = state.get("uploads", {})
    if uploads.get("date") != today_str:
        uploads["date"] = today_str
        uploads["count"] = 0

    if uploads["count"] >= settings.daily_upload_cap:
        return (False, uploads["count"], f"Daily upload cap of {settings.daily_upload_cap} reached for today ({today_str}).")

    uploads["count"] += 1
    state["uploads"] = uploads
    save_state(state)
    return (True, uploads["count"], "Upload approved.")
