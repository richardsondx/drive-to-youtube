"""Build and validate the YouTube video metadata for an upload.

YouTube limits enforced here, so a bad title or a past publish time fails
before any bytes are uploaded:
- title: 1 to 100 characters
- description: 0 to 5000 characters
- tags: at most 30, at most 500 characters total
- publishAt: must be in the future, and only with privacy "private"
  (YouTube flips a private scheduled video public at publish time).
"""

from __future__ import annotations

from datetime import datetime, timezone

MAX_TITLE_LEN = 100
MAX_DESCRIPTION_LEN = 5000
MAX_TAGS = 30
MAX_TAG_CHARS = 500

PRIVACY_CHOICES = ("private", "unlisted", "public")


def parse_publish_at(value: str) -> str:
    """Parse an ISO 8601 time into a UTC RFC 3339 string. Raises ValueError."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"publish-at {value!r} is not an ISO 8601 time, "
            "for example 2026-11-15T14:00:00Z"
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt <= datetime.now(timezone.utc):
        raise ValueError(f"publish-at {value!r} is in the past")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    tags = [t.strip() for t in value.split(",") if t.strip()]
    if len(tags) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags, got {len(tags)}")
    total = sum(len(t) for t in tags)
    if total > MAX_TAG_CHARS:
        raise ValueError(f"tags total at most {MAX_TAG_CHARS} characters, got {total}")
    return tags


def build_snippet(title: str, description: str = "", tags: list[str] | None = None,
                  category_id: str = "22", language: str | None = None) -> dict:
    if not title or not title.strip():
        raise ValueError("title is required")
    if len(title) > MAX_TITLE_LEN:
        raise ValueError(f"title at most {MAX_TITLE_LEN} characters, got {len(title)}")
    if len(description) > MAX_DESCRIPTION_LEN:
        raise ValueError(
            f"description at most {MAX_DESCRIPTION_LEN} characters, "
            f"got {len(description)}"
        )
    if not category_id.isdigit():
        raise ValueError(f"category-id {category_id!r} must be a number, for example 22")
    snippet: dict = {
        "title": title,
        "description": description,
        "tags": tags or [],
        "categoryId": category_id,
    }
    if language:
        snippet["defaultLanguage"] = language
    return snippet


def build_status(privacy: str = "unlisted", publish_at: str | None = None,
                 made_for_kids: bool = False) -> dict:
    if privacy not in PRIVACY_CHOICES:
        raise ValueError(f"privacy must be one of {', '.join(PRIVACY_CHOICES)}")
    status: dict = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at is not None:
        if privacy != "private":
            raise ValueError(
                "publish-at needs privacy 'private': YouTube flips a private "
                "scheduled video public at publish time"
            )
        status["publishAt"] = parse_publish_at(publish_at)
    return status


def build_body(snippet: dict, status: dict) -> dict:
    return {"snippet": snippet, "status": status}
