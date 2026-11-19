"""Thumbnail generation: selects the best frame and overlays punchy title text."""

import os
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import httpx
import subprocess
from .config import settings, find_ffmpeg, find_ffprobe

def extract_poster_frame(video_path: Path, output_path: Path) -> bool:
    """
    Extracts a crisp 9:16 vertical poster frame from the middle of the clip using ffmpeg.
    Uses blur-fit so the video subject is clear in the center with a blurred background.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()

    # Get duration
    duration = 5.0
    try:
        cmd_p = [
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        res = subprocess.run(cmd_p, capture_output=True, text=True)
        if res.stdout.strip():
            duration = max(1.0, float(res.stdout.strip()))
    except Exception:
        pass

    midpoint = duration / 2.0

    # 540x960 9:16 vertical poster frame
    filter_graph = (
        "[0:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960,boxblur=15:4[bg];"
        "[0:v]scale=540:960:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    cmd = [
        ffmpeg, "-y",
        "-ss", str(midpoint),
        "-i", str(video_path),
        "-vf", filter_graph,
        "-vframes", "1",
        "-q:v", "3",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path.exists() and output_path.stat().st_size > 500
    except Exception as e:
        # Fallback to simple single frame
        try:
            cmd_fallback = [
                ffmpeg, "-y", "-ss", "0.5", "-i", str(video_path),
                "-vframes", "1", str(output_path)
            ]
            subprocess.run(cmd_fallback, capture_output=True, check=True)
            return output_path.exists() and output_path.stat().st_size > 500
        except Exception:
            return False

def find_best_frame(video_path: Path, sample_count: int = 8) -> Optional[np.ndarray]:
    """
    Examines frames across the video and picks the one with the highest visual clarity
    (balanced brightness and high Laplacian sharpness variance).
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return None

    best_frame = None
    best_score = -1.0

    step = max(1, total_frames // (sample_count + 1))
    curr_frame = 0
    samples_checked = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if curr_frame % step == 0 and curr_frame > 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            bright_penalty = 0.3 if (brightness < 40 or brightness > 230) else 1.0

            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            score = sharpness * bright_penalty

            if score > best_score:
                best_score = score
                best_frame = frame.copy()

            samples_checked += 1
            if samples_checked >= sample_count:
                break

        curr_frame += 1

    cap.release()
    return best_frame

def draw_title_overlay(
    image: Image.Image,
    title: str,
    accent_color: str = "#C93A18",
) -> Image.Image:
    """Draws high-contrast, beautiful title badge on image."""
    img = image.convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient dark vignette at top and bottom for readability
    top_vignette = Image.new("RGBA", (w, int(h * 0.35)), (0, 0, 0, 0))
    top_draw = ImageDraw.Draw(top_vignette)
    for y in range(top_vignette.height):
        alpha = int(180 * (1.0 - y / top_vignette.height))
        top_draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    img.paste(top_vignette, (0, 0), top_vignette)

    # Word wrapping
    words = title.upper().split()
    lines = []
    curr = []
    for word in words:
        curr.append(word)
        if len(" ".join(curr)) > 16:
            lines.append(" ".join(curr))
            curr = []
    if curr:
        lines.append(" ".join(curr))
    lines = lines[:3]  # max 3 lines

    # Approximate font size
    font_size = max(28, int(h * 0.05))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    line_height = int(font_size * 1.3)
    start_y = int(h * 0.12)

    # Red/orange highlight pill for line 1
    for idx, line in enumerate(lines):
        y_pos = start_y + idx * line_height
        # Measure text
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x_pos = (w - text_w) // 2

        # Draw background pill
        pad_x = 20
        pad_y = 8
        pill_box = [x_pos - pad_x, y_pos - pad_y, x_pos + text_w + pad_x, y_pos + text_h + pad_y]

        if idx == 0:
            draw.rounded_rectangle(pill_box, radius=12, fill=(201, 58, 24, 230))  # #C93A18
            draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255, 255))
        else:
            draw.rounded_rectangle(pill_box, radius=12, fill=(0, 0, 0, 200))
            draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255, 255))

    combined = Image.alpha_composite(img, overlay)
    return combined.convert("RGB")

def generate_ai_image_openai(prompt: str, api_key: str, output_path: Path) -> bool:
    """Generates AI thumbnail using OpenAI DALL-E if key is set with strict timeout."""
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "dall-e-3",
        "prompt": f"Dramatic YouTube short vertical thumbnail, cinematic lighting, 9:16 aspect: {prompt[:200]}",
        "n": 1,
        "size": "1024x1792",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                img_url = resp.json()["data"][0]["url"]
                img_data = client.get(img_url, timeout=5.0).content
                output_path.write_bytes(img_data)
                return True
            else:
                print(f"OpenAI DALL-E returned {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"OpenAI image generation fallback: {e}")
    return False

def create_thumbnail(
    video_path: Path,
    title: str,
    output_path: Path,
    aspect_ratio: str = "9:16",
    use_ai_image: bool = False,
) -> bool:
    """
    Creates thumbnail image:
    1. If use_ai_image=True and OPENAI_API_KEY is configured, tries AI generation.
    2. Otherwise extracts the sharpest frame in milliseconds, fits to aspect ratio, and adds title overlay.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Only call DALL-E if explicitly requested
    if use_ai_image and settings.openai_api_key:
        if generate_ai_image_openai(title, settings.openai_api_key, output_path):
            return True

    # 2. Extract best frame
    frame = find_best_frame(video_path)
    if frame is None:
        # Create gradient canvas if no frame could be read
        target_w, target_h = (1080, 1920) if aspect_ratio == "9:16" else (1080, 1080)
        img = Image.new("RGB", (target_w, target_h), color=(30, 30, 35))
    else:
        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)

    # Crop/fit to 9:16 or target
    target_w, target_h = (1080, 1920) if aspect_ratio == "9:16" else (1080, 1080)
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        # Wider than target -> crop sides
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        # Taller than target -> crop top/bottom
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))

    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Add overlay
    final_thumb = draw_title_overlay(img, title)
    final_thumb.save(str(output_path), "JPEG", quality=90)
    return output_path.exists() and output_path.stat().st_size > 500
