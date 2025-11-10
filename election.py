from __future__ import annotations
import abc
from typing import Any, Iterable, TYPE_CHECKING
import discord
import db


if TYPE_CHECKING:
    from ballot import Ballot

# Global reference to Discord client (set by bot.py on startup)
_client = None


def set_client(client):
    """Called by bot.py to set the Discord client reference."""
    global _client
    _client = client


class Election(abc.ABC):
    def __init__(
        self,
        title: str,
        description: str,
        candidates: list[str],
        method_params: dict[str, str],
        election_id: int | None = None,
        channel_id: int | None = None,
        creator_id: int = 0,
        end_timestamp: int | None = None,
    ):
        self.election_id: int | None = election_id
        self.channel_id: int | None = channel_id
        self.title: str = title
        self.description: str = description
        self.candidates: list[str] = candidates
        self.method_params: dict[str, str] = method_params
        self.open = True
        self.message_id: int | None = None
        self.creator_id: int = creator_id
        self.end_timestamp: int | None = end_timestamp

        # Store method class name for serialization
        self.method_class = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def get_public_view(self) -> dict[str, Any]:
        """Return a dictionary representation of the public view of the election as Discord message fields."""
        import time_utils

        class VoteButton(discord.ui.Button):
            def __init__(_, election_id: int):
                super().__init__(style=discord.ButtonStyle.primary, label="Vote")
                _.election_id = election_id

            async def callback(_, interaction: discord.Interaction):
                election = load_election_from_db(_.election_id)
                if election:
                    await election.send_ballot(interaction)
                else:
                    await interaction.response.send_message(
                        "This election no longer exists.", ephemeral=True
                    )

        vote_count = db.get_vote_count(self.election_id)

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
        )

        # Add end time field if scheduled
        if self.end_timestamp:
            embed.add_field(
                name="Ends",
                value=time_utils.format_timestamp_discord(self.end_timestamp),
                inline=False,
            )

        embed.set_footer(text=f"{vote_count} votes cast")

        return {
            "embed": embed,
            "view": discord.ui.View(timeout=None).add_item(
                VoteButton(self.election_id)
            ),
        }

    async def send_ballot(self, interaction: discord.Interaction):
        """Send a ballot to a user that they can use to vote."""
        if not self.open:
            await interaction.response.send_message(
                content="This election is not open.", ephemeral=True
            )
            return

        session_id = db.new_session()

        # Try to load existing interim ballot
        ballot_data = db.load_user_ballot(
            self.election_id, interaction.user.id, is_submitted=False
        )

        if ballot_data is None:
            # Check if they have a submitted ballot (for editing)
            submitted_data = db.load_user_ballot(
                self.election_id, interaction.user.id, is_submitted=True
            )
            if submitted_data:
                ballot = ballot_from_dict(submitted_data, self.election_id)
                ballot = ballot.copy()
                ballot.ballot_id = None  # New interim ballot
            else:
                ballot = self.blank_ballot()
        else:
            ballot = ballot_from_dict(ballot_data, self.election_id)

        # Update session_id and save
        ballot.session_id = session_id
        db.save_ballot(
            ballot, self.election_id, interaction.user.id, is_submitted=False
        )

        await interaction.response.send_message(
            **ballot.render_interim(session_id),
            ephemeral=True,
        )

    async def check_session(
        self, interaction: discord.Interaction, session_id: int
    ) -> bool:
        """Check if the interaction is part of the current session."""
        if not self.open:
            try:
                await interaction.response.edit_message(
                    content="This election is not open.",
                    embed=None,
                    view=None,
                    delete_after=5,
                )
            except discord.errors.NotFound:
                # Interaction token expired (bot restarted)
                pass
            return False

        # Load the user's interim ballot to check session
        ballot_data = db.load_user_ballot(
            self.election_id, interaction.user.id, is_submitted=False
        )
        if ballot_data is None or ballot_data["session_id"] != session_id:
            try:
                await interaction.response.edit_message(
                    content="This ballot has been superseded by a new ballot. Click the Vote button again to continue.",
                    embed=None,
                    view=None,
                    delete_after=10,
                )
            except discord.errors.NotFound:
                # Interaction token expired (bot restarted)
                pass
            return False
        return True

    async def submit_ballot(self, interaction: discord.Interaction):
        """Submit the user's current interim ballot as their submitted vote."""

        # Load interim ballot
        ballot_data = db.load_user_ballot(
            self.election_id, interaction.user.id, is_submitted=False
        )

        if ballot_data:
            ballot = ballot_from_dict(ballot_data, self.election_id)

            # Atomically move from interim to submitted
            db.submit_ballot(self.election_id, interaction.user.id, ballot)

            await interaction.response.edit_message(
                **ballot.render_submitted(),
                view=None,
            )

            # Update vote count on public message
            await self.update_vote_count()
        else:
            await interaction.response.edit_message(
                content="Your vote **was not recorded** because you did not have a ballot open.  To cast or update your ballot, click the Vote button again.",
                embed=None,
                view=None,
                delete_after=5,
            )

    async def update_vote_count(self):
        """Update the public Discord message with current vote count."""
        try:
            channel = _client.get_channel(self.channel_id)
            message = await channel.fetch_message(self.message_id)
            await message.edit(**self.get_public_view())
        except discord.NotFound:
            pass

    def get_results(self, show_details: bool = True) -> discord.Embed:
        self.open = False
        db.mark_election_closed(self.election_id)

        # Load all submitted ballots from database
        ballot_dicts = db.load_all_ballots(self.election_id, is_submitted=True)
        ballots = [ballot_from_dict(bd, self.election_id) for bd in ballot_dicts]

        winners, details = self.tabulate(ballots)
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


