import abc
from typing import Any
import discord
from ballot import Ballot
import time


class Election(abc.ABC):
    def __init__(self, title: str, description: str, candidates: list[str]):
        self.title: str = title
        self.description: str = description
        self.candidates: list[str] = candidates
        self.sessions: dict[int, int] = {}
        self.interim_ballots: dict[int, Ballot] = {}
        self.submitted_ballots: dict[int, Ballot] = {}
        self.open = True

    def get_public_view(self) -> dict[str, Any]:
        """Return a dictionary representation of the public view of the election as Discord message fields."""

        class VoteButton(discord.ui.Button):
            def __init__(self, election: "Election"):
                super().__init__(style=discord.ButtonStyle.primary, label="Vote")
                self.election = election

            async def callback(self, interaction: discord.Interaction):
                await self.election.send_ballot(interaction)

        return {
            "embed": discord.Embed(
                title=self.title, description=self.description
            ).add_field(
                name="Candidates", value="\n".join(self.candidates), inline=False
            ),
            "view": discord.ui.View(timeout=None).add_item(VoteButton(self)),
        }

    async def send_ballot(self, interaction: discord.Interaction):
        """Send a ballot to a user that they can use to vote."""
        if not self.open:
            await interaction.response.send_message(
                content="This election is closed.", ephemeral=True
            )
            return

        session_id = time.monotonic_ns()
        self.sessions[interaction.user.id] = session_id

        if interaction.user.id not in self.interim_ballots:
            if interaction.user.id in self.submitted_ballots:
                self.interim_ballots[interaction.user.id] = self.submitted_ballots[
                    interaction.user.id
                ].copy()
            else:
                self.interim_ballots[interaction.user.id] = self.blank_ballot()

        await interaction.response.send_message(
            **self.interim_ballots[interaction.user.id].render_interim(session_id),
            ephemeral=True,
        )

    async def check_session(
        self, interaction: discord.Interaction, session_id: int
    ) -> bool:
        """Check if the interaction is part of the current session."""
        if (
            not self.open
            or interaction.user.id not in self.sessions
            or self.sessions[interaction.user.id] != session_id
        ):
            await interaction.response.edit_message(
                content="This ballot has been superceded by a new ballot.",
                embed=None,
                view=None,
            )
            return False
        return True

    async def submit_ballot(self, interaction: discord.Interaction):
        """Submit the user's current interim ballot as their submitted vote."""

        class RevoteButton(discord.ui.Button):
            def __init__(self, election: "Election"):
                super().__init__(style=discord.ButtonStyle.primary, label="Change Vote")
                self.election = election

            async def callback(self, interaction: discord.Interaction):
                await self.election.send_ballot(interaction)

        if interaction.user.id in self.interim_ballots:
            self.submitted_ballots[interaction.user.id] = self.interim_ballots[
                interaction.user.id
            ]
            del self.interim_ballots[interaction.user.id]
            await interaction.response.edit_message(
                **self.submitted_ballots[interaction.user.id].render_submitted(),
                view=discord.ui.View().add_item(RevoteButton(self)),
            )
        else:
            await interaction.response.edit_message(
                content="Your vote **was not recorded** because you did not have a ballot open.  To cast or update your ballot, click the Vote button again.",
                embed=None,
                view=None,
            )

    def get_results(self, show_details: bool = True) -> discord.Embed:
        self.open = False
        winners = self.get_winners()
        embed = discord.Embed(title=f"Results for {self.title}", color=0x00FF00)
        if len(winners) == 0:
            embed.add_field(name="Winners", value="No winner determined", inline=False)
        elif len(winners) == 1:
            embed.add_field(
                name="Winner", value=f"**{winners[0]}** :trophy:", inline=False
            )
        else:
            winners_str = ", ".join([f"**{w}**" for w in winners])
            embed.add_field(
                name="Winners (Tie)", value=f"{winners_str} :trophy:", inline=False
            )
        if show_details:
            details = self.get_tabulation_details()
            embed.add_field(name="Details", value=details, inline=False)
        return embed

    @abc.abstractmethod
    def blank_ballot(self) -> Ballot:
        """Return a new, empty ballot."""
        pass

    @abc.abstractmethod
    def get_winners(self) -> list[str]:
        """Return list of winners (usually one, but multiple in case of a tie)."""
        pass

    @abc.abstractmethod
    def get_tabulation_details(self) -> str:
        """Return an explanation of how the winner was computed."""
        pass
