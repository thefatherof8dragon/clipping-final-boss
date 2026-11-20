"""FastAPI web server and REST API for Clipper."""

import os
import json
import socket
import logging
import threading
import time
import traceback
import shutil
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DATA_DIR, DATA_OUT_DIR, settings
from .session import (
    process_video_pipeline,
    load_session_data,
    save_session_data,
)
from .renderer import render_clip
from .ai import generate_clip_metadata, generate_hook_alternatives
from .thumbnail import create_thumbnail
from .caption_styles import list_caption_styles, get_caption_style
from .state import (
    get_pinned_streamers,
    add_streamer,
    update_streamer,
    remove_streamer,
    load_state,
)
from .streamers import (
    start_watching,
    stop_watching,
    check_channel_live,
    detect_platform,
    resolve_handle_and_platform,
    fetch_streamer_metadata,
)
from .youtube import schedule_upload, is_authenticated, connect_youtube_oauth, get_channel_info
from .jobs import job_manager

logger = logging.getLogger("clipper.api")

app = FastAPI(
    title="Clipping Final Boss",
    description="Local open-source clipping tool for long videos and live streams",
    version="1.0.0",
)

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)

# Static files directory
STATIC_DIR = Path(__file__).parent / "web" / "static"

# Request Models
class ClipRequest(BaseModel):
    url: str
    top_n: int = Field(default=5, ge=1, le=20)
    min_len: Optional[float] = None
    max_len: Optional[float] = None
    length_chip: Optional[str] = "auto"
    async_mode: Optional[bool] = False

