from ballot import Ballot
from typing import Any
import discord
from election import Election
import math

CANDIDATES_PER_PAGE = 20


class SimpleBallot(Ballot):
    """
    A ballot that allows a user to vote for candidates.
    Can allow multiple votes if `multiple_votes` is set to True.
    """

    def __init__(self, election: Election, multiple_votes: bool = False):
        self.election: Election = election
        self.votes: set[str] = set()
        self.multiple_votes: bool = multiple_votes
        self.page: int = 0
        self.visited_pages: set[int] = set()

    def total_pages(self) -> int:
        return math.ceil(len(self.election.candidates) / CANDIDATES_PER_PAGE)

    def candidates_on_page(self) -> list[str]:
        start = self.page * CANDIDATES_PER_PAGE
        end = start + CANDIDATES_PER_PAGE
        return self.election.candidates[start:end]

    def render_interim(self, session_id: int) -> dict[str, Any]:
        class VoteButton(discord.ui.Button):
            def __init__(self, ballot: "SimpleBallot", candidate: str, session_id: int):
                super().__init__(
                    style=discord.ButtonStyle.primary
                    if candidate in ballot.votes
                    else discord.ButtonStyle.gray,
                    label=candidate,
                )
                self.ballot = ballot
                self.candidate = candidate
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(interaction, session_id):
                    if self.candidate in self.ballot.votes:
                        self.ballot.votes.remove(self.candidate)
                    elif self.ballot.multiple_votes:
                        self.ballot.votes.add(self.candidate)
                    else:
                        self.ballot.votes = {self.candidate}
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(session_id)
                    )

        class NextPageButton(discord.ui.Button):
            def __init__(self, ballot: "SimpleBallot", session_id: int):
                super().__init__(
                    style=discord.ButtonStyle.primary, label="Next Page", row=4
                )
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(
                    interaction, self.session_id
                ):
                    if self.ballot.page < self.ballot.total_pages() - 1:
                        self.ballot.page += 1
                    else:
                        self.ballot.page = 0
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(self.session_id)
                    )

        class PrevPageButton(discord.ui.Button):
            def __init__(self, ballot: "SimpleBallot", session_id: int):
                super().__init__(
                    style=discord.ButtonStyle.primary, label="Prev Page", row=4
                )
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(
                    interaction, self.session_id
                ):
                    if self.ballot.page > 0:
                        self.ballot.page -= 1
                    else:
                        self.ballot.page = self.ballot.total_pages() - 1
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(self.session_id)
                    )

        class SubmitButton(discord.ui.Button):
            def __init__(self, ballot: "SimpleBallot", session_id: int):
                super().__init__(
                    style=discord.ButtonStyle.green, label="Submit Vote", row=4
                )
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(interaction, session_id):
                    await self.ballot.election.submit_ballot(interaction)

        self.visited_pages.add(self.page)

        view = discord.ui.View()
        for c in self.candidates_on_page():
            view.add_item(VoteButton(self, c, session_id))
        if self.page > 0:
            view.add_item(PrevPageButton(self, session_id))
        if self.votes and len(self.visited_pages) >= self.total_pages():
            view.add_item(SubmitButton(self, session_id))
        if self.page < self.total_pages() - 1:
            view.add_item(NextPageButton(self, session_id))

        instruction = (
            "Please select all candidates you approve of."
            if self.multiple_votes
            else "Please select a candidate."
        )

        embed = discord.Embed(title=self.election.title, description=instruction)
        if self.total_pages() > 1:
            embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages()}")

        return {
            "embed": embed,
            "view": view,
        }

    def render_submitted(self) -> dict[str, Any]:
        embed = discord.Embed(title="Vote").add_field(
            name="You voted for:",
            value=",".join(self.votes) if self.votes else "No vote recorded",
            inline=False,
        )
        return {"content": "Your vote has been submitted.", "embed": embed}

    def copy(self) -> "SimpleBallot":
        ballot = SimpleBallot(self.election)
        ballot.votes = self.votes.copy()
        ballot.multiple_votes = self.multiple_votes
        ballot.visited_pages = self.visited_pages.copy()

        # Page number is transient and should not be copied to a duplicate ballot.
        ballot.page = 0

        return ballot
