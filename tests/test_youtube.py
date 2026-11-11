"""Tests for drive2yt.youtube: resumable upload with retries, mocked."""

from unittest import mock

import pytest
from googleapiclient.errors import HttpError

from drive2yt import youtube


class _FakeResponse:
    def __init__(self, status, reason="error"):
        self.status = status
        self.reason = reason


class _FakeRequest:
    """Mimics the request object returned by videos().insert()."""

    def __init__(self, outcomes):
        # outcomes: list of ("error", status) or ("chunk", progress, response)
        self._outcomes = list(outcomes)
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        kind = self._outcomes.pop(0)
        if kind[0] == "error":
            raise HttpError(_FakeResponse(kind[1]), b"boom")
        status = mock.Mock()
        status.progress.return_value = kind[1]
        return status, kind[2]


class _FakeVideos:
    def __init__(self, request):
        self._request = request
        self.insert_kwargs = None

    def insert(self, **kwargs):
        self.insert_kwargs = kwargs
        return self._request


class _FakeService:
    def __init__(self, request):
        self._videos = _FakeVideos(request)

    def videos(self):
        return self._videos


def _upload_with(request, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 1024)
    service = _FakeService(request)
    body = {"snippet": {"title": "t"}, "status": {"privacyStatus": "unlisted"}}
    return youtube.upload_video(service, video, body), service


def test_upload_returns_video_id(tmp_path):
    request = _FakeRequest([("chunk", 0.5, None), ("chunk", 1.0, {"id": "abc123"})])
    video_id, service = _upload_with(request, tmp_path)
    assert video_id == "abc123"
    assert service._videos.insert_kwargs["body"]["snippet"]["title"] == "t"


def test_upload_retries_server_error_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    request = _FakeRequest([("error", 503), ("error", 500),
                            ("chunk", 1.0, {"id": "retry-ok"})])
    video_id, _ = _upload_with(request, tmp_path)
    assert video_id == "retry-ok"
    assert request.calls == 3


def test_upload_gives_up_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    request = _FakeRequest([("error", 503)] * 12)
    with pytest.raises(HttpError):
        _upload_with(request, tmp_path)
    assert request.calls == youtube.MAX_RETRIES + 1


def test_upload_does_not_retry_client_error(tmp_path):
    request = _FakeRequest([("error", 400)])
    with pytest.raises(HttpError):
        _upload_with(request, tmp_path)
    assert request.calls == 1


def test_upload_without_id_raises(tmp_path):
    request = _FakeRequest([("chunk", 1.0, {})])
    with pytest.raises(RuntimeError, match="no video id"):
        _upload_with(request, tmp_path)


def test_watch_url():
    assert youtube.watch_url("abc123") == "https://youtu.be/abc123"
