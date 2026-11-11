"""Tests for drive2yt.cli: parsing and dry-run validation."""

import pytest

from drive2yt.cli import build_parser, main


def test_upload_requires_title():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["upload", "--file", "x.mp4"])


def test_upload_defaults():
    args = build_parser().parse_args(
        ["upload", "--file", "x.mp4", "--title", "Hello"])
    assert args.privacy == "unlisted"
    assert args.category_id == "22"
    assert args.dry_run is False
    assert args.made_for_kids is False


def test_upload_rejects_bad_privacy():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["upload", "--file", "x.mp4", "--title", "t",
                           "--privacy", "friends"])


def test_upload_needs_a_source(capsys):
    code = main(["upload", "--title", "t"])
    assert code == 2
    assert "give a source" in capsys.readouterr().err


def test_upload_dry_run_bad_title(capsys):
    code = main(["upload", "--file", "x.mp4", "--title", "x" * 101, "--dry-run"])
    assert code == 1
    assert "at most 100" in capsys.readouterr().err


def test_upload_dry_run_prints_body(capsys):
    code = main(["upload", "--file", "x.mp4", "--title", "Hello",
                 "--description", "Desc", "--tags", "a,b", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"title": "Hello"' in out
    assert '"privacyStatus": "unlisted"' in out


def test_auth_and_find_parse():
    assert build_parser().parse_args(["auth"]).command == "auth"
    find = build_parser().parse_args(["find", "--drive-name", "v.mp4"])
    assert find.drive_name == "v.mp4"
