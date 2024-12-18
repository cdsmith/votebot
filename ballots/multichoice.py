from ballot import Ballot
from typing import Any
import discord
from election import Election


class MultiChoiceBallot(Ballot):
    def __init__(self, election: Election):
        self.election: Election = election
        self.votes: set[str] = set()

    def render_interim(self, session_id: int) -> dict[str, Any]:
        class VoteButton(discord.ui.Button):
            def __init__(
                self, ballot: "MultiChoiceBallot", candidate: str, session_id: int
            ):
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
                    else:
                        self.ballot.votes.add(self.candidate)
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(session_id)
                    )

        class SubmitButton(discord.ui.Button):
            def __init__(self, ballot: "MultiChoiceBallot", session_id: int):
                super().__init__(style=discord.ButtonStyle.green, label="Submit Vote", row=4)
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(interaction, session_id):
                    await self.ballot.election.submit_ballot(interaction)

        view = discord.ui.View()
        for c in self.election.candidates:
            view.add_item(VoteButton(self, c, session_id))
        if self.votes:
            view.add_item(SubmitButton(self, session_id))

        return {
            "embed": discord.Embed(
                title=self.election.title,
                description="Please select all candidates you approve of.",
            ),
            "view": view,
        }

    def render_submitted(self) -> dict[str, Any]:
        return {
            "content": "Your vote has been submitted.",
            "embed": discord.Embed(title="Vote").add_field(
                name="You voted for:",
                value=",".join(self.votes) if self.votes else "No vote recorded",
                inline=False,
            ),
        }

    def copy(self) -> "MultiChoiceBallot":
        ballot = MultiChoiceBallot(self.election)
        ballot.votes = self.votes.copy()
        return ballot
