"""Find and download a video file from Google Drive."""

from __future__ import annotations

import io
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

DOWNLOAD_CHUNK = 8 * 1024 * 1024


def _escape_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_file(service, file_id: str | None = None,
              name: str | None = None) -> dict:
    """Return {'id', 'name', 'mimeType', 'size'} for one Drive video file."""
    if file_id:
        found = service.files().get(
            fileId=file_id, fields="id,name,mimeType,size").execute()
        return found
    if name:
        query = (
            f"name = '{_escape_query_value(name)}' "
            "and mimeType contains 'video/' and trashed = false"
        )
        result = service.files().list(
            q=query, fields="files(id,name,mimeType,size)",
            pageSize=10).execute()
        files = result.get("files", [])
        if not files:
            raise LookupError(f"no video named {name!r} found in Drive")
        if len(files) > 1:
            listing = ", ".join(f"{f['name']} ({f['id']})" for f in files)
            raise LookupError(
                f"more than one video named {name!r}: {listing}. "
                "Use --drive-id to pick one."
            )
        return files[0]
    raise ValueError("give --drive-id or --drive-name")


def download_file(service, file_id: str, dest: Path,
                  progress=None) -> Path:
    """Download a Drive file with a resumable, chunked download."""
    request = service.files().get_media(fileId=file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request, chunksize=DOWNLOAD_CHUNK)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if progress is not None and status is not None:
                progress(int(status.progress() * 100))
    return dest
