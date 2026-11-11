"""Google OAuth for drive2yt.

The tool uses a desktop OAuth flow, because YouTube uploads belong to a
channel, and service accounts have no channel. The user creates one OAuth
client in Google Cloud (Desktop app), downloads its client_secret.json, and
runs `drive2yt auth` once. The refresh token is stored locally and reused.

Scopes:
- drive.readonly: find and download the video from Drive.
- youtube: upload, thumbnail, playlist, and read-back. The single full
  YouTube scope covers all four; videos.insert alone needs youtube.upload,
  but playlistItems.insert needs the full scope, so one scope keeps it simple.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "drive2yt"
TOKEN_FILENAME = "token.json"
CLIENT_SECRETS_FILENAME = "client_secret.json"


def config_dir(explicit: str | None = None) -> Path:
    """Return the config dir, honoring --config-dir and DRIVE2YT_CONFIG_DIR."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("DRIVE2YT_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_DIR


def token_path(explicit: str | None = None) -> Path:
    return config_dir(explicit) / TOKEN_FILENAME


def client_secrets_path(explicit: str | None = None) -> Path:
    return config_dir(explicit) / CLIENT_SECRETS_FILENAME


def load_credentials(config: str | None = None) -> Credentials | None:
    """Load stored credentials, refreshing them if expired. None if absent."""
    path = token_path(config)
    if not path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds, config)
        return creds
    return None


def save_credentials(creds: Credentials, config: str | None = None) -> Path:
    path = token_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    return path


def run_auth_flow(client_secrets: str | None = None,
                  config: str | None = None) -> Credentials:
    """Run the desktop OAuth flow and store the token. Returns credentials."""
    secrets = Path(client_secrets).expanduser() if client_secrets else client_secrets_path(config)
    if not secrets.exists():
        raise FileNotFoundError(
            f"OAuth client secrets not found at {secrets}.\n"
            "Create a Desktop-app OAuth client in Google Cloud, download its\n"
            "client_secret.json, and place it there. See README.md, Setup."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0)
    save_credentials(creds, config)
    return creds


def get_credentials(client_secrets: str | None = None,
                    config: str | None = None) -> Credentials:
    """Return valid credentials, running the auth flow only if needed."""
    creds = load_credentials(config)
    if creds is not None:
        return creds
    return run_auth_flow(client_secrets, config)


def build_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def build_youtube_service(creds: Credentials):
    return build("youtube", "v3", credentials=creds)


def describe_account(drive_service, youtube_service) -> dict:
    """Return the Drive user email and the YouTube channel title, if known."""
    info: dict = {}
    try:
        about = drive_service.about().get(fields="user").execute()
        info["drive_email"] = about.get("user", {}).get("emailAddress")
    except Exception:
        info["drive_email"] = None
    try:
        channels = youtube_service.channels().list(part="snippet", mine=True).execute()
        items = channels.get("items", [])
        info["channel_title"] = items[0]["snippet"]["title"] if items else None
    except Exception:
        info["channel_title"] = None
    return info


def describe_account_json(drive_service, youtube_service) -> str:
    return json.dumps(describe_account(drive_service, youtube_service), indent=2)
