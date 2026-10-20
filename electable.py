"""Unified command interface for managing elections."""

import discord
from typing import Any
import db
from election import load_election_from_db, end_election_and_update_message
from setup import ElectionSetup
import time_utils
import election_checker
from i18n import LocalizedModal, LocalizedView, _, ngettext, use_locale


class ElectableView(LocalizedView):
    """Main view for the /electable command."""

    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.channel_id = interaction.channel_id
        self.user_id = interaction.user.id
        self.selected_election_id: int | None = None

    def get_content(self) -> dict[str, Any]:
        """Rebuild the view from the current elections, and return it as
        message fields."""
        self.clear_items()
        election = (
            load_election_from_db(self.selected_election_id)
            if self.selected_election_id
            else None
        )
        if election:
            self.show_election(election)
        else:
            # The election may have been deleted elsewhere.
            self.selected_election_id = None
            self.show_list()
        return {"view": self}

    def show_list(self):
        """Show the user's elections in this channel."""
        elections = db.load_elections_by_creator(self.channel_id, self.user_id)
        if elections:
            self.add_item(discord.ui.ActionRow(ElectionSelect(elections)))
        self.add_item(discord.ui.ActionRow(CreateNewButton()))

    def show_election(self, election):
        """Show the management screen for an election."""
        vote_count = db.get_vote_count(election.election_id)
        end_time = time_utils.format_timestamp_discord(election.end_timestamp)
        candidates = "\n".join(f"- {c}" for c in election.candidates)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {election.title}"),
                discord.ui.TextDisplay(
                    _("**Method**:\n{method}").format(
                        method=election.method_description(election.method_params)
                    )
                ),
                discord.ui.TextDisplay(
                    _("**Candidates**:\n{candidates}").format(candidates=candidates)
                ),
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        _("**Ends**:\n{end_time}").format(end_time=end_time)
                    ),
                    accessory=RescheduleButton(election.election_id),
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    "-# "
                    + ngettext("{n} vote cast", "{n} votes cast", vote_count).format(
                        n=vote_count
                    )
                ),
            )
        )
        self.add_item(
            discord.ui.ActionRow(
                BackButton(),
                EndNowButton(election.election_id),
                DeleteButton(election.election_id),
            )
        )


async def _show_list(view: ElectableView, interaction: discord.Interaction):
    """Go back to the list of elections."""
    view.selected_election_id = None
    await interaction.response.edit_message(**view.get_content())


class ElectionSelect(discord.ui.Select):
    """Dropdown to select an election to manage."""

    def __init__(self, elections: list[dict[str, Any]]):
        options = []
        for e_data in elections[:25]:  # Discord limit
            vote_count = db.get_vote_count(e_data["election_id"])
            options.append(
                discord.SelectOption(
                    label=e_data["title"][:100],  # Discord limit
                    value=str(e_data["election_id"]),
                    description=ngettext("{n} vote", "{n} votes", vote_count).format(
                        n=vote_count
                    ),
                )
            )

        super().__init__(placeholder=_("Select an election to manage"), options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_election_id = int(self.values[0])
        await interaction.response.edit_message(**self.view.get_content())


class BackButton(discord.ui.Button):
    """Button to go back to the election list."""

    def __init__(self):
        super().__init__(label=_("← Back"), style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await _show_list(self.view, interaction)


class CreateNewButton(discord.ui.Button):
    """Button to create a new election."""

    def __init__(self):
        super().__init__(
            label=_("Create New Election"), style=discord.ButtonStyle.success
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
        super().__init__(label=_("Reschedule"), style=discord.ButtonStyle.primary)
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            await _show_list(self.view, interaction)
            return

        parent_view = self.view

        class RescheduleModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(title=_("Reschedule Election"))
                inner_self.end_time = discord.ui.TextInput(required=False)
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("New End Time"),
                        # Translators: keep the examples as they are; only these formats can be parsed.
                        description=_("Examples: 2d, 3h30m, 2025-12-25 14:30"),
                        component=inner_self.end_time,
                    )
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
                await interaction.response.edit_message(**parent_view.get_content())

        await interaction.response.send_modal(RescheduleModal())


class ConfirmModal(LocalizedModal):
    """Asks the user to confirm with a checkbox, which they must check to
    submit the form."""

    def __init__(self, title: str, question: str, answer: str, on_confirm):
        super().__init__(title=title)
        self.on_confirm = on_confirm
        self.confirm = discord.ui.CheckboxGroup(
            required=True,
            min_values=1,
            options=[discord.CheckboxGroupOption(label=answer, value="yes")],
        )
        self.add_item(discord.ui.Label(text=question, component=self.confirm))

    async def on_submit(self, interaction: discord.Interaction):
        if "yes" in self.confirm.values:
            await self.on_confirm(interaction)


class EndNowButton(discord.ui.Button):
    """Button to end an election immediately."""

    def __init__(self, election_id: int):
        super().__init__(label=_("End Now"), style=discord.ButtonStyle.danger)
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            await _show_list(self.view, interaction)
            return

        async def end(interaction: discord.Interaction):
            # Posting results can take a moment for long tabulations.
            await interaction.response.defer()
            await end_election_and_update_message(
                election, interaction.channel, include_announcement=False
            )
            self.view.selected_election_id = None
            await interaction.edit_original_response(**self.view.get_content())

        await interaction.response.send_modal(
            ConfirmModal(
                _("Confirm End Election"),
                _("End this election now?"),
                _("Yes, end it and post the results"),
                end,
            )
        )


class DeleteButton(discord.ui.Button):
    """Button to delete an election without showing results."""

    def __init__(self, election_id: int):
        super().__init__(label=_("Delete"), style=discord.ButtonStyle.danger)
        self.election_id = election_id

    async def callback(self, interaction: discord.Interaction):
        election = load_election_from_db(self.election_id)
        if not election:
            await _show_list(self.view, interaction)
            return

        async def delete(interaction: discord.Interaction):
            # Delete the public message if it exists
            if election.message_id:
                try:
                    message = await interaction.channel.fetch_message(
                        election.message_id
                    )
                    await message.delete()
                except discord.NotFound:
                    pass  # Message was already deleted

            db.delete_election(election.election_id)
            await _show_list(self.view, interaction)

        await interaction.response.send_modal(
            ConfirmModal(
                _("Confirm Delete Election"),
                _("Delete this election?"),
                _("Yes, delete it without posting results"),
                delete,
            )
        )


async def show_electable(interaction: discord.Interaction):
    """Show the electable command interface."""
    with use_locale(interaction.locale.value):
        view = ElectableView(interaction)
        await interaction.response.send_message(**view.get_content(), ephemeral=True)
