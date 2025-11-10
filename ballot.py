import abc
from typing import Any, Callable, Optional
import copy
import math
import discord
import random
import db


class Ballot(abc.ABC):
    def __init__(
        self,
        election_id: int,
        candidates: list[str],
        instructions: str,
        ballot_id: int | None = None,
    ):
        self.ballot_id: int | None = ballot_id
        self.election_id: int = election_id
        self.instructions: str = instructions
        self.page: int = 0
        self.visited_pages: set[int] = set()
        self.candidates = candidates  # Already shuffled when created
        self.session_id: int = 0  # Will be set when ballot is sent

        # Store ballot type for serialization
        self.ballot_type = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def copy(self) -> "Ballot":
        """Return a duplicate Ballot with the same data as this one."""
        cls = self.__class__
        new = cls.__new__(cls)
        memo = {id(self): new}
        for key, value in self.__dict__.items():
            setattr(new, key, copy.deepcopy(value, memo))
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
            def __init__(_):
                super().__init__(
                    style=discord.ButtonStyle.primary, label="Next Page", row=4
                )

            async def callback(_, interaction: discord.Interaction):
                def modification():
                    if self.page < self.total_pages() - 1:
                        self.page += 1
                    else:
                        self.page = 0

                await self.modify(modification, interaction, session_id)

        class PrevPageButton(discord.ui.Button):
            def __init__(_):
                super().__init__(
                    style=discord.ButtonStyle.primary, label="Prev Page", row=4
                )

            async def callback(_, interaction: discord.Interaction):
                def modification():
                    if self.page > 0:
                        self.page -= 1
                    else:
                        self.page = self.total_pages() - 1

                await self.modify(modification, interaction, session_id)

        class SubmitButton(discord.ui.Button):
            def __init__(_):
                super().__init__(
                    style=discord.ButtonStyle.green, label="Submit Vote", row=4
                )
                _.election_id = self.election_id
                _.session_id_val = session_id

            async def callback(_, interaction: discord.Interaction):
                from election import load_election_from_db
                election = load_election_from_db(_.election_id)
                if await election.check_session(interaction, _.session_id_val):
                    await election.submit_ballot(interaction)

        class ResetButton(discord.ui.Button):
            def __init__(_):
                super().__init__(
                    style=discord.ButtonStyle.danger, label="Start Over", row=4
                )

            async def callback(_, interaction: discord.Interaction):
                def modification():
                    self.clear()
                    self.visited_pages.clear()
                    self.page = 0

                await self.modify(modification, interaction, session_id)

        self.visited_pages.add(self.page)
        view = discord.ui.View()
        for item in self.get_items(self.candidates_on_page(), session_id):
            view.add_item(item)
        if self.page > 0:
            view.add_item(PrevPageButton())
        if self.submittable() and len(self.visited_pages) >= self.total_pages():
            view.add_item(SubmitButton())
        if self.page < self.total_pages() - 1:
            view.add_item(NextPageButton())
        view.add_item(ResetButton())

        # Load election for title
        from election import load_election_from_db
        election = load_election_from_db(self.election_id)

        embed = discord.Embed(
            title=election.title, description=self.instructions
        ).add_field(name="Current vote", value=self.to_markdown(), inline=False)
        if self.total_pages() > 1:
            embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages()}")

        return {
            "embed": embed,
            "view": view,
        }

    async def modify(
        self,
        modification: Callable[[], None],
        interaction: discord.Interaction,
        session_id: int,
    ) -> None:
        from election import load_election_from_db
        election = load_election_from_db(self.election_id)

        if election and await election.check_session(interaction, session_id):
            modification()
            # Save modified ballot to database
            db.save_ballot(self, self.election_id, interaction.user.id, is_submitted=False)
            await interaction.response.edit_message(**self.render_interim(session_id))

    def render_submitted(self) -> dict[str, Any]:
        embed = discord.Embed(title="Vote Submitted").add_field(
            name="Your ballot:",
            value=self.to_markdown(),
            inline=False,
        )
        return {"content": "Your vote has been submitted.", "embed": embed}

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
