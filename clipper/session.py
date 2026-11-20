"""Session orchestration: manages pipeline sessions in data/out/session_N/."""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from .config import DATA_OUT_DIR, DATA_IN_DIR
from .downloader import download_or_load
from .transcriber import transcribe
from .candidate_picker import find_candidate_moments
from .cutter import cut_clip
from .ranker import rank_and_rename_clips
from .renderer import render_clip
from .ai import generate_clip_metadata
from .thumbnail import create_thumbnail, extract_poster_frame
from .games import detect as detect_game

def get_next_session_dir() -> Path:
    """Finds next available session directory e.g. data/out/session_1."""
    DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx = 1
    while (DATA_OUT_DIR / f"session_{idx}").exists():
        idx += 1
    s_dir = DATA_OUT_DIR / f"session_{idx}"
    s_dir.mkdir(parents=True, exist_ok=True)
    return s_dir

def save_session_data(session_dir: Path, data: Dict[str, Any]) -> None:
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_session_data(session_dir: Path) -> Optional[Dict[str, Any]]:
    session_file = session_dir / "session.json"
    if not session_file.exists():
        return None
    try:
        return json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        return None

def process_video_pipeline(
    source: str,
    top_n: int = 5,
    min_len: Optional[float] = None,
    max_len: Optional[float] = None,
    length_range: Optional[str] = None,
    chat_events: Optional[List[Dict[str, Any]]] = None,
    progress_callback: Optional[Any] = None,
    preset: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes full pipeline:
    1. Download or load media
    2. Transcribe with word timestamps
    3. Find candidate moments respecting length constraints
    4. Cut candidate clips
    5. Generate unique AI metadata (title, caption, hashtags)
    6. Rank and rename clips (01_*.mp4)
    7. Generate poster frames & thumbnails
    """
    session_dir = get_next_session_dir()
    session_id = session_dir.name

    # Determine default length constraints
    if min_len is None or max_len is None:
        min_len = 20.0
        max_len = 90.0
        if not length_range:
            length_range = "Auto (< 90s)"
    elif not length_range:
        length_range = f"{int(min_len)}-{int(max_len)}s"

    def report_progress(stage: str, percent: int, msg: str):
        if progress_callback:
            try:
                # Primary consistent signature: def on_progress(pct: float, msg: str = "", **kw)
                progress_callback(float(percent), msg=msg, stage=stage)
            except TypeError:
                try:
                    progress_callback(stage, percent, msg)
                except TypeError:
                    try:
                        progress_callback(msg, percent)
                    except Exception:
                        pass
            except Exception:
                pass

    report_progress("download", 10, "Downloading or loading video source...")

    # 1. Download/Load
    media = download_or_load(source, session_id)
    source_video = media["file_path"]
    duration = media["duration"]

    # Detect game if present and set preset
    detected_game, _ = detect_game(media.get("title", ""), source)
    if preset is None and detected_game:
        preset = "gta6" if detected_game == "Grand Theft Auto VI" else "gaming"

    report_progress("transcribe", 25, "Transcribing audio locally with faster-whisper...")

    # 2. Transcribe
    transcript = transcribe(source_video)

    report_progress("moments", 50, "Detecting hooks, loudness, and chat spikes...")

    # 3. Find Candidate Moments
    candidates = find_candidate_moments(
        video_path=source_video,
        duration=duration,
        transcript=transcript,
        chat_events=chat_events,
        target_count=top_n,
        min_clip_len=min_len,
        max_clip_len=max_len,
        preset=preset,
    )

    report_progress("rank", 70, "Cutting candidate clips with FFmpeg...")

    # 4. Cut raw clips
    raw_clips = []
    used_titles = set()
    total_cands = max(1, len(candidates))
    for idx, cand in enumerate(candidates, start=1):
        temp_name = f"raw_cand_{idx}.mp4"
        out_path = session_dir / temp_name
        cut_pct = 70 + int((idx / total_cands) * 12)
        report_progress("rank", cut_pct, f"Cutting clip #{idx} of {total_cands} and generating viral metadata...")
        success = cut_clip(source_video, out_path, cand.start, cand.end)
        if success:
            # Generate unique AI metadata (with safe timeout and fallback)
            meta = generate_clip_metadata(cand.transcript_text, idx, used_titles=used_titles, game=detected_game)
            raw_clips.append({
                "id": f"clip_{idx}",
                "file_path": str(out_path),
                "start": cand.start,
                "end": cand.end,
                "duration": round(cand.duration, 2),
                "length_range": length_range,
                "hook_score": cand.hook_score,
                "chat_score": cand.chat_score,
                "emotion_score": cand.emotion_score,
                "story_score": cand.story_score,
                "trend_score": cand.trend_score,
                "loudness_score": cand.loudness_score,
                "title": meta["title"],
                "caption": meta["caption"],
                "hashtags": meta["hashtags"],
                "transcript_text": cand.transcript_text,
                "words": cand.words,
                "aspect": "9:16",
                "framing": "blur_fit",
                "trim_start": 0.0,
                "trim_end": round(cand.duration, 2),
                "captions_on": True,
                "caption_style": "pop",
                "hook_text": meta["title"],
            })

    report_progress("rank", 84, "Scoring and ranking clips...")

    # 5. Rank and rename
    has_chat = bool(chat_events and len(chat_events) > 0)
    ranked_clips = rank_and_rename_clips(raw_clips, session_dir, has_chat=has_chat)

    report_progress("render", 88, "Generating 9:16 poster frames and thumbnails...")

    # 6. Render preview thumbnails and poster frames
    total_ranked = max(1, len(ranked_clips))
    for r_idx, clip in enumerate(ranked_clips, start=1):
        thumb_pct = 88 + int((r_idx / total_ranked) * 10)
        report_progress("render", thumb_pct, f"Rendering poster frame for clip #{clip['rank']}...")
        stem = Path(clip["file_path"]).stem
        poster_name = f"{stem}_poster.jpg"
        poster_path = session_dir / poster_name
        # Extract clean 9:16 vertical poster frame from middle of clip
        extract_poster_frame(video_path=Path(clip["file_path"]), output_path=poster_path)

        # Standard thumbnail overlay as backup
        thumb_name = f"{stem}_thumb.jpg"
        thumb_path = session_dir / thumb_name
        create_thumbnail(
            video_path=Path(clip["file_path"]),
            title=clip["title"],
            output_path=thumb_path,
            aspect_ratio="9:16",
            use_ai_image=False,
        )

        clip["poster_url"] = f"/api/media/{session_id}/{poster_name}"
        clip["thumbnail_url"] = f"/api/media/{session_id}/{poster_name}" if poster_path.exists() else f"/api/media/{session_id}/{thumb_name}"
        clip["video_url"] = f"/api/media/{session_id}/{clip['filename']}"

    report_progress("complete", 100, "Complete! Ranked short clips ready.")

    session_data = {
        "id": session_id,
        "title": media["title"],
        "duration": duration,
        "uploader": media["uploader"],
        "source": source,
        "length_range": length_range,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "has_chat": has_chat,
        "clips": ranked_clips,
    }

    save_session_data(session_dir, session_data)

    if progress_callback:
        report_progress("complete", 100, "Complete! Ranked short clips ready.")

    return session_data
