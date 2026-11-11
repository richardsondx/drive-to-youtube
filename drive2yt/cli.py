"""Command line for drive2yt.

Commands:
  drive2yt auth    sign in once with Google, store the token, show the account
  drive2yt find    look up a video in Drive by id or name, print its details
  drive2yt upload  download a video from Drive (or take a local file) and
                   upload it to YouTube with title, description, privacy,
                   schedule, thumbnail, and playlist

Uploads default to unlisted, so nothing goes public by accident. A scheduled
upload needs --privacy private plus --publish-at.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import __version__, auth, drive, metadata, youtube


def _progress(label: str):
    last = {"value": -1}

    def show(percent: int) -> None:
        if percent != last["value"]:
            last["value"] = percent
            print(f"{label}: {percent}%", flush=True)

    return show


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--client-secrets", default=None,
                        help="path to client_secret.json (default: ~/.config/drive2yt/client_secret.json)")
    parser.add_argument("--config-dir", default=None,
                        help="config dir holding token.json (default: ~/.config/drive2yt)")


def _cmd_auth(args: argparse.Namespace) -> int:
    creds = auth.run_auth_flow(args.client_secrets, args.config_dir)
    drive_service = auth.build_drive_service(creds)
    youtube_service = auth.build_youtube_service(creds)
    info = auth.describe_account(drive_service, youtube_service)
    print(f"Signed in. Token saved to {auth.token_path(args.config_dir)}")
    print(f"Drive account: {info.get('drive_email') or 'unknown'}")
    print(f"YouTube channel: {info.get('channel_title') or 'unknown'}")
    print("Uploads will go to that channel.")
    return 0


def _cmd_find(args: argparse.Namespace) -> int:
    creds = auth.get_credentials(args.client_secrets, args.config_dir)
    service = auth.build_drive_service(creds)
    found = drive.find_file(service, file_id=args.drive_id, name=args.drive_name)
    print(json.dumps(found, indent=2))
    return 0


def _resolve_source_file(args: argparse.Namespace, drive_service) -> tuple[Path, Path | None]:
    """Return (local video path, temp dir to clean up or None)."""
    if args.file:
        path = Path(args.file).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"local file not found: {path}")
        return path, None
    found = drive.find_file(drive_service, file_id=args.drive_id, name=args.drive_name)
    if args.download_dir:
        dest_dir = Path(args.download_dir).expanduser()
    else:
        dest_dir = Path(tempfile.mkdtemp(prefix="drive2yt-"))
    dest = dest_dir / found["name"]
    print(f"Downloading from Drive: {found['name']} ({found.get('size', '?')} bytes)")
    drive.download_file(drive_service, found["id"], dest,
                        progress=_progress("Download"))
    cleanup = None if args.keep_download else dest_dir
    return dest, cleanup


def _cmd_upload(args: argparse.Namespace) -> int:
    if not args.file and not args.drive_id and not args.drive_name:
        print("error: give a source: --file, --drive-id, or --drive-name",
              file=sys.stderr)
        return 2
    tags = metadata.parse_tags(args.tags)
    snippet = metadata.build_snippet(
        title=args.title, description=args.description or "",
        tags=tags, category_id=args.category_id, language=args.language)
    status = metadata.build_status(
        privacy=args.privacy, publish_at=args.publish_at,
        made_for_kids=args.made_for_kids)
    body = metadata.build_body(snippet, status)

    if args.dry_run:
        print(json.dumps({"source": args.file or args.drive_id or args.drive_name,
                          "body": body}, indent=2))
        return 0

    creds = auth.get_credentials(args.client_secrets, args.config_dir)
    drive_service = auth.build_drive_service(creds)
    youtube_service = auth.build_youtube_service(creds)

    video_path, cleanup_dir = _resolve_source_file(args, drive_service)
    try:
        print(f"Uploading: {video_path.name}")
        video_id = youtube.upload_video(
            youtube_service, video_path, body,
            notify_subscribers=args.notify_subscribers,
            progress=_progress("Upload"))
        print(f"Uploaded: {youtube.watch_url(video_id)} (id {video_id})")
        if args.thumbnail:
            thumb = Path(args.thumbnail).expanduser()
            youtube.set_thumbnail(youtube_service, video_id, thumb)
            print("Thumbnail set.")
        if args.playlist:
            youtube.add_to_playlist(youtube_service, video_id, args.playlist)
            print(f"Added to playlist {args.playlist}.")
        verified = youtube.verify_video(youtube_service, video_id)
        if verified is None:
            print("Warning: the video did not read back yet. Check YouTube Studio.",
                  file=sys.stderr)
        else:
            state = verified.get("status", {})
            print(f"Verified: privacy {state.get('privacyStatus')}, "
                  f"upload status {state.get('uploadStatus')}.")
    finally:
        if cleanup_dir is not None:
            import shutil
            shutil.rmtree(cleanup_dir, ignore_errors=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drive2yt",
        description="Upload a video from Google Drive (or a local file) to YouTube.")
    parser.add_argument("--version", action="version", version=f"drive2yt {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_auth = sub.add_parser("auth", help="sign in with Google and store the token")
    _add_common(p_auth)
    p_auth.set_defaults(func=_cmd_auth)

    p_find = sub.add_parser("find", help="look up a video in Drive by id or name")
    _add_common(p_find)
    p_find.add_argument("--drive-id", default=None)
    p_find.add_argument("--drive-name", default=None)
    p_find.set_defaults(func=_cmd_find)

    p_up = sub.add_parser("upload", help="upload a video to YouTube")
    _add_common(p_up)
    p_up.add_argument("--file", default=None,
                      help="local video file (instead of a Drive file)")
    p_up.add_argument("--drive-id", default=None, help="Drive file id")
    p_up.add_argument("--drive-name", default=None, help="Drive file name")
    p_up.add_argument("--title", required=True, help="video title, max 100 characters")
    p_up.add_argument("--description", default="", help="video description, max 5000 characters")
    p_up.add_argument("--tags", default=None, help="comma-separated tags, max 30")
    p_up.add_argument("--category-id", default="22",
                      help="YouTube category id (default 22, People & Blogs)")
    p_up.add_argument("--language", default=None, help="video language, for example en")
    p_up.add_argument("--privacy", default="unlisted",
                      choices=metadata.PRIVACY_CHOICES)
    p_up.add_argument("--publish-at", default=None,
                      help="ISO 8601 publish time, for example 2026-11-15T14:00:00Z (needs --privacy private)")
    p_up.add_argument("--made-for-kids", action="store_true",
                      help="declare the video made for kids")
    p_up.add_argument("--thumbnail", default=None, help="local image file for the thumbnail")
    p_up.add_argument("--playlist", default=None, help="playlist id to add the video to")
    p_up.add_argument("--notify-subscribers", action="store_true",
                      help="notify subscribers on publish")
    p_up.add_argument("--dry-run", action="store_true",
                      help="resolve and print the metadata without uploading")
    p_up.add_argument("--download-dir", default=None,
                      help="where to put the Drive download (default: a temp dir)")
    p_up.add_argument("--keep-download", action="store_true",
                      help="keep the downloaded file instead of deleting it")
    p_up.set_defaults(func=_cmd_upload)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, LookupError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - surface API errors plainly
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
