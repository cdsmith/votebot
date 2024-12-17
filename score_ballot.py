from ballot import Ballot
from typing import Any
import discord
from election import Election

STAR = "⭐"


class ScoreBallot(Ballot):
    def __init__(self, election: Election):
        self.election: Election = election
        self.ratings: dict[str, int] = {}

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

        class SubmitButton(discord.ui.Button):
            def __init__(self, ballot: "ScoreBallot", session_id: int):
                super().__init__(style=discord.ButtonStyle.green, label="Submit Vote")
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(interaction, session_id):
                    await self.ballot.election.submit_ballot(interaction)

        view = discord.ui.View()
        for c in self.election.candidates:
            view.add_item(CandidateSelect(self, c, session_id))
        if self.ratings:
            view.add_item(SubmitButton(self, session_id))

        return {
            "embed": discord.Embed(
                title=self.election.title,
                description="Rate candidates from 0 to 5 stars.",
            ),
            "view": view,
        }

    def render_submitted(self) -> dict[str, Any]:
        embed = discord.Embed(title="Vote")
        for c in self.election.candidates:
            r = self.ratings.get(c, 0)
            embed.add_field(name=c, value=" ".join([STAR] * r), inline=False)
        return {
            "content": "Your vote has been submitted.",
            "embed": embed,
        }

    def copy(self) -> "ScoreBallot":
        ballot = ScoreBallot(self.election)
        ballot.ratings = self.ratings.copy()
        return ballot
