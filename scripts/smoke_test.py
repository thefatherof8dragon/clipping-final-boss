"""CI Smoke Test for Clipping Final Boss.

Runs the complete local pipeline on a sample audio/video source,
validates that clips, word timestamps, and ranking metadata are produced,
and exits 0 on success, non-zero on failure.
"""

import sys
import shutil
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from clipper.session import process_video_pipeline
from clipper.config import DATA_OUT_DIR

def run_smoke_test() -> int:
    print("=" * 60)
    print("  🚀 Running Clipping Final Boss CI Smoke Test")
    print("=" * 60)

    # Locate sample video
    sample_video = ROOT_DIR / "data" / "real_speech_5min_final.mp4"
    if not sample_video.exists():
        print(f"❌ Smoke test sample video not found at: {sample_video}")
        return 1

    print(f"Using sample input: {sample_video.name}")

    def on_progress(pct: float, msg: str = "", **kw):
        print(f"  [Progress {pct:5.1f}%] {msg}")

    smoke_session_id = None
    try:
        session = process_video_pipeline(
            source=str(sample_video),
            top_n=1,
            min_len=5.0,
            max_len=25.0,
            length_range="Under 30s",
            progress_callback=on_progress,
        )

        smoke_session_id = session.get("id")
        clips = session.get("clips", [])
        print(f"\nPipeline completed. Produced {len(clips)} clip(s).")

        if not clips:
            print("❌ Failure: Pipeline returned 0 clips.")
            return 1

        clip = clips[0]
        clip_path = Path(clip.get("file_path", ""))
        print(f"Clip #1 File: {clip_path}")
        print(f"Clip #1 Score: {clip.get('score')}")
        print(f"Clip #1 Words: {len(clip.get('words', []))} words")

        # Verifications
        if not clip_path.exists():
            print(f"❌ Failure: Clip file does not exist on disk: {clip_path}")
            return 1

        if clip_path.stat().st_size < 1000:
            print(f"❌ Failure: Clip file is too small ({clip_path.stat().st_size} bytes)")
            return 1

        if not clip.get("words"):
            print("❌ Failure: Clip words transcript is empty.")
            return 1

        score = clip.get("score", 0)
        if score <= 0 or score > 100:
            print(f"❌ Failure: Clip score out of bounds: {score}")
            return 1

        print("\n✅ Smoke test PASSED: Video download/cut, Whisper transcription, and ranking verified.")
        return 0

    except Exception as e:
        print(f"\n❌ Smoke test EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Clean up smoke test output directory
        if smoke_session_id:
            out_dir = DATA_OUT_DIR / smoke_session_id
            if out_dir.exists():
                try:
                    shutil.rmtree(out_dir, ignore_errors=True)
                    print(f"Cleaned up smoke session directory: {smoke_session_id}")
                except Exception:
                    pass

if __name__ == "__main__":
    sys.exit(run_smoke_test())
