"""Stage 6 Check: Pinned streamers, live watcher, and simulated stream spike clipping."""

from clipper.api import (
    api_get_streamers,
    api_pin_streamer,
    api_remove_streamer,
    api_streamer_status,
    api_toggle_watch,
    StreamerRequest,
)
from clipper.streamers import detect_platform, simulate_live_spike

def test_platform_detection():
    assert detect_platform("https://twitch.tv/shroud") == "twitch"
    assert detect_platform("https://kick.com/xqc") == "kick"
    assert detect_platform("https://youtube.com/watch?v=12345") == "youtube"
    assert detect_platform("https://youtu.be/12345") == "youtube"

def test_resolve_handle_and_platform():
    from clipper.streamers import resolve_handle_and_platform
    # Direct URLs
    url, plat = resolve_handle_and_platform("https://twitch.tv/caylus", "auto")
    assert url == "https://twitch.tv/caylus"
    assert plat == "twitch"

    url, plat = resolve_handle_and_platform("https://kick.com/xqc", "auto")
    assert url == "https://kick.com/xqc"
    assert plat == "kick"

    # Bare handles with explicit platform
    url, plat = resolve_handle_and_platform("caylus", "twitch")
    assert url == "https://www.twitch.tv/caylus"
    assert plat == "twitch"

    url, plat = resolve_handle_and_platform("caylus", "kick")
    assert url == "https://kick.com/caylus"
    assert plat == "kick"

    url, plat = resolve_handle_and_platform("caylus", "youtube")
    assert url == "https://www.youtube.com/@caylus"
    assert plat == "youtube"

def test_pin_and_manage_streamers():
    # Pin streamer
    streamer = api_pin_streamer(StreamerRequest(name="TestGamer", url="https://twitch.tv/testgamer"))
    assert streamer["name"] == "TestGamer"
    assert streamer["platform"] == "twitch"
    streamer_id = streamer["id"]

    # List streamers
    streamers = api_get_streamers()
    assert any(s["id"] == streamer_id for s in streamers)

    # Status
    status_data = api_streamer_status(streamer_id)
    assert "chat_rate_history" in status_data

    # Toggle watch
    toggle_data = api_toggle_watch(streamer_id)
    assert "is_live" in toggle_data

    # Clean up
    del_res = api_remove_streamer(streamer_id)
    assert del_res["success"] is True

def test_simulated_stream_spike_clipping(test_video_path):
    """
    Stage 6 requirement: simulated stream (local file plus chat generator) produces spike clips.
    """
    result = simulate_live_spike(
        source_video=test_video_path,
        streamer_id="sim_test_streamer",
        spike_rate=180,
    )
    assert result["streamer_id"] == "sim_test_streamer"
    assert result["clip_count"] >= 1
    clip = result["clips"][0]
    assert "spike_rate" in clip
    assert clip["spike_rate"] == 180
