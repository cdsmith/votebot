import abc
from typing import Any, Callable, Optional
import copy
import math
import discord
import db
from i18n import _, LocalizedView
from layout import action_rows


class Ballot(abc.ABC):
    def __init__(
        self,
        election_id: int,
        candidates: list[str],
        ballot_id: int | None = None,
    ):
        self.ballot_id: int | None = ballot_id
        self.election_id: int = election_id
        self.page: int = 0
        self.visited_pages: set[int] = set()
        self.candidates = candidates  # Already shuffled when created
        self.session_id: int = 0  # Will be set when ballot is sent
        self.current_view: discord.ui.View | None = None  # Most recently rendered view

        # Store ballot type for serialization
        self.ballot_type = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def copy(self) -> "Ballot":
        """Return a duplicate Ballot with the same data as this one."""
        cls = self.__class__
        new = cls.__new__(cls)
        memo = {id(self): new}
        for key, value in self.__dict__.items():
            setattr(new, key, copy.deepcopy(value, memo))
        new.current_view = None
        new.page = 0
        new.ballot_id = None  # New copy gets a new ID
        return new

    def total_pages(self) -> int:
        per_page = self.candidates_per_page()
        return math.ceil(len(self.candidates) / per_page) if per_page else 1

    def candidates_on_page(self) -> list[str]:
        per_page = self.candidates_per_page()
        if per_page:
            start = self.page * per_page
            end = start + per_page
            return self.candidates[start:end]
        else:
            return self.candidates

    def render_interim(self, session_id: int) -> dict[str, Any]:
        class NextPageButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    style=discord.ButtonStyle.primary, label=_("Next Page")
                )

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    if self.page < self.total_pages() - 1:
                        self.page += 1
                    else:
                        self.page = 0

                await self.modify(modification, interaction, session_id)

        class PrevPageButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    style=discord.ButtonStyle.primary, label=_("Prev Page")
                )

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    if self.page > 0:
                        self.page -= 1
                    else:
                        self.page = self.total_pages() - 1

                await self.modify(modification, interaction, session_id)

        class SubmitButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    style=discord.ButtonStyle.green, label=_("Submit Vote")
                )
                inner_self.election_id = self.election_id
                inner_self.session_id_val = session_id

            async def callback(inner_self, interaction: discord.Interaction):
                from election import load_election_from_db

                election = load_election_from_db(inner_self.election_id)
                if await election.check_session(interaction, inner_self.session_id_val):
                    await election.submit_ballot(interaction)
                inner_self.view.stop()

        class ResetButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    style=discord.ButtonStyle.danger, label=_("Start Over")
                )

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    self.clear()
                    self.visited_pages.clear()
                    self.page = 0

                await self.modify(modification, interaction, session_id)

        self.visited_pages.add(self.page)

        # Load election for title
        from election import load_election_from_db

        election = load_election_from_db(self.election_id)

        container = discord.ui.Container(
            discord.ui.TextDisplay(f"## {election.title}"),
            discord.ui.TextDisplay(self.instructions()),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "**{}**\n{}".format(_("Current vote"), self.to_markdown())
            ),
        )
        for row in action_rows(self.get_items(self.candidates_on_page(), session_id)):
            container.add_item(row)
        if self.total_pages() > 1:
            container.add_item(
                discord.ui.TextDisplay(
                    "-# "
                    + _("Page {page}/{total}").format(
                        page=self.page + 1, total=self.total_pages()
                    )
                )
            )

        buttons = []
        if self.page > 0:
            buttons.append(PrevPageButton())
        if self.submittable() and len(self.visited_pages) >= self.total_pages():
            buttons.append(SubmitButton())
        if self.page < self.total_pages() - 1:
            buttons.append(NextPageButton())
        buttons.append(ResetButton())

        # Ballots stay usable for an hour of inactivity.  Views replaced by an
        # interaction are stopped right away; this timeout cleans up the views
        # of abandoned ballots.
        view = LocalizedView(timeout=3600)
        self.current_view = view
        view.add_item(container)
        view.add_item(discord.ui.ActionRow(*buttons))
        return {"view": view}

    async def modify(
        self,
        modification: Callable[[], None],
        interaction: discord.Interaction,
        session_id: int,
    ) -> None:
        from election import load_election_from_db

        election = load_election_from_db(self.election_id)
        if not election:
            return

        # Either way, the message's old view is replaced or removed.
        old_view = self.current_view
        if await election.check_session(interaction, session_id):
            modification()
            # Save modified ballot to database
            db.save_ballot(
                self, self.election_id, interaction.user.id, is_submitted=False
            )
            await interaction.response.edit_message(**self.render_interim(session_id))
        if old_view:
            old_view.stop()

    def render_submitted(self) -> dict[str, Any]:
        view = LocalizedView(timeout=None)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("## " + _("Vote Submitted")),
                discord.ui.TextDisplay(_("Your vote has been submitted.")),
                discord.ui.TextDisplay(
                    "**{}**\n{}".format(_("Your ballot:"), self.to_markdown())
                ),
            )
        )
        return {"view": view}

    @abc.abstractmethod
    def instructions(self) -> str:
        """Return instructions for filling out the ballot."""
        pass

    @abc.abstractmethod
    def candidates_per_page(self) -> Optional[int]:
        """How many candidates can fit on a page.  If None, there is one page for all candidates."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear all votes from the ballot."""
        pass

    @abc.abstractmethod
    def get_items(
        self, candidates: list[str], session_id: int
    ) -> list[discord.ui.Item]:
        """Return a list of discord.Item objects for a page of candidates."""
        pass

    @abc.abstractmethod
    def submittable(self) -> bool:
        """Determines if the ballot is complete enough to submit."""
        pass

    @abc.abstractmethod
    def to_markdown(self) -> str:
        """Return a ballot choice in markdown."""
        pass

    @abc.abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize ballot to dictionary for database storage.

        Returns dict with:
        - Ballot-specific voting data (votes/ranking/ratings)
        - page, visited_pages, candidates (UI state)
        - session_id
        """
        pass

    @classmethod
    @abc.abstractmethod
    def from_dict(cls, ballot_dict: dict[str, Any], election_id: int) -> "Ballot":
        """Reconstruct ballot from database dictionary."""
        pass
