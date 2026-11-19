"""Local transcription using faster-whisper with word-level timestamps."""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from .config import find_ffmpeg, settings

# Compatibility patch for PyAV >= 14 where metadata_errors was removed
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

# Cache model instance in memory
_CACHED_MODEL: Optional[Any] = None
_CACHED_MODEL_SIZE: Optional[str] = None

def get_whisper_model(model_size: str = "tiny") -> Any:
    """Load or retrieve cached faster-whisper model."""
    global _CACHED_MODEL, _CACHED_MODEL_SIZE
    if WhisperModel is None:
        return None
    if _CACHED_MODEL is not None and _CACHED_MODEL_SIZE == model_size:
        return _CACHED_MODEL

    try:
        # Try local cache first for instant offline loading
        _CACHED_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=True)
        _CACHED_MODEL_SIZE = model_size
        return _CACHED_MODEL
    except Exception:
        try:
            _CACHED_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=False)
            _CACHED_MODEL_SIZE = model_size
            return _CACHED_MODEL
        except Exception as e:
            print(f"Whisper model load note: {e}")
            try:
                _CACHED_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
                _CACHED_MODEL_SIZE = "tiny"
                return _CACHED_MODEL
            except Exception:
                return None

def extract_audio_wav(video_path: Path, output_wav: Path) -> bool:
    """Extract 16kHz mono WAV audio from video for fast processing."""
    ffmpeg = find_ffmpeg()
    try:
        cmd = [
            ffmpeg,
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_wav),
        ]
        res = subprocess.run(cmd, capture_output=True, check=True)
        return output_wav.exists() and output_wav.stat().st_size > 100
    except Exception:
        return False

def transcribe(video_path: Path, model_size: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcribes audio from video file with word-level timestamps.
    Supports local faster-whisper (tiny, base, small, medium) and OpenAI Whisper API.
    """
    if model_size is None:
        model_size = getattr(settings, "whisper_model", "tiny") or "tiny"

    video_path = Path(video_path)
    wav_path = video_path.with_suffix(".wav")
    has_audio = extract_audio_wav(video_path, wav_path)
    target_audio = str(wav_path) if has_audio else str(video_path)

    # Optional OpenAI Whisper API if configured
    if getattr(settings, "transcription_option", "") == "openai_whisper" and getattr(settings, "openai_api_key", ""):
        try:
            import httpx
            with open(target_audio, "rb") as af:
                files = {"file": (os.path.basename(target_audio), af, "audio/wav")}
                data = {"model": "whisper-1", "response_format": "verbose_json", "timestamp_granularities[]": "word"}
                headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        words_data = [
                            {"word": w["word"].strip(), "start": round(w["start"], 2), "end": round(w["end"], 2)}
                            for w in res_json.get("words", [])
                        ]
                        segments_data = [
                            {"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip(), "words": words_data}
                            for s in res_json.get("segments", [])
                        ]
                        return {
                            "language": res_json.get("language", "en"),
                            "duration": res_json.get("duration", 0.0),
                            "segments": segments_data,
                            "full_text": res_json.get("text", "").strip(),
                        }
        except Exception as e:
            print(f"OpenAI Whisper fallback to local: {e}")

    model = get_whisper_model(model_size)
    if model is None:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)
        return {
            "language": "en",
            "duration": 0.0,
            "segments": [],
            "full_text": "",
        }

    segments_out = []
    full_text_parts = []
    detected_lang = "en"
    duration = 0.0

    try:
        segments, info = model.transcribe(
            target_audio,
            beam_size=1,
            word_timestamps=True,
            vad_filter=False,
        )
        detected_lang = info.language
        duration = info.duration

        for seg in segments:
            words_data = []
            if seg.words:
                for w in seg.words:
                    words_data.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "prob": round(w.probability, 2),
                    })
            text_clean = seg.text.strip()
            if text_clean:
                full_text_parts.append(text_clean)
                segments_out.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text_clean,
                    "words": words_data,
                })
    except Exception as e:
        print(f"Transcription error: {e}")
    finally:
        if wav_path.exists():
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    return {
        "language": detected_lang,
        "duration": duration,
        "segments": segments_out,
        "full_text": " ".join(full_text_parts),
    }
