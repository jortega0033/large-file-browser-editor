"""Fictional sample log fixture served by GET /api/v1/sample (never stored)."""

SAMPLE_TITLE = "Sample log"
SAMPLE_LINES = 200


def _level(i: int) -> str:
    if i % 25 == 0:
        return "ERROR"
    if i % 10 == 0:
        return "WARN"
    return "INFO"


def sample_line(i: int) -> str:
    s = i - 1
    return (
        f"2026-01-01T{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}Z "
        f"service-{i % 4} {_level(i)} event={i:03d} value={(i * 37) % 101}"
    )


def build_sample_text() -> str:
    return "".join(sample_line(i) + "\n" for i in range(1, SAMPLE_LINES + 1))
