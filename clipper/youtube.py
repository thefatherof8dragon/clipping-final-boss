"""YouTube scheduling and upload module using OAuth 2.0 desktop flow."""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from .config import ROOT_DIR, DATA_DIR, settings
from .state import check_and_increment_upload

CLIENT_SECRETS_FILE = ROOT_DIR / "client_secrets.json"
TOKEN_FILE = DATA_DIR / "youtube_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def get_channel_info() -> Optional[Dict[str, Any]]:
    """Fetch channel title and info using current credentials."""
    if not is_authenticated():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        youtube = build("youtube", "v3", credentials=creds)
        resp = youtube.channels().list(mine=True, part="snippet").execute()
        items = resp.get("items", [])
        if items:
            snippet = items[0].get("snippet", {})
            title = snippet.get("title", "")
            custom_url = snippet.get("customUrl", "")
            channel_name = custom_url if custom_url else title
            settings.save({"youtube_channel_name": channel_name})
            return {
                "title": title,
                "custom_url": custom_url,
                "display_name": channel_name,
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            }
    except Exception as e:
        print(f"Error fetching YouTube channel info: {e}")
    return None

def is_authenticated() -> bool:
    """Returns True if valid YouTube credentials exist on machine."""
    if not TOKEN_FILE.exists():
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        return bool(creds and (creds.valid or creds.expired and creds.refresh_token))
    except Exception:
        return False

def connect_youtube_oauth(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connects YouTube using client ID and client secret entered in UI.
    Creates or updates client_secrets.json and runs OAuth flow.
    """
    cid = (client_id or getattr(settings, "youtube_client_id", "")).strip()
    csecret = (client_secret or getattr(settings, "youtube_client_secret", "")).strip()

    if cid and csecret:
        client_config = {
            "installed": {
                "client_id": cid,
                "client_secret": csecret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost", "http://127.0.0.1"],
            }
        }
        CLIENT_SECRETS_FILE.write_text(json.dumps(client_config, indent=2), encoding="utf-8")
        settings.save({"youtube_client_id": cid, "youtube_client_secret": csecret})

    if not CLIENT_SECRETS_FILE.exists():
        return {
            "success": False,
            "error": "Missing OAuth Client ID and Client Secret. Please paste them in Settings Step 4.",
        }

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        info = get_channel_info()
        channel_display = info.get("display_name", "YouTube Channel") if info else "YouTube Channel"
        return {
            "success": True,
            "channel_name": channel_display,
            "message": f"Successfully connected as {channel_display}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"OAuth connection error: {str(e)}",
        }

def run_desktop_auth_flow() -> bool:
    """Runs Google OAuth desktop flow for YouTube uploading."""
    res = connect_youtube_oauth()
    return res.get("success", False)

def schedule_upload(
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
    publish_at: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Schedules clip upload to YouTube.
    Adheres strictly to daily upload caps, auto-upload settings, and private status for unaudited apps.
    """
    # 1. Enforce Daily Upload Cap
    allowed, current_count, msg = check_and_increment_upload()
    if not allowed and not dry_run:
        return {
            "success": False,
            "error": msg,
            "daily_count": current_count,
            "note": "YouTube daily upload limit reached.",
        }

    # 2. Check Dry Run or Auto-Upload disabled
    if dry_run or not settings.auto_upload:
        print(f"[DRY RUN / SIMULATION] YouTube Upload:")
        print(f"  Title: {title}")
        print(f"  Description: {description[:80]}...")
        print(f"  Tags: {tags}")
        print(f"  Scheduled for: {publish_at or 'Immediate'}")
        print(f"  File: {video_path}")
        return {
            "success": True,
            "simulated": True,
            "video_id": f"sim_{abs(hash(title)) % 10000000:08d}",
            "title": title,
            "scheduled_time": publish_at,
            "daily_count": current_count,
            "note": "Dry-run / AUTO_UPLOAD is off. Video was not uploaded to YouTube.",
        }

    # 3. Real Upload with Google API
    if not is_authenticated():
        return {
            "success": False,
            "error": "Not authenticated with YouTube. Run 'python run.py youtube-login' first.",
        }

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        youtube = build("youtube", "v3", credentials=creds)

        # Unaudited developer apps upload as private by default per YouTube terms
        status_body: Dict[str, Any] = {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        }
        if publish_at:
            status_body["publishAt"] = publish_at

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": [t.lstrip("#") for t in tags][:15],
                "categoryId": "22",  # People & Blogs
            },
            "status": status_body,
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = request.execute()
        video_id = response.get("id")

        return {
            "success": True,
            "simulated": False,
            "video_id": video_id,
            "title": title,
            "url": f"https://youtu.be/{video_id}",
            "privacy": status_body["privacyStatus"],
            "daily_count": current_count,
            "note": "Upload succeeded. Note: unverified YouTube API projects keep uploads private.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "note": "Upload failed. Check YouTube quota or permissions.",
        }
