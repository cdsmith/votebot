from __future__ import annotations
import abc
import time
from typing import Any, Iterable, TYPE_CHECKING
import discord
import db
from i18n import LocalizedView, _, ngettext, use_locale
from layout import notice, pack_text
from text_utils import LAYOUT_TEXT_LIMIT, truncate

# Accent colors for public messages
OPEN_COLOR = 0x5865F2
ENDED_COLOR = 0x99AAB5
RESULTS_COLOR = 0x00FF00

if TYPE_CHECKING:
    from ballot import Ballot

# Global reference to Discord client (set by bot.py on startup)
_client = None

# IDs of elections currently being ended, to avoid posting results twice
_ending_elections: set[int] = set()

# Results messages not yet posted, by election ID.  If posting fails partway,
# a retry resumes from here, so messages aren't repeated and randomized tie
# breaks give the same result.
_unposted_results: dict[int, list[discord.ui.LayoutView]] = {}


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
        locale: str | None = None,
        shared: bool = False,
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
        # Language of public messages, as a Discord locale code; None is English
        self.locale: str | None = locale
        # Whether anyone who can use /electable in the channel may manage this
        # election, rather than only its creator.  Personal elections show
        # their creator.
        self.shared: bool = shared

        # Store method class name for serialization
        self.method_class = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def get_public_view(self, ended_at: int | None = None) -> dict[str, Any]:
        """Return the public message announcing the election, as message
        fields.  If ended_at is given, show the election as ended then."""
        # Public text is in the election's language, whoever caused the update.
        with use_locale(self.locale):
            import time_utils

            class VoteButton(discord.ui.Button):
                def __init__(inner_self, election_id: int):
                    super().__init__(style=discord.ButtonStyle.primary, label=_("Vote"))
                    inner_self.election_id = election_id

                async def callback(inner_self, interaction: discord.Interaction):
                    election = load_election_from_db(inner_self.election_id)
                    if election:
                        await election.send_ballot(interaction)
                    else:
                        await interaction.response.send_message(
                            _("This election no longer exists."), ephemeral=True
                        )

            vote_count = db.get_vote_count(self.election_id)
            votes = ngettext("{n} vote cast", "{n} votes cast", vote_count).format(
                n=vote_count
            )
            candidates = "\n".join(f"- {c}" for c in self.candidates) or _(
                "*No candidates yet!*"
            )
            if ended_at is None:
                end_time = self.end_timestamp and "**{}**\n{}".format(
                    _("Ends"), time_utils.format_timestamp_discord(self.end_timestamp)
                )
                footer = votes
            else:
                end_time = "**{}**\n{}".format(
                    _("Ended"),
                    time_utils.format_timestamp_discord(
                        ended_at, include_relative=False
                    ),
                )
                footer = _("{footer} • Election ended").format(footer=votes)

            heading = [f"## {self.title}"]
            if not self.shared and self.creator_id:
                heading.append(
                    "-# " + _("Run by {user}").format(user=f"<@{self.creator_id}>")
                )
            body = [
                "**{}**\n{}".format(_("Candidates"), candidates),
                "**{}**\n{}".format(
                    _("Method"), self.method_description(self.method_params)
                ),
            ]
            if end_time:
                body.append(end_time)
            footer = f"-# {footer}"
            # The description gets whatever room is left within Discord's limit.
            room = LAYOUT_TEXT_LIMIT - sum(map(len, heading + body)) - len(footer)
            description = [truncate(self.description, room)] if self.description else []
            texts = heading + description + body

            container = discord.ui.Container(
                *(discord.ui.TextDisplay(t) for t in texts),
                accent_color=OPEN_COLOR if ended_at is None else ENDED_COLOR,
            )
            container.add_item(discord.ui.Separator())
            if ended_at is None:
                container.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(footer),
                        accessory=VoteButton(self.election_id),
                    )
                )
            else:
                container.add_item(discord.ui.TextDisplay(footer))

            view = LocalizedView(timeout=None)
            view.add_item(container)
            # Clearing content and embeds converts messages posted before the
            # bot used Components V2.
            return {
                "view": view,
                "content": None,
                "embeds": [],
                # Naming the creator shouldn't notify them.
                "allowed_mentions": discord.AllowedMentions.none(),
            }

    def accepting_votes(self) -> bool:
        """Whether voting is open.  Voting closes at the scheduled end time,
        even if posting the results is delayed."""
        if self.end_timestamp is not None and self.end_timestamp <= time.time():
            return False
        return self.open

    async def send_ballot(self, interaction: discord.Interaction):
        """Send a ballot to a user that they can use to vote."""
        if not self.accepting_votes():
            await interaction.response.send_message(
                content=_("This election is not open."), ephemeral=True
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
        if not self.accepting_votes():
            try:
                await interaction.response.edit_message(
                    view=notice(_("This election is not open.")), delete_after=5
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
                    view=notice(
                        _(
                            "This ballot has been superseded by a new ballot. "
                            "Click the Vote button again to continue."
                        )
                    ),
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

            await interaction.response.edit_message(**ballot.render_submitted())

            # Update vote count on public message
            await self.update_vote_count()
        else:
            await interaction.response.edit_message(
                view=notice(
                    _(
                        "Your vote **was not recorded** because you did not have a "
                        "ballot open.  To cast or update your ballot, click the Vote "
                        "button again."
                    )
                ),
                delete_after=5,
            )

    async def update_vote_count(self):
        """Update the public Discord message with current vote count."""
        try:
            channel = _client.get_channel(self.channel_id)
            message = await channel.fetch_message(self.message_id)
            await message.edit(**self.get_public_view())
        except discord.NotFound:
            # The post is the election, so with the post gone, so is it.
            db.delete_election(self.election_id)

    def get_results(
        self, announcement: str | None = None
    ) -> list[discord.ui.LayoutView]:
        """Tabulate the submitted ballots and return messages describing the
        results: the winners, then the details of the tabulation, split across
        as many messages as needed."""
        # Load all submitted ballots from database
        ballot_dicts = db.load_all_ballots(self.election_id, is_submitted=True)
        ballots = [ballot_from_dict(bd, self.election_id) for bd in ballot_dicts]

        winners, details = self.tabulate(ballots)
        if len(winners) == 0:
            winners_text = "**{}**\n{}".format(_("Winners"), _("No winner determined"))
        elif len(winners) == 1:
            winners_text = "**{}**\n:trophy: **{}** :trophy:".format(
                _("Winner"), winners[0]
            )
        else:
            winners_str = ", ".join([f"**{w}**" for w in winners])
            winners_text = "**{}**\n:trophy: {} :trophy:".format(
                _("Winners"), winners_str
            )

        heading = "## " + _("Results for {title}").format(title=self.title)
        blocks = [heading, winners_text]
        if details:
            blocks += ["### " + _("Details"), details]
        blocks.append(
            "-# "
            + _("Computed using {method}").format(
                method=self.method_description(self.method_params)
            )
        )

        messages = []
        for i, texts in enumerate(pack_text(blocks, len(announcement or ""))):
            view = LocalizedView(timeout=None)
            if i == 0 and announcement:
                view.add_item(discord.ui.TextDisplay(announcement))
            view.add_item(
                discord.ui.Container(
                    *(discord.ui.TextDisplay(t) for t in texts),
                    accent_color=RESULTS_COLOR,
                )
            )
            messages.append(view)
        return messages

    @classmethod
    @abc.abstractmethod
    def method_name(self) -> str:
        """Return the name of the election method.  This identifies the method,
        so it is in English, marked with N_() for translation where it is
        displayed."""
        pass

    @classmethod
    def method_description(self, params: dict[str, str]) -> str:
        """Return the description of the election method."""
        return _(self.method_name())

    @classmethod
    def method_param_names(self) -> list[str]:
        """Return a list of parameters that can be used to configure the election method.

        Like method names, these are identifiers marked with N_()."""
        return []

    @classmethod
    def default_method_params(self) -> dict[str, str]:
        """Return a dictionary of default parameter values."""
        return {}

    @classmethod
    def method_param_choices(
        self, param: str, candidates: list[str]
    ) -> list[str] | None:
        """Return the allowed values of a parameter, to choose from a list, or
        None to enter the value as text."""
        return None

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
        locale=data["locale"],
        shared=data["shared"],
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
    if election.election_id in _ending_elections:
        return  # Already being ended elsewhere (e.g. scheduled end vs. End Now)
    _ending_elections.add(election.election_id)
    try:
        # Results are public, so they're in the election's language even when
        # ended by its creator from a screen in another language.
        with use_locale(election.locale):
            await _end_election(election, channel, include_announcement)
    finally:
        _ending_elections.discard(election.election_id)


async def _end_election(
    election: "Election",
    channel: discord.TextChannel,
    include_announcement: bool,
) -> None:
    unposted = _unposted_results.get(election.election_id)
    if unposted is None:
        announcement = (
            _("Election **{title}** has ended!").format(title=election.title)
            if include_announcement
            else None
        )
        unposted = election.get_results(announcement)
        _unposted_results[election.election_id] = unposted

    # Post results to channel.  The election stays in the database until this
    # succeeds, so a failure here can be retried rather than losing results.
    while unposted:
        await channel.send(view=unposted[0])
        unposted.pop(0)
    del _unposted_results[election.election_id]

    # Show the original message as ended, at its scheduled time if it had one.
    # This needs the election's vote count, so it's built before the election
    # is deleted.
    now = int(time.time())
    if election.end_timestamp and election.end_timestamp <= now:
        ended = election.get_public_view(ended_at=election.end_timestamp)
    else:
        ended = election.get_public_view(ended_at=now)

    # The results are posted, so the election is over.  Delete it before
    # touching the original message, so that a failure there can't cause the
    # results to be posted again.
    db.delete_election(election.election_id)

    if election.message_id:
        try:
            message = await channel.fetch_message(election.message_id)
            await message.edit(**ended)
        except discord.NotFound:
            pass  # Message was deleted
        except discord.HTTPException as e:
            print(f"Error updating message for election {election.election_id}: {e}")