class ClipUpdateRequest(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    aspect: Optional[str] = None
    framing: Optional[str] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    captions_on: Optional[bool] = None
    caption_style: Optional[str] = None
    hook_text: Optional[str] = None
    words: Optional[List[Dict[str, Any]]] = None

class RenderRequest(BaseModel):
    aspect: Optional[str] = None
    framing: Optional[str] = None
    custom_style: Optional[Dict[str, Any]] = None
    hook: Optional[Dict[str, Any]] = None

class StreamerRequest(BaseModel):
    name: Optional[str] = ""
    url: str
    platform: Optional[str] = "auto"

class SettingsUpdateRequest(BaseModel):
    llm_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_url: Optional[str] = None
    transcription_option: Optional[str] = None
    whisper_model: Optional[str] = None
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None
    record_height: Optional[int] = None
    spike_min_msgs: Optional[int] = None
    auto_upload: Optional[bool] = None
    daily_upload_cap: Optional[int] = None
    data_dir: Optional[str] = None

class TestKeyRequest(BaseModel):
    provider: str
    key: Optional[str] = ""
    url: Optional[str] = ""

class TestAndSaveRequest(BaseModel):
    provider: str
    key: Optional[str] = ""
    url: Optional[str] = ""
    model: Optional[str] = None

class YouTubeConnectRequest(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class ScheduleRequest(BaseModel):
    publish_at: Optional[str] = None
    dry_run: Optional[bool] = None

def parse_clip_composite_id(clip_id: str) -> tuple[Path, str]:
    """Parse composite clip id e.g. session_1_clip_1 or session_1:clip_1."""
    if ":" in clip_id:
        sess_name, c_id = clip_id.split(":", 1)
    elif "_clip_" in clip_id:
        parts = clip_id.split("_clip_")
        sess_name = parts[0]
        c_id = f"clip_{parts[1]}"
    else:
        for s_dir in DATA_OUT_DIR.glob("session_*"):
            s_data = load_session_data(s_dir)
            if s_data:
                for c in s_data.get("clips", []):
                    if c["id"] == clip_id:
                        return s_dir, clip_id
        raise HTTPException(status_code=404, detail="Clip not found in any session")

    s_dir = DATA_OUT_DIR / sess_name
    if not s_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session {sess_name} not found")
    return s_dir, c_id

def _run_pipeline_worker(job_id: str, req_data: Dict[str, Any]) -> None:
    job = job_manager.get_job(job_id)
    if not job:
        return

    def on_progress(pct: float, msg: str = "", **kw) -> None:
        stage = kw.get("stage")
        # Handle cases where pct might be a string (legacy stage name or msg)
        if isinstance(pct, str):
            if isinstance(msg, (int, float)):
                pct, msg = float(msg), pct
            else:
                stage = pct
                pct = 0.0
        pct_float = float(pct) if isinstance(pct, (int, float)) else 0.0
        pct_int = max(0, min(100, int(round(pct_float))))

        if not stage:
            if pct_int < 20:
                stage = "download"
            elif pct_int < 45:
                stage = "transcribe"
            elif pct_int < 65:
                stage = "moments"
            elif pct_int < 85:
                stage = "rank"
            elif pct_int < 100:
                stage = "render"
            else:
                stage = "complete"

        job.update(stage, pct_int, str(msg))

    try:
        min_l = req_data.get("min_len")
        max_l = req_data.get("max_len")
        label = None
        chip = (req_data.get("length_chip") or "auto").lower()

        if "under_30" in chip or "< 30" in chip or "<30" in chip:
            min_l = min_l or 15.0
            max_l = max_l or 30.0
            label = "Under 30s"
        elif "30_60" in chip or "30 to 60" in chip:
            min_l = min_l or 30.0
            max_l = max_l or 60.0
            label = "30 to 60s"
        elif "60_90" in chip or "60 to 90" in chip:
            min_l = min_l or 60.0
            max_l = max_l or 90.0
            label = "60 to 90s"
        elif "over_90" in chip or "over 90" in chip or "> 90" in chip:
            min_l = min_l or 90.0
            max_l = max_l or 180.0
            label = "Over 90s"
        else:
            min_l = min_l or 20.0
            max_l = max_l or 90.0
            label = "Auto (< 90s)"

        session = process_video_pipeline(
            source=req_data["url"].strip(),
            top_n=req_data.get("top_n", 5),
            min_len=min_l,
            max_len=max_l,
            length_range=label,
            progress_callback=on_progress,
        )
        job.complete(session)
    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"[Job {job_id}] Pipeline failed at stage '{job.stage}': {e}\n{tb_str}")
        try:
            log_dir = Path("data")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "pipeline.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Job {job_id}] [Stage: {job.stage}] ERROR: {str(e)}\n{tb_str}\n")
        except Exception as log_err:
            logger.error(f"Failed writing to pipeline.log: {log_err}")

        job.fail(str(e))

