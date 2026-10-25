from datetime import UTC, datetime


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to timezone-aware UTC.

    * Naive values (no offset supplied by the client, or read back from SQLite)
      are interpreted as UTC.
    * Aware values are converted to UTC so every stored timestamp uses one
      reference and comparisons/sorting/filtering are consistent.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
