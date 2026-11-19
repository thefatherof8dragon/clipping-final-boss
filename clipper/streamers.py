"""
Pinned streamers and live stream monitoring with rolling circular buffer and chat spike detection.
Integrated with PeakCut-inspired StreamBufferRecorder and RollingBaselineSpikeDetector.
"""

import os
import time
import shutil
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .config import DATA_BUFFER_DIR, DATA_OUT_DIR, find_ffmpeg, find_ffprobe, settings
from .state import load_state, save_state, get_pinned_streamers, update_streamer
from .cutter import cut_clip
from .live_engine import (
    StreamBufferRecorder,
    TwitchAnonymousChatListener,
    RollingBaselineSpikeDetector,
    AUTO_BEFORE,
    AUTO_AFTER,
    AUTO_GAP,
    MERGE_WINDOW,
    DEFAULT_BUFFER_MIN,
)
from .thumbnail import extract_poster_frame
from .ai import extract_local_metadata

import re
import json
import httpx

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Active live recorder jobs {streamer_id: LiveWatcher}
_ACTIVE_WATCHERS: Dict[str, Any] = {}


def detect_platform(url: str) -> str:
    """Identify streaming platform from URL or username."""
    u = url.lower().strip()
    if "twitch.tv" in u or u.startswith("twitch:"):
        return "twitch"
    if "kick.com" in u or u.startswith("kick:"):
        return "kick"
    if "youtube.com" in u or "youtu.be" in u or u.startswith("youtube:") or u.startswith("@"):
        return "youtube"
    return "unknown"


