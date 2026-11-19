"""Stage 7 Check: YouTube scheduling opt-in, daily cap enforcement, and dry-run mode."""

from pathlib import Path
from clipper.youtube import schedule_upload, is_authenticated
from clipper.state import check_and_increment_upload, load_state, save_state
from clipper.config import settings

def test_dry_run_upload(test_video_path):
    res = schedule_upload(
        video_path=test_video_path,
        title="Epic Stream Highlight",
        description="Check out this crazy highlight!",
        tags=["#shorts", "#viral", "#gaming"],
        publish_at="2026-11-20T18:00:00Z",
        dry_run=True,
    )
    assert res["success"] is True
    assert res["simulated"] is True
    assert "video_id" in res
    assert res["scheduled_time"] == "2026-11-20T18:00:00Z"
    assert "Dry-run" in res["note"]

from datetime import date

def test_daily_upload_cap_enforcement(test_video_path):
    state = load_state()
    today_str = str(date.today())
    # Mock daily upload cap reached
    settings.daily_upload_cap = 2
    state["uploads"] = {"date": today_str, "count": 2}
    save_state(state)

    allowed, count, msg = check_and_increment_upload()
    assert allowed is False
    assert "Daily upload cap" in msg

    # Reset
    state["uploads"] = {"date": today_str, "count": 0}
    save_state(state)
    settings.daily_upload_cap = 5

def test_auth_status_check():
    # In test environment with no token, returns False cleanly without error
    auth = is_authenticated()
    assert isinstance(auth, bool)
