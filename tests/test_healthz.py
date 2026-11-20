"""Unit tests for /healthz and startup health diagnostics."""

from fastapi import Response
from clipper.api import api_health
from clipper.health import get_system_health

def test_healthz_function_returns_200_and_expected_fields():
    response = Response()
    data = api_health(response)
    assert response.status_code == 200
    assert data["status"] in ("ok", "degraded")
    assert data["healthy"] is True
    assert data["app_version"] == "1.0.0"
    assert "3.14" in data["python_version"]
    assert data["ffmpeg"]["found"] is True
    assert data["ffprobe"]["found"] is True
    assert data["yt_dlp_version"] != "not installed"
    assert data["js_runtime"]["found"] is True
    assert data["data_folder"]["writable"] is True
    assert data["data_folder"]["free_space_gb"] > 0
    assert data["project_path"]["length"] > 0
    assert "T" in data["time"]
    assert data["failing"] == []

def test_healthz_returns_503_on_failing_dependency(monkeypatch):
    from clipper import health
    monkeypatch.setattr(health, "find_ffmpeg", lambda: "nonexistent_ffmpeg_bin")
    response = Response()
    data = api_health(response)
    assert response.status_code == 503
    assert data["healthy"] is False
    assert len(data["failing"]) > 0