def fetch_streamer_metadata(url: str, platform: str) -> Dict[str, str]:
    """Fetches public channel name and avatar URL without requiring API keys."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    plat = platform.lower()
    meta = {"name": "", "avatar_url": ""}

    try:
        if plat == "youtube":
            clean_url = url.split("/live")[0].split("/streams")[0].rstrip("/")
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.get(clean_url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    t_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
                    img_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
                    if t_m:
                        meta["name"] = t_m.group(1).replace(" - YouTube", "").strip()
                    if img_m:
                        meta["avatar_url"] = img_m.group(1).strip()
        elif plat == "twitch":
            handle = url.rstrip("/").split("/")[-1].lstrip("@")
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.get(f"https://www.twitch.tv/{handle}", headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    t_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
                    img_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
                    if t_m:
                        meta["name"] = t_m.group(1).replace(" - Twitch", "").strip()
                    if img_m:
                        meta["avatar_url"] = img_m.group(1).strip()
        elif plat == "kick":
            handle = url.rstrip("/").split("/")[-1].lstrip("@")
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.get(f"https://kick.com/api/v1/channels/{handle}", headers=headers)
                if resp.status_code == 200:
                    d = resp.json()
                    user = d.get("user", {})
                    meta["name"] = user.get("username") or d.get("slug") or handle
                    meta["avatar_url"] = user.get("profile_pic", "")
    except Exception:
        pass

    return meta


def check_youtube_live(url: str) -> Dict[str, Any]:
    """Check if YouTube channel is live via /live page detection or yt-dlp."""
    u = url.strip()
    if not u.startswith("http"):
        handle = u.lstrip("@")
        live_url = f"https://www.youtube.com/@{handle}/live"
    elif "/live" not in u and ("/watch" not in u):
        live_url = u.rstrip("/") + "/live"
    else:
        live_url = u

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            resp = client.get(live_url, headers=headers)
            if resp.status_code == 404:
                return {
                    "is_live": False,
                    "title": "",
                    "viewers": 0,
                    "status": "Error",
                    "reason": "Channel or handle not found (404)",
                }
            if resp.status_code in (403, 429):
                return {
                    "is_live": False,
                    "title": "",
                    "viewers": 0,
                    "status": "Error",
                    "reason": f"YouTube rate-limited or blocked ({resp.status_code})",
                }

            html = resp.text
            is_live = bool(
                '"isLive":true' in html
                or '"status":"LIVE"' in html
                or '"isLiveBroadcast":true' in html
                or '"liveBroadcastDetails"' in html
            )

            title = ""
            viewers = 0

            title_match = re.search(r'<meta name="title" content="([^"]+)">', html)
            if title_match:
                title = title_match.group(1).replace(" - YouTube", "").strip()
            elif "<title>" in html:
                t_m = re.search(r'<title>([^<]+)</title>', html)
                if t_m:
                    title = t_m.group(1).replace(" - YouTube", "").strip()

            viewers_match = re.search(r'"concurrentViewers":"([0-9,]+)"', html) or re.search(r'([0-9,]+)\s+watching', html)
            if viewers_match:
                try:
                    viewers = int(viewers_match.group(1).replace(",", ""))
                except ValueError:
                    viewers = 0

            if is_live:
                return {
                    "is_live": True,
                    "title": title or "Live Stream",
                    "viewers": viewers,
                    "status": "LIVE",
                    "reason": "Broadcasting now",
                }
            else:
                return {
                    "is_live": False,
                    "title": title,
                    "viewers": 0,
                    "status": "Offline",
                    "reason": "Channel is not currently broadcasting",
                }
    except httpx.TimeoutException:
        return {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": "Connection timed out checking YouTube",
        }
    except Exception as e:
        return {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": f"Check error: {str(e)}",
        }


def check_kick_live(url: str) -> Dict[str, Any]:
    """Check if Kick channel is live using Kick channel API."""
    u = url.strip().rstrip("/")
    slug = u.split("/")[-1].replace("@", "")

    api_url = f"https://kick.com/api/v2/channels/{slug}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(api_url, headers=headers)
            if resp.status_code == 404:
                return {
                    "is_live": False,
                    "title": "",
                    "viewers": 0,
                    "status": "Error",
                    "reason": f"Kick channel '{slug}' does not exist (404)",
                }
            if resp.status_code in (403, 503):
                v1_url = f"https://kick.com/api/v1/channels/{slug}"
                v1_resp = client.get(v1_url, headers=headers)
                if v1_resp.status_code == 200:
                    resp = v1_resp
                else:
                    return {
                        "is_live": False,
                        "title": "",
                        "viewers": 0,
                        "status": "Error",
                        "reason": "Cloudflare challenge or verification required by Kick",
                    }

            if resp.status_code == 200:
                data = resp.json()
                livestream = data.get("livestream")
                if livestream and (livestream.get("is_live", False) or livestream.get("session_title")):
                    return {
                        "is_live": True,
                        "title": livestream.get("session_title", f"{slug} Live"),
                        "viewers": int(livestream.get("viewer_count", 0)),
                        "status": "LIVE",
                        "reason": "Broadcasting now",
                    }
                else:
                    return {
                        "is_live": False,
                        "title": "",
                        "viewers": 0,
                        "status": "Offline",
                        "reason": "Streamer is currently offline",
                    }
            return {
                "is_live": False,
                "title": "",
                "viewers": 0,
                "status": "Error",
                "reason": f"API responded with status {resp.status_code}",
            }
    except httpx.TimeoutException:
        return {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": "Kick API request timed out",
        }
    except Exception as e:
        return {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": f"Kick check error: {str(e)}",
        }


def check_twitch_live(url: str) -> Dict[str, Any]:
    """Check if Twitch channel is live using public GQL endpoint or web page inspection."""
    u = url.strip().rstrip("/")
    login = u.split("/")[-1].replace("@", "").lower()

    gql_url = "https://gql.twitch.tv/gql"
    headers = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    query = {
        "query": f"""query {{
            user(login: "{login}") {{
                stream {{
                    id
                    title
                    viewersCount
                    game {{ name }}
                }}
            }}
        }}"""
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(gql_url, headers=headers, json=query)
            if resp.status_code == 200:
                data = resp.json()
                user_data = data.get("data", {}).get("user")
                if not user_data:
                    return {
                        "is_live": False,
                        "title": "",
                        "viewers": 0,
                        "status": "Error",
                        "reason": f"Twitch user '{login}' not found",
                    }
                stream = user_data.get("stream")
                if stream:
                    return {
                        "is_live": True,
                        "title": stream.get("title", f"{login} on Twitch"),
                        "viewers": int(stream.get("viewersCount", 0)),
                        "status": "LIVE",
                        "reason": "Broadcasting now",
                    }
                else:
                    return {
                        "is_live": False,
                        "title": "",
                        "viewers": 0,
                        "status": "Offline",
                        "reason": "Channel is not live",
                    }
    except Exception:
        pass

    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            page_resp = client.get(f"https://www.twitch.tv/{login}", headers={"User-Agent": "Mozilla/5.0"})
            if '"isLiveBroadcast":true' in page_resp.text:
                return {
                    "is_live": True,
                    "title": f"{login} Live",
                    "viewers": 0,
                    "status": "LIVE",
                    "reason": "Broadcasting live",
                }
            return {
                "is_live": False,
                "title": "",
                "viewers": 0,
                "status": "Offline",
                "reason": "Channel is offline",
            }
    except Exception as e:
        return {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": f"Twitch check error: {str(e)}",
        }


def check_channel_live(url: str, platform: Optional[str] = None) -> Dict[str, Any]:
    """Unified channel live checker with status, title, viewer count, and failure reasons."""
    plat = platform or detect_platform(url)

    if plat == "youtube":
        res = check_youtube_live(url)
    elif plat == "kick":
        res = check_kick_live(url)
    elif plat == "twitch":
        res = check_twitch_live(url)
    else:
        res = {
            "is_live": False,
            "title": "",
            "viewers": 0,
            "status": "Error",
            "reason": "Unknown platform. Please provide a YouTube, Twitch, or Kick URL.",
        }

    res["platform"] = plat
    res["checked_at"] = time.strftime("%H:%M:%S")
    return res


def resolve_handle_and_platform(input_val: str, chosen_platform: Optional[str] = "auto") -> tuple[str, str]:
    """Resolves input handle or URL and platform. If auto, probes platforms and defaults to Twitch."""
    val = input_val.strip()
    plat = (chosen_platform or "auto").lower()

    if val.startswith("http://") or val.startswith("https://"):
        detected = detect_platform(val)
        return val, (detected if detected != "unknown" else (plat if plat != "auto" else "twitch"))

    handle = val.lstrip("@").strip()
    if plat == "twitch":
        return f"https://www.twitch.tv/{handle}", "twitch"
    elif plat == "kick":
        return f"https://kick.com/{handle}", "kick"
    elif plat == "youtube":
        return f"https://www.youtube.com/@{handle}", "youtube"

    found_platforms = []
    try:
        t_res = check_twitch_live(f"https://www.twitch.tv/{handle}")
        if "not found" not in str(t_res.get("reason", "")).lower():
            found_platforms.append("twitch")
    except Exception:
        pass

    try:
        k_res = check_kick_live(f"https://kick.com/{handle}")
        if "does not exist" not in str(k_res.get("reason", "")).lower() and "404" not in str(k_res.get("reason", "")):
            found_platforms.append("kick")
    except Exception:
        pass

    try:
        y_res = check_youtube_live(f"https://www.youtube.com/@{handle}")
        if "not found" not in str(y_res.get("reason", "")).lower() and "404" not in str(y_res.get("reason", "")):
            found_platforms.append("youtube")
    except Exception:
        pass

    if "twitch" in found_platforms:
        return f"https://www.twitch.tv/{handle}", "twitch"
    elif "kick" in found_platforms:
        return f"https://kick.com/{handle}", "kick"
    elif "youtube" in found_platforms:
        return f"https://www.youtube.com/@{handle}", "youtube"
    else:
        return f"https://www.twitch.tv/{handle}", "twitch"


class LiveWatcher:
    """
    Manages rolling buffer recording, chat monitoring, real-time spike detection,
    and automatic end-of-stream clip harvesting for a pinned streamer.
    """

    def __init__(self, streamer_id: str, url: str, platform: str, buffer_minutes: int = DEFAULT_BUFFER_MIN):
        self.streamer_id = streamer_id
        self.url = url
        self.platform = platform
        self.buffer_minutes = buffer_minutes

        self.start_time = time.time()
        self.stop_event = threading.Event()
        self.clips_taken: List[Dict[str, Any]] = []
        self.last_clip_time: float = 0.0
        self.per_stream_cap: int = 10

        self.recorder = StreamBufferRecorder(streamer_id, url, platform, buffer_minutes=buffer_minutes)
        self.chat_listener: Optional[TwitchAnonymousChatListener] = None
        self.spike_detector = RollingBaselineSpikeDetector(
            baseline_seconds=180,
            jump_threshold=0.60,
            cooldown_seconds=AUTO_GAP,
        )

        self.worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts chat listener and monitor thread."""
        if self.platform == "twitch":
            handle = self.url.rstrip("/").split("/")[-1].lstrip("@")
            self.chat_listener = TwitchAnonymousChatListener(handle)
            self.chat_listener.start()
            self.recorder.signal_health["chat"] = "connecting"
        else:
            self.recorder.signal_health["chat"] = "audio-only fallback"

        threading.Thread(target=self._resolve_and_record, daemon=True, name=f"watch_{self.streamer_id}").start()

        self.worker_thread = threading.Thread(target=self._watcher_loop, daemon=True, name=f"loop_{self.streamer_id}")
        self.worker_thread.start()

    def _resolve_and_record(self) -> None:
        """Resolves live stream playable URL via yt-dlp."""
        if not yt_dlp:
            self.recorder.signal_health["buffer"] = "error: yt-dlp missing"
            return

        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if info and info.get("url"):
                    playable_url = info["url"]
                    self.recorder.start(playable_url)
                elif info and info.get("requested_formats"):
                    playable_url = info["requested_formats"][0]["url"]
                    self.recorder.start(playable_url)
                else:
                    self.recorder.signal_health["buffer"] = "offline / no url"
        except Exception as e:
            self.recorder.signal_health["buffer"] = f"resolve notice: {str(e)[:30]}"

    def _watcher_loop(self) -> None:
        """Periodic loop monitoring chat rates, audio levels, spikes, and updating state."""
        while not self.stop_event.is_set():
            time.sleep(2.0)
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"

            chat_active = bool(self.chat_listener and self.chat_listener.is_connected)
            if self.chat_listener:
                self.recorder.signal_health["chat"] = (
                    "connected" if self.chat_listener.is_connected else self.chat_listener.status
                )
            else:
                self.recorder.signal_health["chat"] = "audio-only fallback"

            chat_counts = []
            if chat_active:
                now_s = int(time.time())
                chat_counts = [self.chat_listener.chat_rates.get(t, 0) for t in range(now_s - 180, now_s)]

            spike = self.spike_detector.evaluate(
                db_history=self.recorder.db_history,
                chat_counts=chat_counts,
                chat_active=chat_active,
            )

            if spike and len(self.clips_taken) < self.per_stream_cap:
                self._handle_spike(spike)

            update_streamer(self.streamer_id, {
                "elapsed": elapsed_str,
                "elapsed_seconds": elapsed,
                "signal_health": self.recorder.signal_health,
                "clips_count": len(self.clips_taken),
                "last_clip_time": time.strftime("%H:%M:%S", time.localtime(self.last_clip_time)) if self.last_clip_time else None,
            })

    def _handle_spike(self, spike: Dict[str, Any]) -> None:
        """Cuts a clip from the rolling buffer for the detected spike."""
        now = time.time()
        if now - self.last_clip_time < MERGE_WINDOW:
            return

        self.last_clip_time = now
        center_stream_sec = self.recorder.seg_clock - (AUTO_AFTER / 2.0)
        clip_path = self.recorder.cut_buffer_clip(
            center_time=center_stream_sec,
            pre_roll=AUTO_BEFORE,
            post_roll=AUTO_AFTER,
        )

        if clip_path and clip_path.exists():
            clip_info = {
                "id": f"clip_{len(self.clips_taken) + 1}",
                "title": f"Live Spike ({spike['reasons']})",
                "file_path": str(clip_path),
                "created_at": time.strftime("%H:%M:%S"),
                "score": spike["combined_score"],
                "loud_score": spike["loud_score"],
                "chat_score": spike["chat_score"],
                "reasons": spike["reasons"],
            }
            self.clips_taken.append(clip_info)
            update_streamer(self.streamer_id, {
                "clips": self.clips_taken,
                "clips_count": len(self.clips_taken),
            })

    def on_spike_detected(self, spike_rate: int) -> None:
        """Direct trigger for manual / test spikes."""
        now = time.time()
        self.last_clip_time = now
        clip_name = f"spike_clip_{len(self.clips_taken) + 1}.mp4"
        out_clip = self.recorder.clips_dir / clip_name

        if self.recorder.segments:
            seg = self.recorder.segments[-1][0]
            if seg.exists():
                cut_clip(seg, out_clip, start=0.0, end=min(30.0, 15.0))
        elif (self.recorder.buf_dir / "seg_000.mp4").exists():
            cut_clip(self.recorder.buf_dir / "seg_000.mp4", out_clip, start=0.0, end=10.0)

        clip_info = {
            "id": f"clip_{len(self.clips_taken) + 1}",
            "title": f"Chat Spike ({spike_rate} msgs/min)",
            "file_path": str(out_clip),
            "created_at": time.strftime("%H:%M:%S"),
            "spike_rate": spike_rate,
            "score": min(95.0, max(60.0, spike_rate * 0.5)),
        }
        self.clips_taken.append(clip_info)
        update_streamer(self.streamer_id, {
            "clips": self.clips_taken,
            "clips_count": len(self.clips_taken),
            "last_clip_time": time.strftime("%H:%M:%S"),
        })

    def stop(self) -> None:
        """Stops watching, harvests clips into a final session, and cleans buffer."""
        self.stop_event.set()
        if self.chat_listener:
            self.chat_listener.stop()
        self.recorder.stop()

        if self.clips_taken:
            self._harvest_to_session()

        self.recorder.cleanup_buffer()

    def _harvest_to_session(self) -> None:
        """Ranks harvested live clips and registers them as a finished session in the Clips tab."""
        try:
            from .session import get_next_session_dir
            session_dir = get_next_session_dir()
            session_id = session_dir.name

            session_clips = []
            used_titles = set()

            for idx, clip in enumerate(self.clips_taken, start=1):
                src_path = Path(clip["file_path"])
                if not src_path.exists():
                    continue

                dest_name = f"{idx:02d}_live_clip_{idx}.mp4"
                dest_path = session_dir / dest_name
                shutil.copy2(src_path, dest_path)

                poster_name = f"{dest_path.stem}_poster.png"
                poster_path = session_dir / poster_name
                extract_poster_frame(dest_path, poster_path, timestamp_sec=1.0)

                meta = extract_local_metadata(
                    f"{clip['title']} live broadcast highlight moment",
                    clip_rank=idx,
                    used_titles=used_titles,
                )
                used_titles.add(meta["title"])

                session_clips.append({
                    "id": f"{session_id}_clip_{idx}",
                    "rank": idx,
                    "title": meta["title"],
                    "caption": meta["caption"],
                    "hashtags": meta["hashtags"],
                    "score": clip.get("score", 75.0),
                    "hook_score": clip.get("loud_score", 75.0),
                    "emotion_score": clip.get("chat_score", 70.0),
                    "trend_score": 72.0,
                    "flow_score": 75.0,
                    "start": 0.0,
                    "end": 30.0,
                    "duration": 30.0,
                    "filename": dest_name,
                    "rendered_name": dest_name,
                    "file_path": str(dest_path),
                    "rendered_path": str(dest_path),
                    "video_url": f"/api/media/{session_id}/{dest_name}",
                    "rendered_url": f"/api/media/{session_id}/{dest_name}",
                    "thumbnail_url": f"/api/media/{session_id}/{poster_name}",
                    "poster_url": f"/api/media/{session_id}/{poster_name}",
                    "transcript_text": f"Live highlight: {clip['title']}",
                    "words": [],
                    "aspect_ratio": "9:16",
                    "framing": "blur_fit",
                    "caption_style": "pop",
                    "hook_text": meta["title"],
                    "provider": "local_live_harvest",
                })

            session_data = {
                "id": session_id,
                "title": f"Live Harvest: {self.url.split('/')[-1]}",
                "duration": round(time.time() - self.start_time, 2),
                "uploader": self.streamer_id,
                "source": self.url,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "clips": session_clips,
            }

            session_json_path = session_dir / "session.json"
            session_json_path.write_text(json.dumps(session_data, indent=2), encoding="utf-8")

            state = load_state()
            state.setdefault("sessions", []).insert(0, {
                "id": session_id,
                "title": session_data["title"],
                "source": self.url,
                "created_at": session_data["created_at"],
                "clips_count": len(session_clips),
            })
            save_state(state)
        except Exception as e:
            pass


