"""Video rendering and editing engine supporting aspect ratios, framing modes, word-by-word captions, and overlays."""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
from .config import find_ffmpeg, find_ffprobe
from .caption_styles import get_caption_style

# Target aspect ratio definitions (width, height)
ASPECT_RATIOS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}

def detect_face_centers(video_path: Path, max_samples: int = 12) -> Tuple[float, float]:
    """
    Detects face center position normalized (0.0 to 1.0) using OpenCV Haar Cascade.
    Samples frames sequentially across video for maximum speed and smoothness.
    """
    face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if not os.path.exists(face_cascade_path):
        return (0.5, 0.4)

    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return (0.5, 0.4)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

    if total_frames <= 0 or frame_w <= 0 or frame_h <= 0:
        cap.release()
        return (0.5, 0.4)

    step = max(1, total_frames // max_samples)
    x_centers = []
    y_centers = []
    curr_frame = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if curr_frame % step == 0:
            small_h = 240
            small_w = int(frame_w * (small_h / frame_h))
            small = cv2.resize(frame, (small_w, small_h))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.3,
                minNeighbors=3,
                minSize=(25, 25),
            )

            if len(faces) > 0:
                faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
                fx, fy, fw, fh = faces[0]
                x_centers.append((fx + fw / 2.0) / small_w)
                y_centers.append((fy + fh / 2.0) / small_h)

            if len(x_centers) >= max_samples:
                break

        curr_frame += 1

    cap.release()

    if x_centers and y_centers:
        avg_x = float(np.median(x_centers))
        avg_y = float(np.median(y_centers))
        return (max(0.1, min(0.9, avg_x)), max(0.1, min(0.9, avg_y)))

    return (0.5, 0.4)

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cc"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def hex_to_ass_color(hex_str: str, alpha: str = "00") -> str:
    """Converts CSS hex color #RRGGBB to ASS &HAABBGGRR format."""
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:
        h = f"{h[0]}{h[0]}{h[1]}{h[1]}{h[2]}{h[2]}"
    if len(h) >= 6:
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H{alpha}{b}{g}{r}".upper()
    return f"&H{alpha}FFFFFF"

