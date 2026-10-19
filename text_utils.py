"""Utilities for fitting text into Discord's message and embed size limits."""

import discord

# Discord API limits
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_LIMIT = 1024
EMBED_TOTAL_LIMIT = 6000
EMBEDS_PER_MESSAGE = 10
MESSAGE_CONTENT_LIMIT = 2000


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


def add_long_field(embed: discord.Embed, name: str, value: str) -> discord.Embed:
    """Add a field to an embed, continuing into additional untitled fields if
    the value is too long for one field."""
    for i, chunk in enumerate(split_text(value, EMBED_FIELD_LIMIT)):
        embed.add_field(name=name if i == 0 else "​", value=chunk, inline=False)
    return embed


def group_embeds(embeds: list[discord.Embed]) -> list[list[discord.Embed]]:
    """Group embeds into batches that can each be sent in a single message."""
    groups: list[list[discord.Embed]] = []
    total = 0
    for embed in embeds:
        size = len(embed)
        if (
            groups
            and len(groups[-1]) < EMBEDS_PER_MESSAGE
            and total + size <= EMBED_TOTAL_LIMIT
        ):
            groups[-1].append(embed)
            total += size
        else:
            groups.append([embed])
            total = size
    return groups