# ==================== PIPELINE & JOBS ====================
@app.post("/api/clip")
def api_create_clips(req: ClipRequest, async_mode: Optional[bool] = Query(default=None)):
    """Processes video link or local file and generates ranked clips."""
    url_clean = req.url.strip()
    url_lower = url_clean.lower()
    if any(loopback in url_lower for loopback in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
        raise HTTPException(
            status_code=400,
            detail="Cannot clip from local server address (localhost / 127.0.0.1). Provide a public video URL or local video file path.",
        )

    should_async = req.async_mode if req.async_mode is not None else (async_mode is True)

    if should_async:
        job = job_manager.create_job("clip_generation", {"url": req.url, "top_n": req.top_n})
        req_data = req.model_dump()
        t = threading.Thread(target=_run_pipeline_worker, args=(job.id, req_data), daemon=True)
        t.start()
        return {
            "job_id": job.id,
            "status": "pending",
            "stage": "queued",
            "progress": 0,
            "message": "Clip processing started in background...",
        }

    try:
        min_l = req.min_len
        max_l = req.max_len
        label = None
        chip = (req.length_chip or "auto").lower()

        if "under_30" in chip or "< 30" in chip or "<30" in chip:
            min_l = min_l or 15.0
            max_l = max_l or 30.0
            label = "Under 30s"
        elif "30_60" in chip or "30 to 60" in chip:
            min_l = min_l or 30.0
            max_l = max_l or 60.0
            label = "30 to 60s"
        elif "60_90" in chip or "60 to 90" in chip:
            min_l = min_l or 60.0
            max_l = max_l or 90.0
            label = "60 to 90s"
        elif "over_90" in chip or "over 90" in chip or "> 90" in chip:
            min_l = min_l or 90.0
            max_l = max_l or 180.0
            label = "Over 90s"
        else:
            min_l = min_l or 20.0
            max_l = max_l or 90.0
            label = "Auto (< 90s)"

        session = process_video_pipeline(
            source=req.url.strip(),
            top_n=req.top_n,
            min_len=min_l,
            max_len=max_l,
            length_range=label,
        )
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    """Retrieve the status and real-time stage progress of a background job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

@app.get("/api/templates")
@app.get("/api/caption-styles")
def api_get_caption_styles():
    """Return all 10 visual caption templates."""
    return list_caption_styles()

def startup_cleanup_stale_demo_data() -> None:
    """Purges stale demo/synthetic test sessions and orphaned directories from data/out."""
    if not DATA_OUT_DIR.exists():
        return
    for s_dir in list(DATA_OUT_DIR.glob("session_*")):
        if not s_dir.is_dir():
            continue
        s_data = load_session_data(s_dir)
        is_stale = False
        if not s_data:
            is_stale = True
        else:
            title = str(s_data.get("title", "")).lower()
            source = str(s_data.get("source", "")).lower()
            if "synthetic" in title or "synthetic" in source or "pytest" in source or "\\temp\\" in source or "/temp/" in source:
                is_stale = True
            elif not s_data.get("clips"):
                is_stale = True
        if is_stale:
            try:
                shutil.rmtree(s_dir, ignore_errors=True)
                logger.info(f"[Startup Migration] Removed stale demo session: {s_dir.name}")
            except Exception as e:
                logger.warning(f"Could not remove stale session {s_dir.name}: {e}")

# Run startup cleanup immediately
try:
    startup_cleanup_stale_demo_data()
except Exception as _e:
    logger.warning(f"Startup demo cleanup notice: {_e}")

@app.get("/api/sessions")
def api_list_sessions():
    """List all past clipping sessions, excluding stale test/demo data."""
    sessions = []
    if DATA_OUT_DIR.exists():
        for s_dir in sorted(DATA_OUT_DIR.glob("session_*"), key=lambda p: p.stat().st_mtime, reverse=True):
            s_data = load_session_data(s_dir)
            if s_data and s_data.get("clips"):
                title = str(s_data.get("title", "")).lower()
                source = str(s_data.get("source", "")).lower()
                if "synthetic" in title or "synthetic" in source or "pytest" in source:
                    continue
                sessions.append({
                    "id": s_data.get("id", s_dir.name),
                    "title": s_data.get("title", s_dir.name),
                    "created_at": s_data.get("created_at", ""),
                    "clip_count": len(s_data.get("clips", [])),
                })
    return sessions

@app.get("/api/sessions/{session_id}/clips")
def api_get_session_clips(session_id: str):
    """Returns ranked clips for given session."""
    s_dir = DATA_OUT_DIR / session_id
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return s_data

@app.patch("/api/clips/{clip_id}")
def api_update_clip(clip_id: str, updates: ClipUpdateRequest):
    """Update title, caption, aspect ratio, trim, words timing of a clip."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found or session.json missing")
    target_clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not target_clip:
        raise HTTPException(status_code=404, detail="Clip not found in session")

    dumped = updates.model_dump(exclude_unset=True)
    for k, v in dumped.items():
        target_clip[k] = v

    save_session_data(s_dir, s_data)
    return target_clip