def load_election_from_db(election_id: int) -> Election | None:
    """Load an election from the database by ID."""
    data = db.load_election(election_id)
    if data is None:
        return None

    # Import dynamically to get the correct class
    import importlib

    module_name, class_name = data["method_class"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    election_class = getattr(module, class_name)

    # Instantiate the election
    election = election_class(
        title=data["title"],
        description=data["description"],
        candidates=data["candidates"],
        method_params=data["method_params"],
        election_id=data["election_id"],
        channel_id=data["channel_id"],
        creator_id=data["creator_id"],
        end_timestamp=data["end_timestamp"],
    )
    election.open = data["open"]
    election.message_id = data["message_id"]

    return election


def ballot_from_dict(ballot_dict: dict[str, Any], election_id: int) -> "Ballot":
    """Reconstruct a ballot from database dict."""
    # Import dynamically to get the correct ballot class
    import importlib

    module_name, class_name = ballot_dict["ballot_type"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    ballot_class = getattr(module, class_name)

    # Call the from_dict class method
    return ballot_class.from_dict(ballot_dict, election_id)


async def end_election_and_update_message(
    election: "Election",
    channel: discord.TextChannel,
    include_announcement: bool = False,
) -> None:
    """End an election, post results, and update the original message.

    Args:
        election: The election to end
        channel: The Discord channel where the election is posted
        include_announcement: If True, includes "Election **{title}** has ended!" text
    """
    import time_utils

    # Generate results embed
    results_embed = election.get_results(show_details=True).set_footer(
        text=f"Computed using {election.method_description(election.method_params)}"
    )

    # Post results to channel
    if include_announcement:
        await channel.send(
            content=f"Election **{election.title}** has ended!",
            embed=results_embed,
        )
    else:
        await channel.send(embed=results_embed)

    # Update the original election message
    if election.message_id:
        try:
            message = await channel.fetch_message(election.message_id)
            embed = message.embeds[0] if message.embeds else None
            if embed:
                # Update footer
                embed.set_footer(text=f"{embed.footer.text} • Election ended")

                # Update "Ends" field to "Ended" and remove relative time
                if election.end_timestamp:
                    for i, field in enumerate(embed.fields):
                        if field.name == "Ends":
                            embed.set_field_at(
                                i,
                                name="Ended",
                                value=time_utils.format_timestamp_discord(
                                    election.end_timestamp,
                                    include_relative=False,
                                ),
                                inline=False,
                            )
                            break
            await message.edit(embed=embed, view=None)
        except discord.NotFound:
            pass  # Message was deleted

    # Delete the election from database
    db.delete_election(election.election_id)
