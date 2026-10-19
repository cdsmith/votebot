"""Unified command interface for managing elections."""

import discord
from typing import Any
import asyncio
import db
from election import load_election_from_db, end_election_and_update_message
from setup import ElectionSetup
import time_utils
import election_checker
from i18n import LocalizedModal, LocalizedView, _, ngettext, use_locale
from text_utils import MESSAGE_CONTENT_LIMIT, truncate


class ElectableView(LocalizedView):
    """Main view for the /electable command."""

    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.interaction = interaction
        self.selected_election_id: int | None = None

        # Load user's elections in this channel
        self.elections = db.load_elections_by_creator(
            interaction.channel_id, interaction.user.id
        )

        self.build_view()

    def build_view(self):
        """Build the UI based on current state."""
        self.clear_items()

        if self.selected_election_id:
            # Show management view for selected election
            self.add_item(BackButton())
            self.add_item(RescheduleButton(self.selected_election_id))
            self.add_item(EndNowButton(self.selected_election_id))
            self.add_item(DeleteButton(self.selected_election_id))
        else:
            # Show election list view
            if self.elections:
                self.add_item(ElectionSelect(self.elections, self))
                self.add_item(
                    CreateNewButton(row=1)
                )  # Row 1 when there's a select menu
            else:
                self.add_item(CreateNewButton(row=0))  # Row 0 when no select menu

    def get_content(self) -> dict[str, Any]:
        """Get the message content for the current view."""
        if self.selected_election_id:
            # Show selected election details
            election = load_election_from_db(self.selected_election_id)
            if not election:
                return {
                    "content": _("Error: Election not found."),
                    "view": None,
                }

            vote_count = db.get_vote_count(election.election_id)
            end_time = time_utils.format_timestamp_discord(election.end_timestamp)

            content = _(
                "**Managing: {title}**\n\n"
                "**Method**: {method}\n"
                "**Candidates**: {candidates}\n"
                "**Votes**: {votes}\n"
                "**Ends**: {end_time}\n"
            ).format(
                title=election.title,
                method=election.method_description(election.method_params),
                candidates=", ".join(election.candidates),
                votes=vote_count,
                end_time=end_time,
            )

            return {"content": truncate(content, MESSAGE_CONTENT_LIMIT), "view": self}
        else:
            # Show election list view
            if self.elections:
                content = _("Select an election to manage, or create a new one.")
            else:
                content = _(
                    "You have no active elections in this channel.\n\n"
                    "Click the button below to create one!"
                )

            return {"content": content, "view": self}