@app.post("/api/clips/{clip_id}/render")
def api_render_clip(clip_id: str, req: Optional[RenderRequest] = None):
    """Renders the clip with chosen settings and caption styles."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found or session.json missing")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    input_path = Path(clip["file_path"])
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Source clip file missing on disk")

    if req:
        if req.aspect:
            clip["aspect"] = req.aspect
        if req.framing:
            clip["framing"] = req.framing
        if req.hook and isinstance(req.hook, dict):
            clip["hook_text"] = req.hook.get("text")

    rendered_name = f"rendered_{input_path.stem}_{clip.get('aspect', '9-16').replace(':', '-')}.mp4"
    rendered_path = s_dir / rendered_name

    custom_style = req.custom_style if req and req.custom_style else clip.get("custom_style")

    success = render_clip(
        input_video=input_path,
        output_video=rendered_path,
        aspect_ratio=clip.get("aspect", "9:16"),
        framing=clip.get("framing", "blur_fit"),
        words=clip.get("words", []),
        caption_style=clip.get("caption_style", "pop"),
        captions_on=clip.get("captions_on", True),
        hook_text=clip.get("hook_text") or clip.get("title"),
        trim_start=float(clip.get("trim_start", 0.0)),
        trim_end=float(clip.get("trim_end", clip.get("duration", 30.0))),
        custom_style=custom_style,
    )

    if not success:
        raise HTTPException(status_code=500, detail="FFmpeg rendering failed")

    clip["rendered_path"] = str(rendered_path)
    clip["rendered_filename"] = rendered_name
    clip["rendered_url"] = f"/api/media/{s_dir.name}/{rendered_name}"
    save_session_data(s_dir, s_data)

    return {
        "success": True,
        "rendered_url": clip["rendered_url"],
        "rendered_path": str(rendered_path),
        "clip": clip,
    }

@app.post("/api/clips/{clip_id}/transcribe")
def api_transcribe_clip(clip_id: str):
    """Generates word-level timestamps for a clip on demand."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_file = s_dir / clip.get("file_name", f"{c_id}.mp4")
    if not clip_file.exists():
        source_f = DATA_IN_DIR / f"{s_dir.name}_source.mp4"
        if not source_f.exists():
            raise HTTPException(status_code=404, detail="Media file not found")
        clip_file = source_f

    from .transcriber import transcribe
    res = transcribe(clip_file)
    words = []
    for seg in res.get("segments", []):
        for w in seg.get("words", []):
            words.append(w)
    clip["words"] = words
    save_session_data(s_dir, s_data)
    return {"words": words, "language": res.get("language", "en")}

@app.post("/api/clips/{clip_id}/regenerate")
def api_regenerate_text(clip_id: str):
    """Regenerates title, caption, and hashtags using AI with local fallback."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found or session.json missing")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    meta = generate_clip_metadata(clip.get("transcript_text", ""), clip.get("rank", 1))
    clip["title"] = meta["title"]
    clip["caption"] = meta["caption"]
    clip["hashtags"] = meta["hashtags"]
    save_session_data(s_dir, s_data)
    return clip

@app.post("/api/clips/{clip_id}/hook-alternatives")
def api_get_hook_alternatives(clip_id: str):
    """Generate 3 viral hook overlay alternatives for the clip."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    alternatives = generate_hook_alternatives(
        clip.get("transcript_text", ""),
        clip.get("title", "Highlight Moment")
    )
    return {"alternatives": alternatives}

