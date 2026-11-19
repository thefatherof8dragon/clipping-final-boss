"""Candidate moment picker based on loudness peaks, transcript hook phrases, and chat spikes."""

import subprocess
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import numpy as np
from .config import find_ffmpeg
from .ranker import calculate_score

@dataclass
class CandidateMoment:
    start: float
    end: float
    duration: float
    hook_score: float = 50.0
    chat_score: float = 0.0
    emotion_score: float = 50.0
    story_score: float = 50.0
    trend_score: float = 50.0
    loudness_score: float = 50.0
    combined_score: float = 50.0
    reason: str = "Exciting moment detected"
    transcript_text: str = ""
    words: List[Dict[str, Any]] = field(default_factory=list)

HOOK_KEYWORDS = {
    "wait", "watch", "secret", "never", "insane", "crazy", "unbelievable",
    "shocking", "omg", "look", "what", "why", "how", "listen", "bro",
    "stop", "huge", "biggest", "win", "lost", "fail", "died", "crying",
    "screaming", "no way", "oh my god", "did you", "truth", "revealed",
    "exposed", "wild", "caught", "hack", "trick", "money", "free", "warning",
    "secretly", "actually", "promise", "guarantee", "mistake"
}

EMOTION_KEYWORDS = {
    "love", "hate", "angry", "sad", "happy", "excited", "scared", "terrified",
    "amazing", "awesome", "terrible", "worst", "best", "hilarious", "laughing",
    "cry", "screaming", "shock", "pain", "fire", "omg", "holy", "insane",
    "heartbroken", "furious", "hype", "blessed", "relief", "panic", "chill"
}

STORY_KEYWORDS = {
    "then", "suddenly", "because", "so", "finally", "started", "happened",
    "yesterday", "story", "remember", "turned out", "next thing", "realized",
    "ended up", "years ago", "first time", "when", "after", "eventually",
    "meanwhile", "at that point", "in the end", "believe it or not"
}

TREND_KEYWORDS = {
    "viral", "trending", "challenge", "tiktok", "trend", "sigma", "skibidi",
    "fyp", "rizz", "mrbeast", "streamer", "react", "shorts", "meta",
    "clutch", "goat", "w", "l", "banned", "drama", "update", "secret"
}

