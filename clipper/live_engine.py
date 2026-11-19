"""
Live streaming engine for Clipping Final Boss: rolling buffer recording,
multi-platform chat monitoring, real-time loudness analysis, and dynamic spike detection.

Portions adapted from PeakCut (https://github.com/haziqahmedqasmi/PeakCut):
MIT License - Copyright (c) 2024 Haziq Ahmed Qasmi
- 6-second MPEG-TS buffer segmenting with CSV index tracking
- Real-time s16le audio PCM pipe for loudness RMS calculation
- Anonymous Twitch IRC TLS socket listener (justinfan)
"""

import collections
import json
import logging
import math
import os
import re
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from .config import DATA_BUFFER_DIR, DATA_OUT_DIR, find_ffmpeg, find_ffprobe, settings
from .cutter import cut_clip
from .state import update_streamer, load_state, save_state

logger = logging.getLogger("clipper.live")

SEG_SEC = 6               # 6-second segment chunks
SAMPLE_RATE = 16000       # 16kHz audio sampling for loudness & whisper
AUTO_BEFORE = 20          # 20s pre-roll before spike
AUTO_AFTER = 10           # 10s post-roll after spike
PAD = 4                   # 4s extra padding for editor re-trimming
AUTO_GAP = 60             # 60s minimum cooldown between auto-clips
MERGE_WINDOW = 15         # Merge spikes within 15s into one clip
DEFAULT_BUFFER_MIN = 10   # 10 minutes rolling buffer retention
MAX_DISK_MB = 2048        # 2 GB buffer cap per streamer

_NICK_REGEX = re.compile(r"(?m)^:([A-Za-z0-9_]{2,25})!")
_CLIP_TRIGGER_WORDS = re.compile(r"\bclip(\s+(it|that|this))?\b", re.I)