@app.post("/api/clips/{clip_id}/thumbnail")
def api_regenerate_thumbnail(clip_id: str):
    """Regenerates thumbnail for the clip."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found or session.json missing")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    thumb_name = f"{Path(clip['file_path']).stem}_thumb.jpg"
    thumb_path = s_dir / thumb_name
    success = create_thumbnail(
        video_path=Path(clip["file_path"]),
        title=clip.get("title", "Clip"),
        output_path=thumb_path,
        aspect_ratio=clip.get("aspect", "9:16"),
        use_ai_image=False,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Thumbnail creation failed")

    clip["thumbnail_url"] = f"/api/media/{s_dir.name}/{thumb_name}?t={int(os.path.getmtime(thumb_path))}"
    save_session_data(s_dir, s_data)
    return clip

@app.post("/api/clips/{clip_id}/schedule")
def api_schedule_clip(clip_id: str, req: ScheduleRequest):
    """Schedules clip to YouTube or runs dry-run simulation."""
    s_dir, c_id = parse_clip_composite_id(clip_id)
    s_data = load_session_data(s_dir)
    if not s_data:
        raise HTTPException(status_code=404, detail="Session not found or session.json missing")
    clip = next((c for c in s_data.get("clips", []) if c["id"] == c_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    target_video = Path(clip.get("rendered_path") or clip["file_path"])
    result = schedule_upload(
        video_path=target_video,
        title=clip.get("title", "Clipper Short"),
        description=clip.get("caption", "") + "\n\n" + " ".join(clip.get("hashtags", [])),
        tags=clip.get("hashtags", []),
        publish_at=req.publish_at,
        dry_run=req.dry_run if req.dry_run is not None else (not settings.auto_upload),
    )
    return result

# ==================== STREAMERS ====================
@app.get("/api/streamers")
def api_get_streamers():
    return get_pinned_streamers()

def _build_streamer_updates(live_res: Dict[str, Any]) -> Dict[str, Any]:
    now_ts = time.time()
    is_live = bool(live_res.get("is_live", False))
    title = live_res.get("title", "")
    viewers = int(live_res.get("viewers", 0))
    status_text = live_res.get("status", "Offline")
    reason = live_res.get("reason", "")
    return {
        "is_live": is_live,
        "title": title,
        "live_title": title,
        "stream_title": title,
        "viewers": viewers,
        "viewer_count": viewers,
        "status_text": status_text,
        "status_reason": reason,
        "last_error": reason if not is_live else "",
        "last_checked": now_ts,
        "last_checked_str": time.strftime("%H:%M:%S"),
    }

@app.post("/api/streamers")
def api_pin_streamer(req: StreamerRequest):
    canonical_url, platform = resolve_handle_and_platform(req.url, req.platform)
    meta = fetch_streamer_metadata(canonical_url, platform)
    display_name = (req.name or "").strip() or meta.get("name") or canonical_url.rstrip("/").split("/")[-1].lstrip("@")
    avatar_url = meta.get("avatar_url") or ""
    streamer = add_streamer(display_name, canonical_url, platform, avatar_url=avatar_url)
    # Check live status immediately upon pinning
    try:
        live_res = check_channel_live(streamer["url"], platform)
        updates = _build_streamer_updates(live_res)
        if meta.get("avatar_url"):
            updates["avatar_url"] = meta["avatar_url"]
        if meta.get("name") and not (req.name or "").strip():
            updates["name"] = meta["name"]
        update_streamer(streamer["id"], updates)
    except Exception as e:
        logger.warning(f"Initial streamer live check warning: {e}")
    state = load_state()
    return next((s for s in state.get("streamers", []) if s["id"] == streamer["id"]), streamer)

@app.delete("/api/streamers/{streamer_id}")
def api_remove_streamer(streamer_id: str):
    success = remove_streamer(streamer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Streamer not found")
    return {"success": True}

@app.get("/api/streamers/{streamer_id}/status")
def api_streamer_status(streamer_id: str):
    state = load_state()
    streamer = next((s for s in state.get("streamers", []) if s["id"] == streamer_id), None)
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    return streamer

@app.post("/api/streamers/{streamer_id}/check")
def api_check_streamer_live(streamer_id: str):
    """Trigger an immediate live status check for a pinned streamer."""
    state = load_state()
    streamer = next((s for s in state.get("streamers", []) if s["id"] == streamer_id), None)
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    live_res = check_channel_live(streamer["url"], streamer.get("platform"))
    updates = _build_streamer_updates(live_res)
    update_streamer(streamer_id, updates)
    return {**streamer, **updates}

@app.post("/api/streamers/check-all")
def api_check_all_streamers():
    """Trigger immediate live checks for all pinned streamers."""
    state = load_state()
    streamers = state.get("streamers", [])
    updated = []
    for s in streamers:
        live_res = check_channel_live(s["url"], s.get("platform"))
        updates = _build_streamer_updates(live_res)
        update_streamer(s["id"], updates)
        updated.append({**s, **updates})
    return updated

@app.post("/api/streamers/{streamer_id}/toggle-watch")
def api_toggle_watch(streamer_id: str):
    state = load_state()
    streamer = next((s for s in state.get("streamers", []) if s["id"] == streamer_id), None)
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    if streamer.get("is_live", False):
        stop_watching(streamer_id)
        return {"is_live": False}
    else:
        start_watching(streamer_id)
        return {"is_live": True}

# ==================== SETTINGS & KEY TESTING ====================
def mask_secret(secret: str) -> str:
    """Masks secret so it is never returned in plaintext to the UI."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"

