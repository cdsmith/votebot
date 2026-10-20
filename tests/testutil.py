import discord

from text_utils import LAYOUT_COMPONENT_LIMIT, LAYOUT_TEXT_LIMIT


class PrefillBallot:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def texts(view: discord.ui.LayoutView) -> list[str]:
    """The text shown in a Components V2 view."""
    return [
        item.content
        for item in view.walk_children()
        if isinstance(item, discord.ui.TextDisplay)
    ]


def labels(view: discord.ui.LayoutView) -> list[str]:
    """The labels and placeholders of a view's buttons and selects."""
    return [
        getattr(item, "label", None) or getattr(item, "placeholder", None)
        for item in view.walk_children()
        if isinstance(item, (discord.ui.Button, discord.ui.Select))
    ]


def assert_fits(view: discord.ui.LayoutView):
    """Check a view against Discord's limits for Components V2 messages."""
    assert view.total_children_count <= LAYOUT_COMPONENT_LIMIT
    assert view.content_length() <= LAYOUT_TEXT_LIMIT
