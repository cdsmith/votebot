from __future__ import annotations
import abc
from typing import Any, Iterable, TYPE_CHECKING
import discord
import time


if TYPE_CHECKING:
    from ballot import Ballot


class Election(abc.ABC):
    def __init__(
        self,
        title: str,
        description: str,
        candidates: list[str],
        method_params: dict[str, str],
    ):
        self.title: str = title
        self.description: str = description
        self.candidates: list[str] = candidates
        self.method_params: dict[str, str] = method_params
        self.sessions: dict[int, int] = {}
        self.interim_ballots: dict[int, Ballot] = {}
        self.submitted_ballots: dict[int, Ballot] = {}
        self.open = True
        self.original_message: discord.Message | None = None

    def get_public_view(self) -> dict[str, Any]:
        """Return a dictionary representation of the public view of the election as Discord message fields."""

        class VoteButton(discord.ui.Button):
            def __init__(self, election: "Election"):
                super().__init__(style=discord.ButtonStyle.primary, label="Vote")
                self.election = election

            async def callback(self, interaction: discord.Interaction):
                await self.election.send_ballot(interaction)

        embed = (
            discord.Embed(
                title=self.title,
                description=self.description,
            )
            .add_field(
                name="Candidates",
                value="\n".join(f"- {c}" for c in self.candidates)
                or "*No candidates yet!*",
                inline=False,
            )
            .add_field(
                name="Method",
                value=self.method_description(self.method_params),
                inline=False,
            )
            .set_footer(text=f"{str(len(self.submitted_ballots))} votes cast")
        )

        return {
            "embed": embed,
            "view": discord.ui.View(timeout=None).add_item(VoteButton(self)),
        }

    async def send_ballot(self, interaction: discord.Interaction):
        """Send a ballot to a user that they can use to vote."""
        if not self.open:
            await interaction.response.send_message(
                content="This election is not open.", ephemeral=True
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
        if not self.open:
            await interaction.response.edit_message(
                content="This election is not open.",
                embed=None,
                view=None,
                delete_after=5,
            )
            return False
        if (
            interaction.user.id not in self.sessions
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
        winners, details = self.tabulate(self.submitted_ballots.values())
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
                name="Winners",
                value=f":trophy: {winners_str} :trophy:",
                inline=False,
            )
        if show_details:
            embed.add_field(name="Details", value=details, inline=False)
        return embed

    @classmethod
    @abc.abstractmethod
    def method_name(self) -> str:
        """Return the name of the election method."""
        pass

    @classmethod
    def method_description(self, params: dict[str, str]) -> str:
        """Return the description of the election method."""
        return self.method_name()

    @classmethod
    def method_param_names(self) -> list[str]:
        """Return a list of parameters that can be used to configure the election method."""
        return []

    @classmethod
    def default_method_params(self) -> dict[str, str]:
        """Return a dictionary of default parameter values."""
        return {}

    @classmethod
    def validate_method_params(
        self, params: dict[str, str], candidates: list[str]
    ) -> str | None:
        """If the given parameter values are invalid, return a string explaining the reason."""
        return None

    @abc.abstractmethod
    def blank_ballot(self) -> Ballot:
        """Return a new, empty ballot."""
        pass

    @abc.abstractmethod
    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        """Returns tabulated results.

        The first result should be a list of winners.
        The second result should be an explanation of how the winner was chosen.
        """
        pass
