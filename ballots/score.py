from ballot import Ballot
from typing import Any
import discord
from election import Election
import math

STAR = "⭐"
CANDIDATES_PER_PAGE = 4


class ScoreBallot(Ballot):
    def __init__(self, election: Election):
        self.election: Election = election
        self.ratings: dict[str, int] = {}
        self.page: int = 0
        self.visited_pages: set[int] = set()

    def total_pages(self) -> int:
        return math.ceil(len(self.election.candidates) / CANDIDATES_PER_PAGE)

    def candidates_on_page(self) -> list[str]:
        start = self.page * CANDIDATES_PER_PAGE
        end = start + CANDIDATES_PER_PAGE
        return self.election.candidates[start:end]

    def render_interim(self, session_id: int) -> dict[str, Any]:
        class CandidateSelect(discord.ui.Select):
            def __init__(self, ballot: "ScoreBallot", candidate: str, session_id: int):
                current_rating = ballot.ratings.get(candidate, 0)
                super().__init__(
                    placeholder=f"{candidate}: {' '.join([STAR] * current_rating)}",
                    options=[
                        discord.SelectOption(
                            value=str(i),
                            label=f"{candidate}: {' '.join([STAR] * i)}",
                        )
                        for i in range(6)
                    ],
                )
                self.ballot = ballot
                self.candidate = candidate
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(interaction, session_id):
                    chosen = int(self.values[0])
                    self.ballot.ratings[self.candidate] = chosen
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(session_id)
                    )

        class NextPageButton(discord.ui.Button):
            def __init__(self, ballot: "ScoreBallot", session_id: int):
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
            def __init__(self, ballot: "ScoreBallot", session_id: int):
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
            def __init__(self, ballot: "ScoreBallot", session_id: int):
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
            view.add_item(CandidateSelect(self, c, session_id))
        if self.page > 0:
            view.add_item(PrevPageButton(self, session_id))
        if self.ratings and len(self.visited_pages) >= self.total_pages():
            view.add_item(SubmitButton(self, session_id))
        if self.page < self.total_pages() - 1:
            view.add_item(NextPageButton(self, session_id))

        instruction = "Rate candidates from 0 to 5 stars."

        embed = discord.Embed(title=self.election.title, description=instruction)
        if self.total_pages() > 1:
            embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages()}")

        return {
            "embed": embed,
            "view": view,
        }

    def render_submitted(self) -> dict[str, Any]:
        embed = discord.Embed(title="Vote")
        for c in self.election.candidates:
            r = self.ratings.get(c, 0)
            embed.add_field(name=c, value=" ".join([STAR] * r), inline=False)
        return {"content": "Your vote has been submitted.", "embed": embed}

    def copy(self) -> "ScoreBallot":
        ballot = ScoreBallot(self.election)
        ballot.ratings = self.ratings.copy()
        ballot.visited_pages = self.visited_pages.copy()

        # Page number is transient and should not be copied to a duplicate ballot.
        ballot.page = 0

        return ballot
