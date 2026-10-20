"""Utilities for fitting text into Discord's message size limits."""

# Discord API limits
LAYOUT_TEXT_LIMIT = 4000  # Text across a Components V2 message
LAYOUT_COMPONENT_LIMIT = 40  # Components in a Components V2 message, nested included
MESSAGE_CONTENT_LIMIT = 2000
SELECT_OPTION_LIMIT = 100  # Label and description of a select option
SELECT_PLACEHOLDER_LIMIT = 150


def truncate(text: str, limit: int) -> str:
    """Truncate text to at most limit characters, marking truncation with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most limit characters, breaking at newlines
    where possible."""
    chunks = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if not current:
            current = line
        elif len(current) + 1 + len(line) <= limit:
            current += "\n" + line
        else:
            chunks.append(current)
            current = line
    if current or not chunks:
        chunks.append(current)
    return chunks
