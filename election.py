from __future__ import annotations
import abc
from typing import Any, TYPE_CHECKING
import discord
import time

if TYPE_CHECKING:
    from ballot import Ballot

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

        embed = discord.Embed(
            title=self.title,
            description=self.description,
        ).add_field(
            name="Candidates", value="\n".join(f"- {c}" for c in self.candidates), inline=False
        ).add_field(
            name="Method", value=self.name(), inline=False
        ).set_footer(text=f"{str(len(self.submitted_ballots))} votes cast")

        return {
            "embed": embed,
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
                delete_after=5,
            )
            return False
        return True

    async def submit_ballot(self, interaction: discord.Interaction):
        """Submit the user's current interim ballot as their submitted vote."""

        if interaction.user.id in self.interim_ballots:
            self.submitted_ballots[interaction.user.id] = self.interim_ballots[
                interaction.user.id
            ]
            del self.interim_ballots[interaction.user.id]
            await interaction.response.edit_message(
                **self.submitted_ballots[interaction.user.id].render_submitted(),
                view=None,
            )
            if self.original_message is not None:
                await self.original_message.edit(**self.get_public_view())
        else:
            await interaction.response.edit_message(
                content="Your vote **was not recorded** because you did not have a ballot open.  To cast or update your ballot, click the Vote button again.",
                embed=None,
                view=None,
                delete_after=5,
            )

    def get_results(self, show_details: bool = True) -> discord.Embed:
        self.open = False
        winners, details = self.tabulate()
        embed = discord.Embed(title=f"Results for {self.title}", color=0x00FF00)
        if len(winners) == 0:
            embed.add_field(name="Winners", value="No winner determined", inline=False)
        elif len(winners) == 1:
            embed.add_field(
                name="Winner", value=f":trophy: **{winners[0]}** :trophy:", inline=False
            )
        else:
            winners_str = ", ".join([f"**{w}**" for w in winners])
            embed.add_field(
                name="Winners (Tie)", value=f":trophy: {winners_str} :trophy:", inline=False
            )
        if show_details:
            embed.add_field(name="Details", value=details, inline=False)
        return embed

    @abc.abstractmethod
    def name(self) -> str:
        """Return the name of the election method."""
        pass

    @abc.abstractmethod
    def blank_ballot(self) -> Ballot:
        """Return a new, empty ballot."""
        pass

    @abc.abstractmethod
    def tabulate(self) -> tuple[list[str], str]:
        """Returns tabulated results.

        The first result should be a list of winners (usually one, but multiple in case of a tie)
        The second result should be an explanation of how the winner was chosen.
        """
        pass