class StreamBufferRecorder:
    """
    Records a live stream into 6-second MPEG-TS segments with CSV tracking,
    while streaming raw 16kHz mono audio over an stdout pipe for sub-second
    loudness monitoring and speech detection.
    """

    def __init__(
        self,
        streamer_id: str,
        stream_url: str,
        platform: str,
        buffer_minutes: int = DEFAULT_BUFFER_MIN,
        disk_cap_mb: int = MAX_DISK_MB,
    ):
        self.streamer_id = streamer_id
        self.stream_url = stream_url
        self.platform = platform
        self.buffer_minutes = buffer_minutes
        self.disk_cap_mb = disk_cap_mb

        self.buf_dir = DATA_BUFFER_DIR / streamer_id
        self.buf_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir = self.buf_dir / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)

        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.is_recording = False
        self.ended = False

        self.proc: Optional[subprocess.Popen] = None
        self.part = 0
        self.seg_clock = 0.0
        self.csv_seen: Dict[int, int] = {}
        self.segments: List[Tuple[Path, float, float]] = []  # (path, start_sec, end_sec)

        # Audio loudness & speech
        self.db_history: List[float] = []       # RMS dB per second
        self.samples_received = 0
        self.pending_audio = bytearray()
        self.words: List[Dict[str, Any]] = []

        # Diagnostics & health
        self.signal_health = {
            "chat": "connecting",
            "audio": "waiting",
            "buffer": "empty",
            "buffer_sec": 0,
            "buffer_mb": 0.0,
        }

    def start(self, live_media_url: str) -> None:
        """Starts ffmpeg recording process and reader thread."""
        self.is_recording = True
        self.part += 1
        p_prefix = f"p{self.part:02d}"

        ffmpeg = find_ffmpeg()
        cmd = [
            ffmpeg,
            "-v", "error",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-i", live_media_url,
            # Output 1: 6-second video segments
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(SEG_SEC),
            "-reset_timestamps", "1",
            "-segment_format", "mpegts",
            "-segment_list", f"{p_prefix}.csv",
            "-segment_list_type", "csv",
            f"{p_prefix}_%05d.ts",
            # Output 2: 16kHz mono audio pipe for real-time loudness & speech
            "-map", "0:a:0",
            "-vn",
            "-ac", "1",
            "-ar", str(SAMPLE_RATE),
            "-f", "s16le",
            "pipe:1",
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(self.buf_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.signal_health["buffer"] = "recording"
            threading.Thread(target=self._read_audio_pipe, daemon=True, name=f"audio_pipe_{self.streamer_id}").start()
            threading.Thread(target=self._segment_manager_loop, daemon=True, name=f"seg_mgr_{self.streamer_id}").start()
        except Exception as e:
            logger.error(f"Failed to start ffmpeg buffer process: {e}")
            self.signal_health["buffer"] = f"error: {str(e)[:40]}"
            self.is_recording = False

    def _read_audio_pipe(self) -> None:
        """Reads 1-second chunks of 16-bit mono PCM from ffmpeg stdout."""
        bytes_per_sec = SAMPLE_RATE * 2
        while not self.stop_event.is_set() and self.proc and self.proc.poll() is None:
            try:
                chunk = self.proc.stdout.read(bytes_per_sec)
                if not chunk:
                    break
                data = chunk[: (len(chunk) // 2) * 2]
                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                level = float(20 * np.log10(np.sqrt((arr ** 2).mean() + 1e-10))) if len(arr) else -100.0

                with self.lock:
                    self.db_history.append(level)
                    self.samples_received += len(data) // 2
                    self.pending_audio += data

                self.signal_health["audio"] = f"active ({round(level, 1)} dB)"
            except Exception as e:
                logger.warning(f"Audio pipe read error: {e}")
                break

        self.signal_health["audio"] = "stopped"

    def _segment_manager_loop(self) -> None:
        """Periodically scans for new segments and prunes expired ones according to retention rules."""
        while not self.stop_event.is_set():
            self._scan_and_prune()
            time.sleep(2.0)

    def _scan_and_prune(self) -> None:
        with self.lock:
            # 1. Parse CSV index files written by ffmpeg
            for i in range(1, self.part + 1):
                csv_path = self.buf_dir / f"p{i:02d}.csv"
                if not csv_path.exists():
                    continue
                try:
                    lines = [r.split(",") for r in csv_path.read_text(encoding="utf-8", errors="ignore").splitlines() if r.count(",") >= 2]
                    start_idx = self.csv_seen.get(i, 0)
                    for row in lines[start_idx:]:
                        name = row[0].strip()
                        try:
                            a, b = float(row[1]), float(row[2])
                            dur = max(0.0, b - a)
                        except ValueError:
                            dur = float(SEG_SEC)

                        seg_file = self.buf_dir / name
                        self.segments.append((seg_file, self.seg_clock, self.seg_clock + dur))
                        self.seg_clock += dur

                    self.csv_seen[i] = len(lines)
                except Exception as e:
                    logger.debug(f"CSV read notice: {e}")

            # 2. Prune segments older than buffer_minutes
            keep_from = self.seg_clock - (self.buffer_minutes * 60)
            while self.segments and self.segments[0][2] < keep_from:
                old_seg = self.segments.pop(0)
                try:
                    old_seg[0].unlink(missing_ok=True)
                except Exception:
                    pass

            # 3. Enforce disk cap
            total_bytes = sum(f.stat().st_size for f in self.buf_dir.glob("*.ts") if f.exists())
            mb = total_bytes / (1024 * 1024)
            while mb > self.disk_cap_mb and len(self.segments) > 2:
                old_seg = self.segments.pop(0)
                try:
                    old_seg[0].unlink(missing_ok=True)
                except Exception:
                    pass
                total_bytes = sum(f.stat().st_size for f in self.buf_dir.glob("*.ts") if f.exists())
                mb = total_bytes / (1024 * 1024)

            # Update health metrics
            buf_dur = (self.segments[-1][2] - self.segments[0][1]) if self.segments else 0
            self.signal_health["buffer_sec"] = int(buf_dur)
            self.signal_health["buffer_mb"] = round(mb, 1)

    def cut_buffer_clip(self, center_time: float, pre_roll: float = AUTO_BEFORE, post_roll: float = AUTO_AFTER, out_path: Optional[Path] = None) -> Optional[Path]:
        """
        Concatenates matching .ts segments covering [center_time - pre_roll, center_time + post_roll]
        and creates an MP4 clip.
        """
        clip_start = max(0.0, center_time - pre_roll)
        clip_end = center_time + post_roll

        # Ensure segments are freshly scanned
        self._scan_and_prune()

        with self.lock:
            needed = [
                s for s in self.segments
                if s[2] > (clip_start - PAD) and s[1] < (clip_end + PAD) and s[0].exists()
            ]

        if not needed:
            logger.warning(f"No buffer segments found for clip window [{clip_start}, {clip_end}]")
            return None

        ffmpeg = find_ffmpeg()
        concat_list = self.clips_dir / f"concat_{int(time.time() * 1000)}.txt"
        temp_ts = self.clips_dir / f"temp_{int(time.time() * 1000)}.ts"
        if out_path is None:
            out_path = self.clips_dir / f"clip_{int(time.time())}.mp4"

        try:
            # Write ffmpeg concat file
            with open(concat_list, "w", encoding="utf-8") as f:
                for seg in needed:
                    f.write(f"file '{seg[0].resolve().as_posix()}'\n")

            # Concat without re-encoding
            cmd_concat = [
                ffmpeg, "-y", "-v", "error",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(temp_ts)
            ]
            subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Calculate slice bounds within concatenated stream
            stream_start = needed[0][1]
            ss = max(0.0, clip_start - stream_start)
            dur = max(2.0, clip_end - clip_start)

            # Trim to exact mp4
            cmd_trim = [
                ffmpeg, "-y", "-v", "error",
                "-ss", f"{ss:.2f}",
                "-i", str(temp_ts),
                "-t", f"{dur:.2f}",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-avoid_negative_ts", "make_zero",
                str(out_path)
            ]
            subprocess.run(cmd_trim, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if out_path.exists() and out_path.stat().st_size > 1000:
                return out_path
            return None
        except Exception as e:
            logger.error(f"Error cutting buffer clip: {e}")
            return None
        finally:
            concat_list.unlink(missing_ok=True)
            temp_ts.unlink(missing_ok=True)

    def stop(self) -> None:
        """Terminates ffmpeg process and signals background threads to exit."""
        self.stop_event.set()
        self.is_recording = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

    def cleanup_buffer(self) -> None:
        """Cleans up raw buffer .ts files when stream concludes to free disk space."""
        try:
            for f in self.buf_dir.glob("*.ts"):
                f.unlink(missing_ok=True)
            for f in self.buf_dir.glob("*.csv"):
                f.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Buffer cleanup notice: {e}")


class TwitchAnonymousChatListener:
    """
    Connects to Twitch IRC anonymously via TLS on irc.chat.twitch.tv:6697
    using NICK justinfan<rand> and JOIN #<channel>. Zero credentials needed.
    """

    def __init__(self, channel: str):
        self.channel = channel.lower().lstrip("@")
        self.stop_event = threading.Event()
        self.chat_rates = collections.Counter()  # second -> msg count
        self.chat_users = {}                     # second -> set of users
        self.total_msgs = 0
        self.is_connected = False
        self.status = "disconnected"

    def start(self) -> None:
        threading.Thread(target=self._run_loop, daemon=True, name=f"twitch_chat_{self.channel}").start()

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                raw_sock = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=15)
                ssl_sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname="irc.chat.twitch.tv")
                nick = f"justinfan{int(time.time()) % 90000 + 10000}"
                ssl_sock.sendall(f"NICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
                ssl_sock.settimeout(25.0)

                self.is_connected = True
                self.status = "connected"
                rest = b""

                while not self.stop_event.is_set():
                    try:
                        data = ssl_sock.recv(8192)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    *lines, rest = (rest + data).split(b"\r\n")
                    for line in lines:
                        if line.startswith(b"PING"):
                            ssl_sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                        elif b" PRIVMSG #" in line:
                            sec = int(time.time())
                            self.chat_rates[sec] += 1
                            self.total_msgs += 1
                            who = _NICK_REGEX.findall(line.decode("utf-8", "replace"))
                            if who:
                                self.chat_users.setdefault(sec, set()).add(who[0].lower())

                ssl_sock.close()
            except Exception as e:
                logger.debug(f"Twitch IRC reconnect notice: {e}")
            finally:
                self.is_connected = False
                self.status = "audio-only fallback"
                self.stop_event.wait(5.0)

    def stop(self) -> None:
        self.stop_event.set()
        self.is_connected = False


class RollingBaselineSpikeDetector:
    """
    Evaluates loudness, chat density, and speech signals against a dynamic rolling
    baseline (mean + k*std) over the last 3 minutes instead of static thresholds.
    """

    def __init__(
        self,
        baseline_seconds: int = 180,
        jump_threshold: float = 0.60,
        cooldown_seconds: int = AUTO_GAP,
    ):
        self.baseline_seconds = baseline_seconds
        self.jump_threshold = jump_threshold
        self.cooldown_seconds = cooldown_seconds

        self.last_spike_time = -999.0
        self.spikes: List[Dict[str, Any]] = []

    def evaluate(
        self,
        db_history: List[float],
        chat_counts: List[int],
        chat_active: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculates rolling baseline and checks if current activity triggers a spike.
        Returns a spike info dict if triggered, or None.
        """
        now = time.time()
        if now - self.last_spike_time < self.cooldown_seconds:
            return None

        n = len(db_history)
        if n < 45:  # Need at least 45 seconds to establish warming baseline
            return None

        # 1. Loudness Baseline & Spike Evaluation
        recent_db = np.array(db_history[max(0, n - self.baseline_seconds):], dtype=np.float32)
        amp = 10.0 ** (recent_db / 20.0)

        # Baseline is prior minutes excluding last 8 seconds
        base_amp = float(amp[:-8].mean()) if len(amp) > 12 else 0.01
        cur_amp = float(amp[-5:].mean()) if len(amp) >= 5 else 0.01

        loud_jump = (cur_amp / max(base_amp, 1e-6)) - 1.0
        loud_score = min(100.0, max(0.0, (loud_jump / self.jump_threshold) * 75.0))

        # 2. Chat Baseline & Spike Evaluation
        chat_jump = 0.0
        chat_score = 0.0
        chat_now_rate = 0.0
        if chat_active and chat_counts:
            c_arr = chat_counts[max(0, len(chat_counts) - self.baseline_seconds):]
            if len(c_arr) > 12:
                base_chat = float(np.mean(c_arr[:-8]))
                cur_chat = float(np.mean(c_arr[-5:]))
                chat_now_rate = cur_chat
                chat_jump = (cur_chat / max(base_chat, 0.5)) - 1.0
                chat_score = min(100.0, max(0.0, (chat_jump / self.jump_threshold) * 75.0))

        # 3. Decision Logic
        is_spike = False
        reasons = []

        if loud_jump >= self.jump_threshold:
            is_spike = True
            reasons.append(f"Loudness +{int(loud_jump * 100)}%")

        if chat_active and chat_jump >= self.jump_threshold and chat_now_rate >= 2.0:
            is_spike = True
            reasons.append(f"Chat +{int(chat_jump * 100)}%")

        if is_spike:
            self.last_spike_time = now
            spike_data = {
                "timestamp": now,
                "reasons": ", ".join(reasons),
                "loud_score": round(loud_score, 1),
                "chat_score": round(chat_score, 1),
                "combined_score": round(0.5 * loud_score + 0.5 * chat_score if chat_active else loud_score, 1),
            }
            self.spikes.append(spike_data)
            return spike_data

        return None
