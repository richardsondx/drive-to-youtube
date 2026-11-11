"""Tests for drive2yt.metadata: limits and publish rules."""

import pytest

from drive2yt import metadata


def test_snippet_ok():
    snippet = metadata.build_snippet("Hello", "Desc", ["a", "b"], "22", "en")
    assert snippet["title"] == "Hello"
    assert snippet["tags"] == ["a", "b"]
    assert snippet["categoryId"] == "22"
    assert snippet["defaultLanguage"] == "en"


def test_title_required():
    with pytest.raises(ValueError, match="title is required"):
        metadata.build_snippet("   ")


def test_title_too_long():
    with pytest.raises(ValueError, match="at most 100"):
        metadata.build_snippet("x" * 101)


def test_description_too_long():
    with pytest.raises(ValueError, match="at most 5000"):
        metadata.build_snippet("t", "x" * 5001)


def test_category_must_be_numeric():
    with pytest.raises(ValueError, match="must be a number"):
        metadata.build_snippet("t", category_id="People")


def test_tags_too_many():
    with pytest.raises(ValueError, match="at most 30 tags"):
        metadata.parse_tags(",".join(f"t{i}" for i in range(31)))


def test_tags_too_long():
    with pytest.raises(ValueError, match="at most 500 characters"):
        metadata.parse_tags("x" * 501)


def test_status_defaults_unlisted_not_kids():
    status = metadata.build_status()
    assert status["privacyStatus"] == "unlisted"
    assert status["selfDeclaredMadeForKids"] is False
    assert "publishAt" not in status


def test_publish_at_needs_private():
    with pytest.raises(ValueError, match="needs privacy 'private'"):
        metadata.build_status(privacy="public", publish_at="2999-01-01T00:00:00Z")


def test_publish_at_past():
    with pytest.raises(ValueError, match="in the past"):
        metadata.build_status(privacy="private", publish_at="2000-01-01T00:00:00Z")


def test_publish_at_bad_format():
    with pytest.raises(ValueError, match="not an ISO 8601"):
        metadata.build_status(privacy="private", publish_at="next Friday")


def test_publish_at_ok_and_normalized():
    status = metadata.build_status(privacy="private",
                                   publish_at="2999-01-01T12:00:00+02:00")
    assert status["publishAt"] == "2999-01-01T10:00:00Z"


def test_build_body_shape():
    body = metadata.build_body({"title": "t"}, {"privacyStatus": "unlisted"})
    assert body == {"snippet": {"title": "t"}, "status": {"privacyStatus": "unlisted"}}
