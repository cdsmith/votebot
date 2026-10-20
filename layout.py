"""Helpers for building the bot's Components V2 messages."""

import discord

from i18n import LocalizedView
from text_utils import LAYOUT_TEXT_LIMIT, split_text

# Room left in each message for headings and footers around split text
_TEXT_MARGIN = 200


def notice(text: str) -> discord.ui.LayoutView:
    """A message that just shows some text.  Messages using Components V2 can
    only be edited into other V2 messages, so this replaces plain text."""
    view = LocalizedView(timeout=None)
    view.add_item(discord.ui.TextDisplay(text))
    return view


def action_rows(items: list[discord.ui.Item]) -> list[discord.ui.ActionRow]:
    """Lay out buttons and selects in rows: each select on its own row, and
    buttons five to a row, as Discord allows."""
    rows = []
    buttons: list[discord.ui.Item] = []
    for item in items:
        if isinstance(item, discord.ui.Button):
            if len(buttons) == 5:
                rows.append(discord.ui.ActionRow(*buttons))
                buttons = []
            buttons.append(item)
        else:
            if buttons:
                rows.append(discord.ui.ActionRow(*buttons))
                buttons = []
            rows.append(discord.ui.ActionRow(item))
    if buttons:
        rows.append(discord.ui.ActionRow(*buttons))
    return rows


def pack_text(blocks: list[str], first_message_used: int = 0) -> list[list[str]]:
    """Group blocks of text into messages that fit Discord's limit on text per
    message, splitting blocks that are too long on their own.

    first_message_used is text already taken up in the first message."""
    limit = LAYOUT_TEXT_LIMIT - _TEXT_MARGIN
    pieces = [piece for block in blocks for piece in split_text(block, limit)]
    messages: list[list[str]] = [[]]
    used = first_message_used
    for piece in pieces:
        if (messages[-1] or used) and used + len(piece) > limit:
            messages.append([])
            used = 0
        messages[-1].append(piece)
        used += len(piece)
    return messages
