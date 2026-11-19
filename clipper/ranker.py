"""Ranking engine for scored clips."""

import re
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("clipper.ranker")

def calculate_score(
    hook: float,
    chat: float,
    emotion: float,
    story: float,
    trend: float,
    has_chat: bool = True,
) -> float:
    """
    Calculates 0-100 score according to spec:
    score = 0.30 hook + 0.25 chat + 0.20 emotion + 0.15 story + 0.10 trend.
    When has_chat is False, the chat weight (0.25) is redistributed over the other four:
    hook = 0.30/0.75 = 40%
    emotion = 0.20/0.75 = 26.67%
    story = 0.15/0.75 = 20%
    trend = 0.10/0.75 = 13.33%
    """
    hook = max(0.0, min(100.0, float(hook)))
    chat = max(0.0, min(100.0, float(chat)))
    emotion = max(0.0, min(100.0, float(emotion)))
    story = max(0.0, min(100.0, float(story)))
    trend = max(0.0, min(100.0, float(trend)))

    if has_chat:
        score = (
            0.30 * hook
            + 0.25 * chat
            + 0.20 * emotion
            + 0.15 * story
            + 0.10 * trend
        )
    else:
        norm = 0.30 + 0.20 + 0.15 + 0.10  # 0.75
        w_hook = 0.30 / norm
        w_emotion = 0.20 / norm
        w_story = 0.15 / norm
        w_trend = 0.10 / norm
        score = (
            w_hook * hook
            + w_emotion * emotion
            + w_story * story
            + w_trend * trend
        )

    return round(score, 1)

def build_rank_reason(rank: int, scores: Dict[str, float], has_chat: bool) -> str:
    """Generate human-readable one-line reason for why the clip ranked."""
    sub_keys = [("Hook", scores.get("hook", 0)),
                ("Emotion", scores.get("emotion", 0)),
                ("Story", scores.get("story", 0)),
                ("Trend", scores.get("trend", 0))]
    if has_chat:
        sub_keys.append(("Chat Craze", scores.get("chat", 0)))

    sub_keys.sort(key=lambda x: x[1], reverse=True)
    best_factors = [f"{k} ({v:.0f})" for k, v in sub_keys[:2] if v >= 40]
    if best_factors:
        factors_str = " and ".join(best_factors)
        return f"Ranked #{rank} driven by high {factors_str}"
    return f"Ranked #{rank} based on balanced engagement across all metrics"

def slugify(text: str) -> str:
    """Sanitize string for filenames."""
    s = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", s)[:30] or "clip"

def rank_and_rename_clips(
    clips: List[Dict[str, Any]],
    session_dir: Path,
    has_chat: bool = False,
) -> List[Dict[str, Any]]:
    """
    Ranks clips descending by score, assigns ranks (#1 to #N),
    renames files to 01_*.mp4, 02_*.mp4, and returns ranked list.
    """
    # Calculate scores
    for clip in clips:
        h = clip.get("hook_score", 50.0)
        c = clip.get("chat_score", 0.0)
        e = clip.get("emotion_score", 50.0)
        s = clip.get("story_score", 50.0)
        t = clip.get("trend_score", 50.0)
        clip["score"] = calculate_score(h, c, e, s, t, has_chat=has_chat)

    # Sort descending by score with deterministic tie-breakers (hook, loudness, chronological)
    clips.sort(key=lambda x: (
        round(float(x.get("score", 0.0)), 2),
        round(float(x.get("hook_score", 0.0)), 2),
        round(float(x.get("loudness_score", 0.0)), 2),
        -float(x.get("start", 0.0))
    ), reverse=True)

    # Log reason if any clips share identical overall scores
    scores_seen: Dict[float, Dict[str, Any]] = {}
    for clip in clips:
        s_val = round(float(clip.get("score", 0.0)), 1)
        if s_val in scores_seen:
            prev = scores_seen[s_val]
            logger.info(
                f"[Score Tie] Clips '{clip.get('title')}' and '{prev.get('title')}' share score {s_val:.1f}. "
                f"Breakdown for '{clip.get('title')}': Hook={clip.get('hook_score')}, Emotion={clip.get('emotion_score')}, "
                f"Story={clip.get('story_score')}, Trend={clip.get('trend_score')}, Loudness={clip.get('loudness_score')}. "
                f"Breakdown for '{prev.get('title')}': Hook={prev.get('hook_score')}, Emotion={prev.get('emotion_score')}, "
                f"Story={prev.get('story_score')}, Trend={prev.get('trend_score')}, Loudness={prev.get('loudness_score')}."
            )
        else:
            scores_seen[s_val] = clip

    ranked_clips = []
    for idx, clip in enumerate(clips, start=1):
        rank = idx
        clip["rank"] = rank
        clip["has_chat"] = has_chat
        scores_breakdown = {
            "hook": clip.get("hook_score", 50.0),
            "chat": clip.get("chat_score", 0.0),
            "emotion": clip.get("emotion_score", 50.0),
            "story": clip.get("story_score", 50.0),
            "trend": clip.get("trend_score", 50.0),
            "total": clip["score"],
        }
        clip["scores"] = scores_breakdown
        clip["reason"] = build_rank_reason(rank, scores_breakdown, has_chat)

        # Rename file to 01_slug.mp4
        old_path = Path(clip.get("file_path", ""))
        title = clip.get("title", f"Clip {rank}")
        slug = slugify(title)
        new_filename = f"{rank:02d}_{slug}.mp4"
        new_path = session_dir / new_filename

        if old_path.exists() and old_path != new_path:
            try:
                shutil.move(str(old_path), str(new_path))
                clip["file_path"] = str(new_path)
                clip["filename"] = new_filename
            except Exception as e:
                print(f"File rename warning: {e}")
                clip["file_path"] = str(old_path)
                clip["filename"] = old_path.name
        elif old_path.exists():
            clip["file_path"] = str(old_path)
            clip["filename"] = old_path.name
        else:
            clip["filename"] = new_filename

        ranked_clips.append(clip)

    return ranked_clips