def start_watching(streamer_id: str) -> bool:
    """Start watcher for a streamer."""
    if streamer_id in _ACTIVE_WATCHERS:
        return True

    state = load_state()
    streamer = next((s for s in state.get("streamers", []) if s["id"] == streamer_id), None)
    if not streamer:
        return False

    watcher = LiveWatcher(streamer_id, streamer["url"], streamer["platform"])
    _ACTIVE_WATCHERS[streamer_id] = watcher
    watcher.start()
    update_streamer(streamer_id, {"is_live": True})
    return True


def stop_watching(streamer_id: str) -> bool:
    """Stop watcher for a streamer."""
    watcher = _ACTIVE_WATCHERS.pop(streamer_id, None)
    if watcher:
        watcher.stop()
    update_streamer(streamer_id, {"is_live": False})
    return True


def simulate_live_spike(
    source_video: Path,
    streamer_id: str,
    spike_rate: int = 150,
) -> Dict[str, Any]:
    """
    Simulation helper for unit testing Stage 6:
    Simulates a live streamer experiencing a chat spike and cutting a clip.
    """
    watcher = LiveWatcher(streamer_id, f"sim://{streamer_id}", "simulated")
    out_dir = DATA_BUFFER_DIR / streamer_id
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_file = out_dir / "seg_000.mp4"

    shutil.copy2(source_video, seg_file)
    watcher.on_spike_detected(spike_rate)
    clips = watcher.clips_taken
    return {
        "streamer_id": streamer_id,
        "clips": clips,
        "clip_count": len(clips),
    }
