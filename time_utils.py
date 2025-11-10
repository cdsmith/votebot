"""Utilities for parsing and handling time durations and timestamps."""

import re
import time
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta


# Regex pattern for parsing duration strings like "2d", "3h30m", "1w2d"
_DURATION_REGEX = re.compile(
    r"((?P<years>\d+)\s*(?:years?|Y|y)\s*)?"
    r"((?P<months>\d+)\s*(?:months?|M)\s*)?"
    r"((?P<weeks>\d+)\s*(?:weeks?|W|w)\s*)?"
    r"((?P<days>\d+)\s*(?:days?|D|d)\s*)?"
    r"((?P<hours>\d+)\s*(?:hours?|H|h)\s*)?"
    r"((?P<minutes>\d+)\s*(?:minutes?|m)\s*)?"
    r"((?P<seconds>\d+)\s*(?:seconds?|S|s))?"
)


def parse_duration_string(duration_str: str) -> relativedelta | None:
    """
    Parse a duration string into a relativedelta object.

    Supports formats like:
    - 2d (2 days)
    - 3h30m (3 hours 30 minutes)
    - 1w2d (1 week 2 days)
    - 1y6m (1 year 6 months)

    Returns None if parsing fails.
    """
    duration_str = duration_str.strip()
    match = _DURATION_REGEX.fullmatch(duration_str)

    if not match:
        return None

    duration_dict = {k: int(v) for k, v in match.groupdict().items() if v is not None}

    if not duration_dict:
        return None

    return relativedelta(**duration_dict)


def parse_absolute_datetime(datetime_str: str) -> datetime | None:
    """
    Parse an absolute datetime string into a timezone-aware datetime.

    Supports ISO format and many natural formats:
    - 2025-12-25 14:30
    - 2025-12-25T14:30:00
    - December 25, 2025 2:30 PM

    Returns None if parsing fails.
    """
    try:
        dt = dateutil_parser.parse(datetime_str, fuzzy=False)
        # If no timezone info, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, dateutil_parser.ParserError):
        return None


def parse_time_input(time_str: str) -> int | None:
    """
    Parse a time input string into a Unix timestamp (UTC).

    Tries to parse as:
    1. Relative duration (2d, 3h30m, etc.) - interpreted as time from now
    2. Absolute datetime (2025-12-25 14:30, etc.)

    Returns Unix timestamp (seconds since epoch) or None if parsing fails.
    """
    time_str = time_str.strip()

    # Try parsing as duration first
    duration = parse_duration_string(time_str)
    if duration:
        future_time = datetime.now(timezone.utc) + duration
        return int(future_time.timestamp())

    # Try parsing as absolute datetime
    dt = parse_absolute_datetime(time_str)
    if dt:
        return int(dt.timestamp())

    return None


def validate_time_input(time_str: str) -> tuple[int | None, str | None]:
    """
    Validate and parse a time input string.

    Returns:
        tuple: (timestamp, error_message)
        - If valid: (timestamp, None)
        - If invalid: (None, error_message)
    """
    if not time_str or not time_str.strip():
        return (None, None)  # Empty is valid (no end time)

    timestamp = parse_time_input(time_str)

    if timestamp is None:
        return (
            None,
            "Unable to parse time. Try formats like: 2d, 3h30m, 1w, or 2025-12-25 14:30",
        )

    current_time = int(time.time())
    if timestamp <= current_time:
        return (None, "End time must be in the future")

    return (timestamp, None)


def format_timestamp_discord(
    timestamp: int | None, include_relative: bool = True
) -> str:
    """
    Format a Unix timestamp for Discord display.

    Args:
        timestamp: Unix timestamp in seconds
        include_relative: If True, shows both absolute and relative times.
                         If False, shows only absolute time.

    Returns:
        - With relative: "January 13, 2025 3:30 PM (in 2 hours)"
        - Without relative: "January 13, 2025 3:30 PM"
        - If None: "Manual (no scheduled end time)"
    """
    if timestamp is None:
        return "When manually ended"

    if include_relative:
        return f"<t:{timestamp}:f> (<t:{timestamp}:R>)"
    else:
        return f"<t:{timestamp}:f>"


def humanize_duration(seconds: int) -> str:
    """
    Convert a duration in seconds to a human-readable string.

    Examples:
    - 3600 -> "1 hour"
    - 7200 -> "2 hours"
    - 90 -> "1 minute"
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    if hours < 24:
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"

    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours == 0:
        return f"{days} day{'s' if days != 1 else ''}"
    return f"{days} day{'s' if days != 1 else ''} {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
