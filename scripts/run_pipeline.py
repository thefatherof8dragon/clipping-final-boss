import os
import sys
import shutil
import subprocess
import json
import time
from pathlib import Path

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from clipper.config import (
    find_ffmpeg,
    find_ffprobe,
    settings,
    DATA_IN_DIR,
    DATA_OUT_DIR,
)
from clipper.downloader import download_or_load
from clipper.transcriber import transcribe
from clipper.candidate_picker import find_candidate_moments
from clipper.ai import generate_clip_metadata
from clipper.cutter import cut_clip
from clipper.renderer import render_clip


def print_banner(text: str):
    print("\n" + "=" * 65)
    print(f" {text}")
    print("=" * 65)


def check_prerequisites():
    print_banner("STAGE 0: PREREQUISITES VERIFICATION")

    # 1. Python version
    py_ver = sys.version.replace("\n", " ")
    print(f"[OK] Python Version: {py_ver}")
    if sys.version_info < (3, 10):
        print("[FAIL] Python 3.10+ is required!")
        sys.exit(1)

    # 2. ffmpeg & ffprobe
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    if not ffmpeg or not os.path.exists(ffmpeg):
        print("[FAIL] ffmpeg not found! Please install ffmpeg or add to PATH.")
        sys.exit(1)
    if not ffprobe or not os.path.exists(ffprobe):
        print("[FAIL] ffprobe not found! Please install ffprobe or add to PATH.")
        sys.exit(1)

    # Ensure ffmpeg bin is in PATH for any sub-processes
    ffmpeg_dir = str(Path(ffmpeg).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{ffmpeg_dir};" + os.environ.get("PATH", "")

    # Get ffmpeg version
    ff_res = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
    first_line = ff_res.stdout.splitlines()[0] if ff_res.stdout else "Unknown"
    print(f"[OK] ffmpeg: {ffmpeg}")
    print(f"     Version info: {first_line}")

    prob_res = subprocess.run([ffprobe, "-version"], capture_output=True, text=True)
    prob_line = prob_res.stdout.splitlines()[0] if prob_res.stdout else "Unknown"
    print(f"[OK] ffprobe: {ffprobe}")
    print(f"     Version info: {prob_line}")

    # 3. yt-dlp
    try:
        import yt_dlp
        print(f"[OK] yt-dlp installed: version {yt_dlp.version.__version__}")
    except ImportError:
        print("[FAIL] yt-dlp is not installed in the environment!")
        sys.exit(1)

    # 4. Disk space
    total, used, free = shutil.disk_usage(WORKSPACE_ROOT)
    free_gb = free / (1024 ** 3)
    print(f"[OK] Disk Space: {free_gb:.2f} GB free")
    if free_gb < 2.0:
        print("[WARN] Low disk space (< 2 GB free).")


def run_ffprobe_json(file_path: Path) -> dict:
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_pipeline.py <url_or_video_path>")
        sys.exit(1)

    raw_url = sys.argv[1].strip()

    # Step 0: Check prerequisites
    check_prerequisites()

    # Normalize YouTube video ID case if standard format
    target_url = raw_url
    if "CsWOUBuokjo" in target_url:
        target_url = target_url.replace("CsWOUBuokjo", "CswOUBuokjo")

    session_id = f"cli_{int(time.time())}"
    print(f"\nStarting pipeline run for session: {session_id}")
    print(f"Target URL: {target_url}")

    # Step 1: Download stage
    print_banner("STAGE 1: DOWNLOAD")
    try:
        dl_res = download_or_load(target_url, session_id=session_id)
        video_path = Path(dl_res["file_path"])
    except Exception as e:
        print(f"[FAIL] Download failed: {e}")
        if "bot" in str(e).lower() or "403" in str(e):
            print("Hint: YouTube bot-check/403 error. Try exporting browser cookies with --cookies.")
        sys.exit(1)

    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Downloaded file path: {video_path}")
    print(f"[OK] File size: {file_size_mb:.2f} MB")

    probe_data = run_ffprobe_json(video_path)
    duration = float(probe_data.get("format", {}).get("duration", 0.0))
    streams = probe_data.get("streams", [])
    print(f"[OK] ffprobe duration: {duration:.2f} seconds")
    print(f"[OK] ffprobe streams ({len(streams)}):")
    for s in streams:
        codec_type = s.get("codec_type")
        codec_name = s.get("codec_name")
        w = s.get("width")
        h = s.get("height")
        dim_str = f" {w}x{h}" if w and h else ""
        print(f"     - Stream #{s.get('index')}: {codec_type} ({codec_name}){dim_str}")

    # Step 2: Transcribe stage
    print_banner("STAGE 2: TRANSCRIBE")
    trans_cache_file = video_path.with_suffix(".transcript.json")
    if trans_cache_file.exists():
        with open(trans_cache_file, "r", encoding="utf-8") as tf:
            trans_res = json.load(tf)
        print(f"[OK] Loaded cached transcript from {trans_cache_file}")
    else:
        trans_res = transcribe(video_path, model_size=settings.whisper_model or "tiny")
        try:
            with open(trans_cache_file, "w", encoding="utf-8") as tf:
                json.dump(trans_res, tf)
        except Exception:
            pass
    segments = trans_res.get("segments", [])
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append(w)

    print(f"[OK] Total transcribed segments: {len(segments)}")
    print(f"[OK] Total words detected: {len(all_words)}")
    print("\n--- FIRST 10 TRANSCRIBED WORDS WITH TIMESTAMPS ---")
    for idx, w in enumerate(all_words[:10], start=1):
        print(f"  {idx:2d}. [{w.get('start', 0.0):.2f}s -> {w.get('end', 0.0):.2f}s]: \"{w.get('word', '').strip()}\"")
    print("--------------------------------------------------")

    # Step 3: Candidate Moments & Virality Ranking
    print_banner("STAGE 3: CANDIDATE MOMENTS & VIRALITY RANKING")
    moments = find_candidate_moments(
        video_path=video_path,
        duration=duration,
        transcript=trans_res,
        target_count=3,
        min_clip_len=15.0,
        max_clip_len=60.0,
    )
    print(f"[OK] Detected {len(moments)} viable candidate moments.")
    if not moments:
        print("[FAIL] No candidate moments detected!")
        sys.exit(1)

    top_moment = moments[0]
    print(f"[OK] Selected Top Moment: [{top_moment.start}s -> {top_moment.end}s] "
          f"Duration: {top_moment.duration}s, Score: {top_moment.combined_score}")
    print(f"     Transcript excerpt: \"{top_moment.transcript_text[:120]}...\"")

    print("\nCalling Gemini LLM for Virality Metadata (Prompt & Response)...")
    meta = generate_clip_metadata(
        transcript_text=top_moment.transcript_text,
        clip_rank=1,
    )
    print(f"[OK] Returned Title:   \"{meta.get('title')}\"")
    print(f"[OK] Returned Caption: \"{meta.get('caption')}\"")
    print(f"[OK] Returned Tags:    {meta.get('hashtags')}")
    print(f"[OK] Provider Used:    {meta.get('provider')}")

    # Step 4: Cut & Render
    print_banner("STAGE 4: CUT & RENDER CLIP")
    out_dir = DATA_OUT_DIR / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_cut_path = out_dir / "raw_clip_1.mp4"
    final_clip_path = out_dir / "01_rendered_clip.mp4"

    # Cut segment
    ffmpeg_bin = find_ffmpeg()
    cut_cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(top_moment.start),
        "-to", str(top_moment.end),
        "-i", str(video_path),
        "-c:v", "libx264", "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        str(raw_cut_path),
    ]
    print(f"FFmpeg Cut Command: {' '.join(cut_cmd)}")
    cut_res = subprocess.run(cut_cmd, capture_output=True, text=True)
    print(f"FFmpeg Cut Exit Code: {cut_res.returncode}")
    if cut_res.returncode != 0:
        print(f"[FAIL] Cut failed: {cut_res.stderr}")
        sys.exit(1)
    print(f"[OK] Cut clip saved: {raw_cut_path} ({raw_cut_path.stat().st_size / 1024:.1f} KB)")

    # Render vertical 9:16 with animated captions
    print("\nRendering vertical 9:16 clip with kinetic captions...")
    success = render_clip(
        input_video=raw_cut_path,
        output_video=final_clip_path,
        aspect_ratio="9:16",
        framing="blur_fit",
        words=top_moment.words,
        caption_style="pop",
        hook_text=meta.get("title"),
    )
    print(f"Render Success: {success}")

    if not final_clip_path.exists() or final_clip_path.stat().st_size < 1000:
        print(f"[FAIL] Rendered clip missing or empty at {final_clip_path}!")
        sys.exit(1)

    print(f"[OK] Rendered clip successfully: {final_clip_path}")
    print(f"     Size: {final_clip_path.stat().st_size / (1024 * 1024):.2f} MB")

    # Probe rendered clip
    clip_probe = run_ffprobe_json(final_clip_path)
    c_streams = clip_probe.get("streams", [])
    print(f"[OK] Rendered clip streams ({len(c_streams)}):")
    for s in c_streams:
        c_type = s.get("codec_type")
        c_name = s.get("codec_name")
        w = s.get("width")
        h = s.get("height")
        dim_str = f" {w}x{h}" if w and h else ""
        print(f"     - Stream #{s.get('index')}: {c_type} ({c_name}){dim_str}")

    # Step 5: Extract frame 1 and 50% duration PNG frames
    print_banner("STAGE 5: FRAME EXTRACTION & VERIFICATION")
    scratch_dir = WORKSPACE_ROOT / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    frame_1_path = scratch_dir / "frame_1.png"
    frame_50_path = scratch_dir / "frame_50pct.png"

    # Frame 1 (at 0.1s to ensure keyframe decode)
    ffmpeg_bin = find_ffmpeg()
    cmd1 = [
        ffmpeg_bin, "-y",
        "-ss", "0.1",
        "-i", str(final_clip_path),
        "-vframes", "1",
        str(frame_1_path),
    ]
    subprocess.run(cmd1, capture_output=True, check=True)

    # Frame at 50%
    clip_dur = float(clip_probe.get("format", {}).get("duration", top_moment.duration))
    half_time = max(0.1, clip_dur / 2.0)
    cmd2 = [
        ffmpeg_bin, "-y",
        "-ss", f"{half_time:.2f}",
        "-i", str(final_clip_path),
        "-vframes", "1",
        str(frame_50_path),
    ]
    subprocess.run(cmd2, capture_output=True, check=True)

    print(f"[OK] Extracted Frame 1:    {frame_1_path} ({frame_1_path.stat().st_size / 1024:.1f} KB)")
    print(f"[OK] Extracted Frame 50%:  {frame_50_path} ({frame_50_path.stat().st_size / 1024:.1f} KB)")

    # Assert frames are real PNG files and substantial size
    assert frame_1_path.stat().st_size > 10000, "Frame 1 image is too small, possible blank/corrupted frame"
    assert frame_50_path.stat().st_size > 10000, "Frame 50% image is too small, possible blank/corrupted frame"

    print("\n" + "=" * 65)
    print(" PIPELINE COMPLETED SUCCESSFULLY WITH 100% REAL DATA!")
    print("=" * 65)


if __name__ == "__main__":
    main()
