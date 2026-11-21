"""Input limits and content validation shared by the HTTP layer."""

import unicodedata

MAX_TITLE_CODE_POINTS = 120
MAX_TEXT_BYTES = 262144
MAX_BODY_BYTES = 1048576
MAX_DOCUMENTS = 500
MAX_INT64 = 2**63 - 1


class ApiError(Exception):
    """An error that maps directly to an HTTP error response."""

    def __init__(self, status, code, message, field=None, headers=None, extra=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.headers = headers or {}
        self.extra = extra or {}

    def body(self):
        err = {"code": self.code, "message": self.message}
        if self.field:
            err["field"] = self.field
        out = {"error": err}
        out.update(self.extra)
        return out


def _invalid(message, field=None):
    return ApiError(400, "invalid_field", message, field=field)


def validate_title(value):
    """Return the trimmed title or raise ApiError."""
    if not isinstance(value, str):
        raise _invalid("Title must be a string.", "title")
    title = value.strip()
    if len(title) < 1:
        raise _invalid("Title must not be empty.", "title")
    if len(title) > MAX_TITLE_CODE_POINTS:
        raise _invalid(
            f"Title must be at most {MAX_TITLE_CODE_POINTS} characters.", "title"
        )
    for ch in title:
        if unicodedata.category(ch) in ("Cc", "Cs"):
            raise _invalid("Title must not contain control characters.", "title")
    return title


def validate_text(value):
    """Return the text unchanged or raise ApiError."""
    if not isinstance(value, str):
        raise _invalid("Text must be a string.", "text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise _invalid("Text must be valid Unicode.", "text") from None
    if len(encoded) > MAX_TEXT_BYTES:
        raise ApiError(
            413,
            "text_too_large",
            f"Text must be at most {MAX_TEXT_BYTES} bytes in UTF-8.",
            field="text",
        )
    if "\x00" in value:
        raise _invalid("Text must not contain NUL characters.", "text")
    return value


def validate_base_revision(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid("base_revision must be an integer.", "base_revision")
    if value < 1 or value > MAX_INT64:
        raise _invalid("base_revision must be at least 1.", "base_revision")
    return value


def validate_payload(obj, update):
    """Validate a create/update body. Returns a dict of cleaned values."""
    if not isinstance(obj, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object.")
    required = ["title", "text"] + (["base_revision"] if update else [])
    for key in obj:
        if key not in required:
            raise _invalid("Unknown field in request body.")
    for key in required:
        if key not in obj:
            raise _invalid(f"Missing field: {key}.", key)
    out = {
        "title": validate_title(obj["title"]),
        "text": validate_text(obj["text"]),
    }
    if update:
        out["base_revision"] = validate_base_revision(obj["base_revision"])
    return out