class ElectionSelect(discord.ui.Select):
    """Dropdown to select an election to manage."""

    def __init__(self, elections: list[dict[str, Any]], parent_view: ElectableView):
        self.parent_view = parent_view

        options = []
        for e_data in elections[:25]:  # Discord limit
            election = load_election_from_db(e_data["election_id"])
            vote_count = db.get_vote_count(election.election_id)
            options.append(
                discord.SelectOption(
                    label=election.title[:100],  # Discord limit
                    value=str(election.election_id),
                    description=ngettext("{n} vote", "{n} votes", vote_count).format(
                        n=vote_count
                    ),
                )
            )

        super().__init__(
            placeholder=_("Select an election to manage"),
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_election_id = int(self.values[0])
        self.parent_view.build_view()
        await interaction.response.edit_message(**self.parent_view.get_content())


class BackButton(discord.ui.Button):
    """Button to go back to the election list."""

    def __init__(self):
        super().__init__(label=_("← Back"), style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, ElectableView):
            view.selected_election_id = None
            # Reload elections in case they changed
            view.elections = db.load_elections_by_creator(
                interaction.channel_id, interaction.user.id
            )
            view.build_view()
            await interaction.response.edit_message(**view.get_content())


class CreateNewButton(discord.ui.Button):
    """Button to create a new election."""

    def __init__(self, row: int = 0):
        super().__init__(
            label=_("Create New Election"),
            style=discord.ButtonStyle.success,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        parent_view = self.view

        result = await ElectionSetup().start(interaction, parent_view)
        if result:
            channel_id, title, election, start_interaction = result

            # Check if election already exists
            existing = db.load_election_by_natural_key(channel_id, title)
            if existing:
                await interaction.followup.send(
                    _(
                        "An election with the title `{title}` is already ongoing in "
                        "this channel."
                    ).format(title=title),
                    ephemeral=True,
                )
                return

            # Set channel_id and save to database
            election.channel_id = channel_id
            db.save_election(election)

            # Post public message
            channel = interaction.channel
            message = await channel.send(**election.get_public_view())
            election.message_id = message.id
            db.save_election(election)

            # Trigger background task to check for expiration immediately
            election_checker.trigger_check()

            # Update the electable view to refresh the election list
            if isinstance(parent_view, ElectableView):
                parent_view.elections = db.load_elections_by_creator(
                    channel_id, interaction.user.id
                )
                parent_view.build_view()
                # Edit the message using the start interaction to show the updated list
                try:
                    await start_interaction.response.edit_message(
                        **parent_view.get_content()
                    )
                except (discord.errors.NotFound, discord.errors.HTTPException):
                    pass  # If we can't edit it (message deleted or interaction expired), that's okay


class RescheduleButton(discord.ui.Button):
    """Button to reschedule an election's end time."""

    def __init__(self, election_id: int):
        super().__init__(
            label=_("Reschedule"),
            style=discord.ButtonStyle.primary,
            row=2,
        )
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            # Election no longer exists - refresh the view to show current elections
            view = self.view
            if isinstance(view, ElectableView):
                view.selected_election_id = None
                view.elections = db.load_elections_by_creator(
                    interaction.channel_id, interaction.user.id
                )
                view.build_view()
                await interaction.response.edit_message(**view.get_content())
            return

        parent_view = self.view

        class RescheduleModal(LocalizedModal, title=_("Reschedule Election")):
            end_time = discord.ui.TextInput(
                label=_("New End Time"),
                # Translators: keep the examples as they are; only these formats can be parsed.
                placeholder=_("Examples: 2d, 3h30m, 2025-12-25 14:30"),
                default="",
                required=False,
            )

            async def on_submit(inner_self, interaction: discord.Interaction):
                # Parse new end time
                new_timestamp, error = time_utils.validate_time_input(
                    inner_self.end_time.value
                )
                if error:
                    await interaction.response.send_message(
                        _("Error: {error}").format(error=error),
                        ephemeral=True,
                        delete_after=10,
                    )
                    return

                # Update election
                election.end_timestamp = new_timestamp
                db.save_election(election)

                # Trigger background task to check for expiration immediately
                election_checker.trigger_check()

                # Update public message
                await election.update_vote_count()

                # Update the management view to show new end time
                if isinstance(parent_view, ElectableView):
                    await interaction.response.edit_message(**parent_view.get_content())
                else:
                    # Fallback if view context is lost
                    await interaction.response.send_message(
                        _("Election rescheduled!"),
                        ephemeral=True,
                        delete_after=5,
                    )

        await interaction.response.send_modal(RescheduleModal())


class EndNowButton(discord.ui.Button):
    """Button to end an election immediately."""

    def __init__(self, election_id: int):
        super().__init__(
            label=_("End Now"),
            style=discord.ButtonStyle.danger,
            row=2,
        )
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            # Election no longer exists - refresh the view to show current elections
            view = self.view
            if isinstance(view, ElectableView):
                view.selected_election_id = None
                view.elections = db.load_elections_by_creator(
                    interaction.channel_id, interaction.user.id
                )
                view.build_view()
                await interaction.response.edit_message(**view.get_content())
            return

        class ConfirmModal(LocalizedModal, title=_("Confirm End Election")):
            confirm = discord.ui.TextInput(
                # Translators: keep "CONFIRM" in English; users must type it exactly.
                label=_('Type "CONFIRM" to end this election'),
                placeholder="CONFIRM",
                max_length=7,
            )

            async def on_submit(inner_self, interaction: discord.Interaction):
                if inner_self.confirm.value.strip().upper() != "CONFIRM":
                    await interaction.response.send_message(
                        _("Election not ended. Confirmation text did not match."),
                        ephemeral=True,
                    )
                    return

                # End the election using shared logic
                await end_election_and_update_message(
                    election, interaction.channel, include_announcement=False
                )

                # Update the parent view and go back to the election list
                view = self.view
                if isinstance(view, ElectableView):
                    view.selected_election_id = None
                    view.elections = db.load_elections_by_creator(
                        interaction.channel_id, interaction.user.id
                    )
                    view.build_view()
                    await interaction.response.edit_message(**view.get_content())

        await interaction.response.send_modal(ConfirmModal())


class DeleteButton(discord.ui.Button):
    """Button to delete an election without showing results."""

    def __init__(self, election_id: int):
        super().__init__(
            label=_("Delete"),
            style=discord.ButtonStyle.danger,
            row=2,
        )
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            # Election no longer exists - refresh the view to show current elections
            view = self.view
            if isinstance(view, ElectableView):
                view.selected_election_id = None
                view.elections = db.load_elections_by_creator(
                    interaction.channel_id, interaction.user.id
                )
                view.build_view()
                await interaction.response.edit_message(**view.get_content())
            return

        class ConfirmModal(LocalizedModal, title=_("Confirm Delete Election")):
            confirm = discord.ui.TextInput(
                # Translators: keep "DELETE" in English; users must type it exactly.
                label=_('Type "DELETE" to delete this election'),
                placeholder="DELETE",
                max_length=6,
            )

            async def on_submit(inner_self, interaction: discord.Interaction):
                if inner_self.confirm.value.strip().upper() != "DELETE":
                    await interaction.response.send_message(
                        _("Election not deleted. Confirmation text did not match."),
                        ephemeral=True,
                    )
                    return

                # Delete the public message if it exists
                if election.message_id:
                    try:
                        channel = interaction.channel
                        message = await channel.fetch_message(election.message_id)
                        await message.delete()
                    except discord.NotFound:
                        pass  # Message was already deleted

                # Delete the election from database
                db.delete_election(election.election_id)

                # Update the parent view and go back to the election list
                view = self.view
                if isinstance(view, ElectableView):
                    view.selected_election_id = None
                    view.elections = db.load_elections_by_creator(
                        interaction.channel_id, interaction.user.id
                    )
                    view.build_view()
                    await interaction.response.edit_message(**view.get_content())

        await interaction.response.send_modal(ConfirmModal())


async def show_electable(interaction: discord.Interaction):
    """Show the electable command interface."""
    with use_locale(interaction.locale.value):
        view = ElectableView(interaction)
        await interaction.response.send_message(**view.get_content(), ephemeral=True)