def analyze_audio_loudness(video_path: Path, duration: float) -> np.ndarray:
    """Extract second-by-second audio RMS loudness using ffmpeg and numpy."""
    ffmpeg = find_ffmpeg()
    target_len = max(1, int(np.ceil(duration)))
    loudness = np.zeros(target_len, dtype=np.float32)

    try:
        cmd = [
            ffmpeg,
            "-y",
            "-i", str(video_path),
            "-vn",
            "-ac", "1",
            "-ar", "8000",
            "-f", "s16le",
            "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_bytes, _ = proc.communicate(timeout=60)
        if raw_bytes:
            samples = np.frombuffer(raw_bytes, dtype=np.int16)
            sr = 8000
            total_secs = len(samples) // sr
            if total_secs > 0:
                sec_rms = []
                for s in range(min(total_secs, target_len)):
                    chunk = samples[s * sr : (s + 1) * sr]
                    rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
                    sec_rms.append(rms)

                arr = np.array(sec_rms, dtype=np.float32)
                max_val = float(np.max(arr)) if len(arr) > 0 and np.max(arr) > 0 else 1.0
                normalized = (arr / max_val) * 100.0
                loudness[: len(normalized)] = normalized
    except Exception as e:
        logger.error(f"Loudness analysis error: {e}")
        raise RuntimeError(f"Audio loudness analysis failed on {video_path}: {e}") from e

    return loudness

def calculate_candidate_scores(
    start_sec: float,
    end_sec: float,
    loudness: np.ndarray,
    transcript_segments: List[Dict[str, Any]],
    chat_density: np.ndarray,
    has_chat: bool,
    window_words: List[Dict[str, Any]],
    window_text: str,
) -> Dict[str, float]:
    """Calculate distinct, nuanced metric scores for a specific time window."""
    s_idx = max(0, int(start_sec))
    e_idx = min(len(loudness), max(s_idx + 1, int(end_sec)))
    win_len = max(1.0, end_sec - start_sec)

    # Audio loudness metrics
    loud_slice = loudness[s_idx:e_idx] if len(loudness) > s_idx else np.array([50.0])
    avg_loudness = float(np.mean(loud_slice)) if len(loud_slice) > 0 else 50.0
    peak_loudness = float(np.max(loud_slice)) if len(loud_slice) > 0 else 50.0
    loud_std = float(np.std(loud_slice)) if len(loud_slice) > 0 else 5.0

    # First 4 seconds audio rise
    early_slice = loudness[s_idx : min(len(loudness), s_idx + 4)]
    early_avg = float(np.mean(early_slice)) if len(early_slice) > 0 else avg_loudness
    loudness_jump = max(0.0, early_avg - 40.0)

    # Text analysis
    text_lower = window_text.lower()
    first_sentence = ""
    for delimiter in [".", "!", "?"]:
        if delimiter in window_text:
            first_sentence = window_text.split(delimiter)[0].strip().lower()
            break
    if not first_sentence:
        first_sentence = " ".join(text_lower.split()[:10])

    # 1. Hook Score
    hook = 38.0
    if "?" in first_sentence:
        hook += 24.0
    elif any(first_sentence.startswith(q) for q in ["what", "why", "how", "did you", "can you", "who", "when"]):
        hook += 20.0
    if "!" in first_sentence:
        hook += 16.0
    for kw in HOOK_KEYWORDS:
        if kw in first_sentence:
            hook += 14.0
            break
    # Loudness surge at start boosts hook
    hook += min(15.0, loudness_jump * 0.4)
    hook = max(15.0, min(98.0, hook + (avg_loudness * 0.1)))

    # 2. Emotion Score
    emotion = 36.0
    emo_count = sum(1 for kw in EMOTION_KEYWORDS if kw in text_lower)
    emotion += min(35.0, emo_count * 14.0)
    # Speech tempo: fast speech indicates excitement
    word_rate = len(window_words) / win_len if win_len > 0 else 0
    if word_rate > 2.5:
        emotion += 18.0
    elif word_rate > 1.8:
        emotion += 10.0
    # Vocal volume fluctuation
    emotion += min(15.0, loud_std * 0.8)
    emotion = max(15.0, min(97.0, emotion))

    # 3. Story Score
    story = 35.0
    story_count = sum(1 for kw in STORY_KEYWORDS if kw in text_lower)
    story += min(36.0, story_count * 12.0)
    if any(end_p in window_text[-8:] for end_p in [".", "!", "?"]):
        story += 12.0  # Clean resolution
    if win_len >= 30.0:
        story += 10.0  # Room for narrative arc
    story = max(15.0, min(96.0, story))

    # 4. Trend Score
    trend = 34.0
    trend_count = sum(1 for kw in TREND_KEYWORDS if kw in text_lower)
    trend += min(40.0, trend_count * 18.0)
    if peak_loudness > 75.0:
        trend += 14.0
    trend = max(15.0, min(95.0, trend))

    # 5. Chat Score
    chat = 0.0
    if has_chat and len(chat_density) > s_idx:
        chat_slice = chat_density[s_idx:e_idx]
        chat = float(np.mean(chat_slice)) if len(chat_slice) > 0 else 0.0
        chat = max(0.0, min(100.0, chat))

    # 6. Combined Score using spec formula
    combined = calculate_score(hook, chat, emotion, story, trend, has_chat=has_chat)

    return {
        "hook": round(hook, 1),
        "chat": round(chat, 1),
        "emotion": round(emotion, 1),
        "story": round(story, 1),
        "trend": round(trend, 1),
        "loudness": round(avg_loudness, 1),
        "combined": round(combined, 1),
    }

def find_candidate_moments(
    video_path: Path,
    duration: float,
    transcript: Optional[Dict[str, Any]] = None,
    chat_events: Optional[List[Dict[str, Any]]] = None,
    target_count: int = 5,
    min_clip_len: float = 20.0,
    max_clip_len: float = 60.0,
) -> List[CandidateMoment]:
    """
    Finds candidate moments in video respecting length constraints and ensuring
    differentiated, realistic scores and natural boundaries.
    """
    if duration <= 0:
        duration = 60.0

    # Adapt length constraints gracefully if video duration is shorter
    if duration < min_clip_len:
        effective_min = max(2.0, duration * 0.25)
        effective_max = max(effective_min + 1.0, duration * 0.9)
    else:
        effective_min = max(3.0, min_clip_len)
        effective_max = min(duration, max(effective_min + 2.0, max_clip_len))

    loudness = analyze_audio_loudness(video_path, duration)
    total_secs = max(1, int(np.ceil(duration)))

    # Chat density
    chat_density = np.zeros(total_secs, dtype=np.float32)
    has_chat = bool(chat_events and len(chat_events) > 0)
    if has_chat:
        for ev in chat_events:
            t = int(ev.get("time", ev.get("offset", 0)))
            if 0 <= t < total_secs:
                chat_density[t] += 1
        max_chat = float(np.max(chat_density)) if np.max(chat_density) > 0 else 1.0
        chat_density = (chat_density / max_chat) * 100.0

    segments = transcript.get("segments", []) if transcript else []
    has_segments = len(segments) > 0

    candidates: List[CandidateMoment] = []

    # Strategy A: Use sentence/segment boundaries if transcript has speech
    if has_segments and duration >= 15.0:
        for i, seg in enumerate(segments):
            start_t = float(seg.get("start", 0.0))
            if start_t > duration - effective_min:
                break

            # Find matching segment ending that satisfies effective_min to effective_max
            best_end = None
            for j in range(i, len(segments)):
                seg_end = float(segments[j].get("end", 0.0))
                seg_len = seg_end - start_t
                if seg_len >= effective_min:
                    best_end = seg_end
                    # Stop if we hit a sentence end or close to max
                    txt = segments[j].get("text", "").strip()
                    if txt.endswith((".", "!", "?")) or seg_len >= (effective_min + effective_max) / 2.0:
                        break
                    if seg_len >= effective_max:
                        best_end = min(duration, start_t + effective_max)
                        break

            if best_end is None:
                best_end = min(duration, start_t + (effective_min + effective_max) / 2.0)

            end_t = min(duration, max(start_t + effective_min, best_end))
            if end_t - start_t > effective_max:
                end_t = start_t + effective_max

            # Collect text and words
            w_texts = []
            w_words = []
            for s in segments:
                if s["end"] >= start_t and s["start"] <= end_t:
                    w_texts.append(s.get("text", ""))
                    if "words" in s:
                        for w in s["words"]:
                            if w["start"] >= start_t and w["end"] <= end_t:
                                w_words.append(w)

            summary_text = " ".join(w_texts).strip()

            scores = calculate_candidate_scores(
                start_sec=start_t,
                end_sec=end_t,
                loudness=loudness,
                transcript_segments=segments,
                chat_density=chat_density,
                has_chat=has_chat,
                window_words=w_words,
                window_text=summary_text,
            )

            candidates.append(CandidateMoment(
                start=round(start_t, 2),
                end=round(end_t, 2),
                duration=round(end_t - start_t, 2),
                hook_score=scores["hook"],
                chat_score=scores["chat"],
                emotion_score=scores["emotion"],
                story_score=scores["story"],
                trend_score=scores["trend"],
                loudness_score=scores["loudness"],
                combined_score=scores["combined"],
                transcript_text=summary_text,
                words=w_words,
            ))

    # Strategy B: Sliding window across audio/time (works for music, games, or to fill gaps)
    target_win = min(
        effective_max,
        max(effective_min, min((effective_min + effective_max) / 2.0, (duration / max(1, target_count)) * 1.15))
    )
    step = max(1.0, target_win * 0.35)
    max_start = max(0.1, duration - target_win)

    cur_s = 0.0
    while cur_s <= max_start:
        cur_e = min(duration, cur_s + target_win)
        if cur_e - cur_s >= effective_min * 0.8:
            # Check if this window is already covered by a segment candidate
            min_cov_gap = min(2.5, max(1.0, duration / (target_count + 1)))
            already_covered = any(abs(c.start - cur_s) < min_cov_gap for c in candidates)
            if not already_covered:
                w_texts = []
                w_words = []
                for s in segments:
                    if s["end"] >= cur_s and s["start"] <= cur_e:
                        w_texts.append(s.get("text", ""))
                        if "words" in s:
                            for w in s["words"]:
                                if w["start"] >= cur_s and w["end"] <= cur_e:
                                    w_words.append(w)

                summary_text = " ".join(w_texts).strip()
                scores = calculate_candidate_scores(
                    start_sec=cur_s,
                    end_sec=cur_e,
                    loudness=loudness,
                    transcript_segments=segments,
                    chat_density=chat_density,
                    has_chat=has_chat,
                    window_words=w_words,
                    window_text=summary_text,
                )

                candidates.append(CandidateMoment(
                    start=round(cur_s, 2),
                    end=round(cur_e, 2),
                    duration=round(cur_e - cur_s, 2),
                    hook_score=scores["hook"],
                    chat_score=scores["chat"],
                    emotion_score=scores["emotion"],
                    story_score=scores["story"],
                    trend_score=scores["trend"],
                    loudness_score=scores["loudness"],
                    combined_score=scores["combined"],
                    transcript_text=summary_text,
                    words=w_words,
                ))

        cur_s += step

    # Sort candidates descending by combined score
    candidates.sort(key=lambda c: c.combined_score, reverse=True)

    # Non-maximum suppression to prevent overlapping clips
    selected: List[CandidateMoment] = []
    min_gap = min(max(1.0, duration / (target_count + 1)), max(2.0, effective_min * 0.45))
    for cand in candidates:
        if len(selected) >= target_count:
            break
        overlap = any(abs(cand.start - s.start) < min_gap for s in selected)
        if not overlap:
            selected.append(cand)

    # If we need more candidates to satisfy target_count and have candidates left, loosen min_gap
    if len(selected) < target_count and len(candidates) > len(selected):
        for cand in candidates:
            if len(selected) >= target_count:
                break
            if cand not in selected:
                overlap = any(abs(cand.start - s.start) < 0.8 for s in selected)
                if not overlap:
                    selected.append(cand)

    # Must have real detected moments
    if not selected:
        raise RuntimeError(
            "No viable speech or loudness moments detected in the source video. "
            "Please ensure the video contains intelligible speech or audio activity."
        )

    # Sort final selected list descending by combined score
    selected.sort(key=lambda c: c.combined_score, reverse=True)
    return selected[:target_count]