@app.get("/api/settings")
def api_get_settings():
    d = settings.to_dict()
    d["youtube_authenticated"] = is_authenticated()
    d["youtube_channel_name"] = settings.youtube_channel_name

    # Data directory and free space
    d["data_dir"] = str(DATA_DIR)
    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        d["free_disk_space_gb"] = round(usage.free / (1024 ** 3), 2)
    except Exception:
        d["free_disk_space_gb"] = 0.0

    # No-key status indicator
    has_any_llm_key = bool(
        settings.gemini_api_key or settings.openai_api_key or
        settings.groq_api_key or settings.anthropic_api_key
    )
    d["no_key_mode"] = not has_any_llm_key
    d["ranking_mode"] = "AI virality scoring (cloud LLM)" if has_any_llm_key else "Audio loudness & speech spikes (no-key local mode)"

    # Mask secrets
    for k in ["gemini_api_key", "openai_api_key", "groq_api_key", "anthropic_api_key", "youtube_client_secret"]:
        if d.get(k):
            d[k] = mask_secret(d[k])

    return d

@app.put("/api/settings")
def api_update_settings(updates: SettingsUpdateRequest):
    dumped = updates.model_dump(exclude_unset=True)
    # Filter out masked secrets so we don't overwrite real keys with *** or ...
    for k in ["gemini_api_key", "openai_api_key", "groq_api_key", "anthropic_api_key", "youtube_client_secret"]:
        if k in dumped and ("..." in str(dumped[k]) or "***" in str(dumped[k])):
            dumped.pop(k)

    settings.save(dumped)
    return api_get_settings()

@app.post("/api/settings/test-and-save")
def api_test_and_save(req: TestAndSaveRequest):
    """Verifies credentials with a live test call, and if valid, saves locally into .env."""
    test_res = api_test_key(TestKeyRequest(provider=req.provider, key=req.key, url=req.url))
    if not test_res.get("success"):
        raise HTTPException(status_code=400, detail=test_res.get("error", "Key verification failed."))

    prov = req.provider.lower().strip()
    key = (req.key or "").strip()
    updates = {"llm_provider": prov}
    if prov == "gemini":
        updates["gemini_api_key"] = key
    elif prov == "openai":
        updates["openai_api_key"] = key
    elif prov == "groq":
        updates["groq_api_key"] = key
    elif prov == "anthropic":
        updates["anthropic_api_key"] = key
    elif prov == "ollama" and req.url:
        updates["ollama_url"] = req.url

    settings.save(updates)
    return {
        "success": True,
        "message": f"Successfully verified and saved {prov.title()} credentials locally!",
        "masked_key": mask_secret(key),
        "provider": prov,
    }