def generate_ass_subtitles(
    words: List[Dict[str, Any]],
    output_ass: Path,
    style: str = "pop",
    target_w: int = 1080,
    target_h: int = 1920,
    hook_text: Optional[str] = None,
    trim_offset: float = 0.0,
    custom_style: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Generates word-by-word animated ASS subtitle file matching the visual templates.
    Supports custom style overrides (font, size, colors, position).
    """
    # Normalize aliases
    clean_style = (style or "pop").lower().strip()
    if clean_style == "karaoke":
        clean_style = "pop"
    elif clean_style == "tiktok":
        clean_style = "box"

    tmpl = get_caption_style(clean_style)
    font_name = tmpl.get("ass_font", "Arial")
    primary_color = tmpl.get("ass_primary", "&H00FFFFFF")
    active_color = tmpl.get("ass_active", "&H0000F2FF")
    outline_color = tmpl.get("ass_outline", "&H00000000")
    back_color = tmpl.get("ass_back", "&H80000000")
    bold = tmpl.get("bold", 1)
    italic = tmpl.get("italic", 0)
    border_style = tmpl.get("border_style", 1)
    outline = tmpl.get("outline", 4)
    shadow = tmpl.get("shadow", 2)
    scale_pct = int(tmpl.get("active_scale", 1.1) * 100)
    is_uppercase = tmpl.get("text_transform") == "uppercase"

    font_size = int(target_h * 0.038)
    margin_v = int(target_h * 0.28)  # lower-middle region

    # Apply custom style overrides if provided
    if custom_style:
        if custom_style.get("font"):
            font_name = custom_style["font"]
        if custom_style.get("size"):
            # Size scale: 24 -> normal
            scale_fac = float(custom_style["size"]) / 28.0
            font_size = int(target_h * 0.038 * scale_fac)
        if custom_style.get("primary_color"):
            primary_color = hex_to_ass_color(custom_style["primary_color"])
        if custom_style.get("highlight_color"):
            active_color = hex_to_ass_color(custom_style["highlight_color"])
        if custom_style.get("position"):
            pos = str(custom_style["position"]).lower()
            if pos == "bottom":
                margin_v = int(target_h * 0.16)
            elif pos == "middle":
                margin_v = int(target_h * 0.44)
            elif pos == "top":
                margin_v = int(target_h * 0.76)
        if custom_style.get("boxed"):
            border_style = 3  # opaque box
            back_color = hex_to_ass_color(custom_style.get("box_color", "#111827"), alpha="40")

    hook_style_size = int(target_h * 0.042)
    hook_margin_v = int(target_h * 0.10)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_w}
PlayResY: {target_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},{bold},{italic},0,0,100,100,1,0,{border_style},{outline},{shadow},2,40,40,{margin_v},1
Style: Hook,Arial,{hook_style_size},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,1,0,0,0,100,100,1,0,1,5,3,8,40,40,{hook_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # Optional top hook banner for the first 5 seconds
    if hook_text and hook_text.strip():
        clean_hook = hook_text.strip().replace("\n", " ")
        events.append(f"Dialogue: 1,0:00:00.00,0:00:05.00,Hook,,0,0,0,,{clean_hook}")

    # Process words into small 3-5 word chunks
    if words:
        chunks = []
        current_chunk = []
        for w in words:
            # Adjust word start/end relative to trim offset
            w_start = w.get("start", 0.0) - trim_offset
            w_end = w.get("end", 0.0) - trim_offset
            if w_end < 0:
                continue
            current_chunk.append({
                "word": w.get("word", "").strip(),
                "start": max(0.0, w_start),
                "end": max(0.0, w_end),
            })
            if len(current_chunk) >= 4 or w.get("word", "").endswith((".", "!", "?")):
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        # For each chunk, highlight active word as it plays
        for chunk in chunks:
            chunk_start = chunk[0]["start"]
            chunk_end = chunk[-1]["end"]
            if chunk_end <= chunk_start:
                chunk_end = chunk_start + 1.5

            for i, active_w in enumerate(chunk):
                w_start = active_w["start"]
                w_end = max(w_start + 0.1, active_w["end"])

                # Assemble line with active word styled
                line_parts = []
                for j, item in enumerate(chunk):
                    word_str = item["word"]
                    if is_uppercase:
                        word_str = word_str.upper()

                    if i == j:
                        # Active word highlighted
                        if scale_pct != 100:
                            line_parts.append(r"{\c" + active_color + f"\\fscx{scale_pct}\\fscy{scale_pct}" + r"}" + word_str + r"{\r}")
                        else:
                            line_parts.append(r"{\c" + active_color + r"}" + word_str + r"{\r}")
                    else:
                        line_parts.append(r"{\c" + primary_color + r"}" + word_str)

                text_line = " ".join(line_parts)
                start_str = format_ass_time(w_start)
                end_str = format_ass_time(w_end)
                events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_line}")

    output_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

def render_clip(
    input_video: Path,
    output_video: Path,
    aspect_ratio: str = "9:16",
    framing: str = "blur_fit",
    words: Optional[List[Dict[str, Any]]] = None,
    caption_style: str = "karaoke",
    captions_on: bool = True,
    hook_text: Optional[str] = None,
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    custom_style: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Renders clip with chosen aspect ratio, framing mode, captions, and overlays.
    """
    ffmpeg = find_ffmpeg()
    target_w, target_h = ASPECT_RATIOS.get(aspect_ratio, (1080, 1920))
    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Determine trim duration
    trim_duration = None
    if trim_end is not None and trim_end > trim_start:
        trim_duration = trim_end - trim_start

    # Build video filter graph based on framing mode
    if framing == "crop_to_face":
        # Compute face center
        center_x, center_y = detect_face_centers(input_video)
        # Target aspect ratio as float
        target_ratio = target_w / target_h

        # In crop_to_face:
        # If target is taller than source (e.g. 9:16 from 16:9), crop width = H * target_ratio
        # If target is wider than source, crop height = W / target_ratio
        filter_base = (
            f"[0:v]split[v1][v2];"
            f"[v1]scale=trunc(ih*{target_ratio}/2)*2:ih[face_crop];"
            f"[v2]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},boxblur=20:5[bg];"
            f"[face_crop]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )
    else:  # blur_fit (default)
        filter_base = (
            f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},"
            f"boxblur=20:5,eq=brightness=-0.10[bg];"
            f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )

    # Subtitles handling
    ass_path = output_video.with_suffix(".ass")
    has_subtitles = False
    if captions_on and (words or (hook_text and hook_text.strip())):
        generate_ass_subtitles(
            words=words or [],
            output_ass=ass_path,
            style=caption_style,
            target_w=target_w,
            target_h=target_h,
            hook_text=hook_text,
            trim_offset=trim_start,
            custom_style=custom_style,
        )
        has_subtitles = ass_path.exists()

    # Format subtitles filter safely for Windows path escaping
    if has_subtitles:
        # FFmpeg ass filter requires escaping colons and backslashes
        ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
        video_filter = f"{filter_base};[base]ass='{ass_str}'[outv]"
    else:
        video_filter = f"{filter_base};[base]null[outv]"

    cmd = [
        ffmpeg,
        "-y",
    ]
    if trim_start > 0:
        cmd.extend(["-ss", str(trim_start)])
    if trim_duration is not None:
        cmd.extend(["-t", str(trim_duration)])

    cmd.extend([
        "-i", str(input_video),
        "-filter_complex", video_filter,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_video),
    ])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_video.exists() and output_video.stat().st_size > 1000
    except subprocess.CalledProcessError as e:
        print(f"Render failed with error: {e.stderr}")
        # If ASS filter failed (e.g. fontconfig), retry without ASS
        if has_subtitles:
            try:
                cmd_retry = [
                    ffmpeg, "-y",
                ]
                if trim_start > 0:
                    cmd_retry.extend(["-ss", str(trim_start)])
                if trim_duration is not None:
                    cmd_retry.extend(["-t", str(trim_duration)])
                cmd_retry.extend([
                    "-i", str(input_video),
                    "-filter_complex", f"{filter_base};[base]null[outv]",
                    "-map", "[outv]",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "22",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    str(output_video),
                ])
                subprocess.run(cmd_retry, capture_output=True, check=True)
                return output_video.exists() and output_video.stat().st_size > 1000
            except Exception as e2:
                print(f"Render retry failed: {e2}")
        return False
    finally:
        if ass_path.exists():
            try:
                ass_path.unlink(missing_ok=True)
            except Exception:
                pass
