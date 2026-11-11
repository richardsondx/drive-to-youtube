"""Upload a video to YouTube, then set its thumbnail, playlist, and verify.

The upload is resumable with retries, following Google's documented pattern:
retry on 500/502/503/504 and on connection errors, with exponential backoff,
up to 10 attempts. A failed upload that already created a video still prints
the video id when the API returns one.
"""

from __future__ import annotations

import http.client
import time
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

UPLOAD_CHUNK = 8 * 1024 * 1024
RETRIABLE_STATUS = (500, 502, 503, 504)
MAX_RETRIES = 10


def _is_retriable(error: Exception) -> bool:
    if isinstance(error, HttpError):
        return error.resp.status in RETRIABLE_STATUS
    return isinstance(error, (OSError, http.client.HTTPException))


def upload_video(service, file_path: Path, body: dict,
                 notify_subscribers: bool = False,
                 progress=None) -> str:
    """Upload a local video file. Returns the YouTube video id."""
    media = MediaFileUpload(str(file_path), mimetype="video/*",
                            resumable=True, chunksize=UPLOAD_CHUNK)
    request = service.videos().insert(
        part="snippet,status", body=body, media_body=media,
        notifySubscribers=notify_subscribers)
    attempt = 0
    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if progress is not None and status is not None:
                progress(int(status.progress() * 100))
        except Exception as exc:  # noqa: BLE001 - retriable errors are broad
            if not _is_retriable(exc):
                raise
            attempt += 1
            if attempt > MAX_RETRIES:
                raise
            time.sleep(2 ** attempt)
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"upload finished but no video id came back: {response}")
    return video_id


def set_thumbnail(service, video_id: str, image_path: Path) -> None:
    media = MediaFileUpload(str(image_path), mimetype="image/*", resumable=False)
    service.thumbnails().set(videoId=video_id, media_body=media).execute()


def add_to_playlist(service, video_id: str, playlist_id: str) -> None:
    service.playlistItems().insert(
        part="snippet",
        body={"snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }}).execute()


def verify_video(service, video_id: str) -> dict | None:
    """Read the video back. Returns the video resource, or None if missing."""
    result = service.videos().list(
        part="snippet,status", id=video_id).execute()
    items = result.get("items", [])
    return items[0] if items else None


def watch_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"