@app.get("/api/settings/models")
def api_find_models(provider: Optional[str] = None, key: Optional[str] = None):
    """Finds and lists available models from the specified provider."""
    prov = (provider or settings.llm_provider).lower().strip()
    target_key = key or (
        settings.gemini_api_key if prov == "gemini" else
        settings.openai_api_key if prov == "openai" else
        settings.groq_api_key if prov == "groq" else
        settings.anthropic_api_key if prov == "anthropic" else ""
    )

    models = []
    if prov == "gemini":
        if not target_key:
            return {"provider": prov, "models": ["gemini-flash-lite-latest", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={target_key}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    raw_models = resp.json().get("models", [])
                    models = [
                        m["name"].replace("models/", "")
                        for m in raw_models
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
        except Exception:
            models = ["gemini-flash-lite-latest", "gemini-1.5-flash", "gemini-1.5-pro"]
        return {"provider": prov, "models": models or ["gemini-flash-lite-latest", "gemini-1.5-flash"]}

    elif prov == "openai":
        if not target_key:
            return {"provider": prov, "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]}
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {target_key}"}
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    models = [m["id"] for m in raw if "gpt" in m["id"] or "o1" in m["id"] or "o3" in m["id"]]
                    models.sort()
        except Exception:
            models = ["gpt-4o-mini", "gpt-4o"]
        return {"provider": prov, "models": models or ["gpt-4o-mini", "gpt-4o"]}

    elif prov == "groq":
        if not target_key:
            return {"provider": prov, "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]}
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {target_key}"}
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    models = [m["id"] for m in raw]
        except Exception:
            models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
        return {"provider": prov, "models": models or ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]}

    elif prov == "ollama":
        target_url = (settings.ollama_url or "http://127.0.0.1:11434").rstrip("/")
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(f"{target_url}/api/tags")
                if resp.status_code == 200:
                    raw = resp.json().get("models", [])
                    models = [m["name"] for m in raw]
        except Exception:
            models = ["llama3:latest", "mistral:latest"]
        return {"provider": prov, "models": models or ["llama3:latest"]}

    return {"provider": prov, "models": []}

@app.get("/api/health")
def api_health():
    """Startup health check and environment diagnostics."""
    from .health import get_system_health
    return get_system_health()

@app.get("/api/models/whisper/status")
def api_whisper_status():
    """Local faster-whisper model catalog and download status."""
    return {
        "current_model": getattr(settings, "whisper_model", "tiny"),
        "models": [
            {"name": "tiny", "size_mb": 75, "speed": "Fastest (~32x)", "accuracy": "Good for clear speech", "downloaded": True},
            {"name": "base", "size_mb": 145, "speed": "Fast (~16x)", "accuracy": "Standard default", "downloaded": True},
            {"name": "small", "size_mb": 480, "speed": "Moderate (~6x)", "accuracy": "High accuracy", "downloaded": False},
            {"name": "medium", "size_mb": 1500, "speed": "Slower (~2x)", "accuracy": "Maximum precision", "downloaded": False},
        ],
        "is_local": getattr(settings, "transcription_option", "local_whisper") == "local_whisper",
    }

@app.post("/api/settings/test-key")
def api_test_key(req: TestKeyRequest):
    """Makes a tiny real call to verify an API key or local endpoint without heavy usage."""
    prov = req.provider.lower().strip()
    key = (req.key or "").strip()

    if prov == "gemini":
        if not key:
            raise HTTPException(status_code=400, detail="Gemini API key is required to test.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return {"success": True, "message": "Google Gemini API key is valid and connected!"}
                else:
                    return {"success": False, "error": f"Gemini error ({resp.status_code}): {resp.text[:120]}"}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    elif prov == "openai":
        if not key:
            raise HTTPException(status_code=400, detail="OpenAI API key is required to test.")
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return {"success": True, "message": "OpenAI API key is valid and active!"}
                else:
                    return {"success": False, "error": f"OpenAI error ({resp.status_code}): {resp.text[:120]}"}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    elif prov == "groq":
        if not key:
            raise HTTPException(status_code=400, detail="Groq API key is required to test.")
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {key}"}
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return {"success": True, "message": "Groq API key is valid!"}
                else:
                    return {"success": False, "error": f"Groq error ({resp.status_code}): {resp.text[:120]}"}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    elif prov == "ollama":
        target_url = (req.url or settings.ollama_url or "http://127.0.0.1:11434").rstrip("/")
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{target_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    m_names = [m.get("name") for m in models[:3]]
                    return {
                        "success": True,
                        "message": f"Ollama is online! Found {len(models)} model(s): {', '.join(m_names)}",
                    }
                else:
                    return {"success": False, "error": f"Ollama responded with status {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Could not reach Ollama at {target_url}: {str(e)}"}

    elif prov == "whisper":
        opt = req.key or getattr(settings, "transcription_option", "local_whisper")
        if opt == "openai_whisper":
            if not settings.openai_api_key:
                return {"success": False, "error": "OpenAI API key is missing for OpenAI Whisper."}
            return {"success": True, "message": "OpenAI Whisper configuration is ready."}
        else:
            return {"success": True, "message": "Local faster-whisper is installed and ready to transcribe."}

    raise HTTPException(status_code=400, detail=f"Unknown provider '{prov}'")

# ==================== YOUTUBE CONNECTION ====================
@app.post("/api/youtube/connect")
def api_youtube_connect(req: YouTubeConnectRequest):
    """In-app connection for YouTube OAuth using entered credentials."""
    res = connect_youtube_oauth(req.client_id, req.client_secret)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "YouTube authentication failed"))
    return res

@app.get("/api/youtube/status")
def api_youtube_status():
    """Retrieve YouTube OAuth connection status and channel identity."""
    auth = is_authenticated()
    channel_name = settings.youtube_channel_name
    if auth and not channel_name:
        info = get_channel_info()
        if info:
            channel_name = info.get("display_name", "")
    return {
        "authenticated": auth,
        "channel_name": channel_name or ("Connected Channel" if auth else ""),
    }

# ==================== MEDIA SERVING ====================
@app.get("/api/media/{session_id}/{filename}")
def api_serve_media(session_id: str, filename: str, request: Request):
    """Securely serve media files from data/out/session_N with HTTP 206 Partial Content Range support."""
    clean_filename = Path(filename).name
    file_path = DATA_OUT_DIR / session_id / clean_filename
    if not file_path.exists():
        # Fallback check directly in session_id directory or DATA_OUT_DIR
        alt = DATA_OUT_DIR / clean_filename
        if alt.exists():
            file_path = alt
        else:
            raise HTTPException(status_code=404, detail="Media file not found")

    file_size = file_path.stat().st_size
    is_video = clean_filename.endswith(".mp4")
    if is_video:
        content_type = "video/mp4"
    elif clean_filename.endswith(".png"):
        content_type = "image/png"
    elif clean_filename.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif clean_filename.endswith(".webp"):
        content_type = "image/webp"
    else:
        content_type = "application/octet-stream"

    # Range request handling for video streaming and seeking (Problem B.2)
    range_header = request.headers.get("Range")
    if is_video and range_header and range_header.startswith("bytes="):
        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
            if start >= file_size:
                raise HTTPException(status_code=416, detail="Requested range not satisfiable")
            end = min(end, file_size - 1)
            chunk_length = end - start + 1

            with open(file_path, "rb") as f:
                f.seek(start)
                data = f.read(chunk_length)

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
                "Content-Type": content_type,
            }
            return Response(data, status_code=206, headers=headers)
        except HTTPException:
            raise
        except Exception:
            pass

    # Standard response with caching headers (Problem D.4)
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400" if not is_video else "no-cache",
    }
    return FileResponse(file_path, media_type=content_type, headers=headers)

# Serve Frontend SPA
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "Clipper backend running. Frontend static files pending."})
