import discord
from election import Election
import methods
from typing import Any
import asyncio
import math
from i18n import (
    LocalizedModal,
    LocalizedView,
    _,
    available_locales,
    language_name,
    supported_locale,
)
from text_utils import MESSAGE_CONTENT_LIMIT, SELECT_OPTION_LIMIT, truncate

# Input limits chosen to fit Discord's limits wherever these are displayed:
# button labels (80), select option labels (100), and embed titles (256).
TITLE_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 2000
CANDIDATE_MAX_LENGTH = 80

# Select value for English, which has no locale code (Discord doesn't allow
# empty values)
ENGLISH = "en"

# How long an idle setup stays usable
SETUP_TIMEOUT_SECONDS = 3600


class ElectionSetup:
    def __init__(self):
        self.future: asyncio.Future = None
        self.title: str = ""
        self.method_class: type | None = ""
        self.method_params: dict[str, str] = {}
        self.description: str = ""
        self.candidates: list[str] = []
        self.end_time_str: str = ""
        self.end_timestamp: int | None = None
        self.locale: str | None = None  # Language of the election's public messages
        self.current_view: discord.ui.View | None = None  # Most recently rendered view

    def abandon(self):
        """Give up on this setup, e.g. after it has been idle too long."""
        if self.future and not self.future.done():
            self.future.set_result(None)

    def new_view(self) -> discord.ui.View:
        """Return a new, empty view to replace the current one."""

        class SetupView(LocalizedView):
            async def on_timeout(inner_self):
                self.abandon()

        # Only the latest view is live; stopping the old one also keeps its
        # timeout from abandoning the setup.
        if self.current_view:
            self.current_view.stop()
        self.current_view = SetupView(timeout=SETUP_TIMEOUT_SECONDS)
        return self.current_view

    async def start(
        self, interaction: discord.Interaction, parent_view=None
    ) -> tuple[int, str, Election] | None:
        self.parent_view = parent_view
        # Public messages default to the server's language.
        if interaction.guild_locale:
            self.locale = supported_locale(interaction.guild_locale.value)

        class NewModal(LocalizedModal, title=_("Create Election")):
            title_field = discord.ui.TextInput(
                label=_("Election Title"),
                default=self.title,
                max_length=TITLE_MAX_LENGTH,
            )
            description = discord.ui.TextInput(
                label=_("Description"),
                style=discord.TextStyle.paragraph,
                default=self.description,
                required=False,
                max_length=DESCRIPTION_MAX_LENGTH,
            )
            end_time = discord.ui.TextInput(
                label=_("End Time (optional)"),
                placeholder=_("Examples: 2d, 3h30m, 2025-12-25 14:30"),
                default=self.end_time_str,
                required=False,
            )

            async def on_submit(inner_self, interaction: discord.Interaction):
                import time_utils

                self.title = inner_self.title_field.value
                self.description = inner_self.description.value
                self.end_time_str = inner_self.end_time.value

                # Parse and validate end time
                self.end_timestamp, error = time_utils.validate_time_input(
                    self.end_time_str
                )
                if error:
                    await interaction.response.send_message(
                        _("Error: {error}").format(error=error),
                        ephemeral=True,
                        delete_after=10,
                    )
                    self.abandon()
                    return

                # Edit the original ephemeral message (from the button click) to show setup UI
                # We need to use interaction.edit_original_response() because the message is ephemeral
                await interaction.response.defer()
                await interaction.edit_original_response(**self.get_setup_message())

            async def on_timeout(inner_self):
                self.abandon()

        self.future = asyncio.Future()
        await interaction.response.send_modal(NewModal(timeout=SETUP_TIMEOUT_SECONDS))
        try:
            return await self.future
        finally:
            if self.current_view:
                self.current_view.stop()

    def get_setup_message(self) -> dict[str, Any]:
        """Return a string describing the current 'setup' state of the Election."""

        class MethodSelect(discord.ui.Select):
            def __init__(inner_self):
                super().__init__(
                    placeholder=(
                        _(self.method_class.method_name())
                        if self.method_class
                        else _("Select Method")
                    ),
                    options=[
                        discord.SelectOption(label=_(name), value=name)
                        for name in methods.NAMED_METHODS
                    ],
                    row=0,
                )

            async def callback(inner_self, interaction: discord.Interaction):
                method = inner_self.values[0]
                if method in methods.NAMED_METHODS:
                    if (
                        not self.method_class
                        or self.method_class.method_name() != method
                    ):
                        self.method_class = methods.NAMED_METHODS[method]
                        self.method_params = self.method_class.default_method_params()
                else:
                    self.method_class = None
                    self.method_params = {}

                await interaction.response.edit_message(**self.get_setup_message())

        class ConfigureMethodButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label=_("Configure Method"),
                    style=discord.ButtonStyle.primary,
                    row=1,
                )

            async def callback(inner_self, interaction: discord.Interaction):
                class ConfigureMethodModal(LocalizedModal):
                    param_fields = {}

                    def __init__(inner_self):
                        super().__init__(title=_("Configure Method"))
                        if self.method_class:
                            for param in self.method_class.method_param_names():
                                field = discord.ui.TextInput(
                                    label=_(param),
                                    default=self.method_params.get(param, ""),
                                )
                                inner_self.add_item(field)
                                inner_self.param_fields[param] = field

                    async def on_submit(inner_self, interaction: discord.Interaction):
                        self.method_params = {
                            param: field.value
                            for param, field in inner_self.param_fields.items()
                        }
                        await interaction.response.edit_message(
                            **self.get_setup_message()
                        )

                await interaction.response.send_modal(ConfigureMethodModal())

        class LanguageButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    label=_("Language"), style=discord.ButtonStyle.primary, row=1
                )

            async def callback(inner_self, interaction: discord.Interaction):
                await interaction.response.edit_message(**self.get_language_message())

        class AddCandidateButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label=_("Add Candidate"), style=discord.ButtonStyle.primary, row=2
                )

            async def callback(inner_self, interaction: discord.Interaction):
                class AddCandidateModal(LocalizedModal, title=_("Add a Candidate")):
                    candidate_name = discord.ui.TextInput(
                        label=_("Candidate Name"), max_length=CANDIDATE_MAX_LENGTH
                    )

                    async def on_submit(inner_self, interaction: discord.Interaction):
                        new_name = inner_self.candidate_name.value.strip()
                        if new_name in self.candidates:
                            await interaction.response.send_message(
                                content=_("**{name}** is already a candidate.").format(
                                    name=new_name
                                ),
                                ephemeral=True,
                                delete_after=5,
                            )
                            return
                        if new_name:
                            self.candidates.append(new_name)
                        await interaction.response.edit_message(
                            **self.get_setup_message()
                        )

                await interaction.response.send_modal(AddCandidateModal())

        class RemoveCandidateSelect(discord.ui.Select):
            def __init__(inner_self):
                super().__init__(
                    placeholder=_("Remove Candidate"),
                    options=[
                        discord.SelectOption(
                            label=truncate(
                                _("Remove {candidate}").format(candidate=c),
                                SELECT_OPTION_LIMIT,
                            ),
                            value=c,
                        )
                        for c in self.candidates
                    ],
                    row=3,
                )

            async def callback(inner_self, interaction: discord.Interaction):
                remove_name = inner_self.values[0].strip()
                if remove_name in self.candidates:
                    self.candidates.remove(remove_name)
                await interaction.response.edit_message(**self.get_setup_message())

        class StartElectionButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    label=_("Start Election"),
                    style=discord.ButtonStyle.success,
                    disabled=bool(self.invalid_reason()),
                    row=4,
                )

            async def callback(inner_self, interaction: discord.Interaction):
                if not self.future or self.future.done():
                    return

                # Check if scheduled end time has already passed
                import time

                if self.end_timestamp and self.end_timestamp <= int(time.time()):
                    await interaction.response.send_message(
                        _(
                            "Error: The scheduled end time has already passed. Please "
                            "reschedule or remove the end time."
                        ),
                        ephemeral=True,
                        delete_after=10,
                    )
                    return

                election = self.method_class(
                    title=self.title,
                    description=self.description,
                    candidates=self.candidates,
                    method_params=self.method_params,
                    creator_id=interaction.user.id,
                    end_timestamp=self.end_timestamp,
                    locale=self.locale,
                )

                # Return the election to the caller - don't edit the message here
                # The caller will handle updating the view
                self.future.set_result(
                    (interaction.channel_id, self.title, election, interaction)
                )

        class EditButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label=_("Edit"), style=discord.ButtonStyle.primary, row=4
                )

            async def callback(inner_self, interaction: discord.Interaction):
                class EditModal(LocalizedModal, title=_("Edit Attributes")):
                    title_field = discord.ui.TextInput(
                        label=_("Election Title"),
                        default=self.title,
                        max_length=TITLE_MAX_LENGTH,
                    )
                    description = discord.ui.TextInput(
                        label=_("Description"),
                        style=discord.TextStyle.paragraph,
                        default=self.description,
                        required=False,
                        max_length=DESCRIPTION_MAX_LENGTH,
                    )
                    end_time = discord.ui.TextInput(
                        label=_("End Time (optional)"),
                        placeholder=_("Examples: 2d, 3h30m, 2025-12-25 14:30"),
                        default=self.end_time_str,
                        required=False,
                    )

                    async def on_submit(inner_self, interaction: discord.Interaction):
                        import time_utils

                        self.description = inner_self.description.value
                        self.title = inner_self.title_field.value
                        self.end_time_str = inner_self.end_time.value

                        # Parse and validate end time
                        self.end_timestamp, error = time_utils.validate_time_input(
                            self.end_time_str
                        )
                        if error:
                            await interaction.response.send_message(
                                _("Error: {error}").format(error=error),
                                ephemeral=True,
                                delete_after=10,
                            )
                            return

                        await interaction.response.edit_message(
                            **self.get_setup_message()
                        )

                await interaction.response.send_modal(EditModal())

        class CancelSetupButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    label=_("Cancel"), style=discord.ButtonStyle.danger, row=4
                )

            async def callback(inner_self, interaction: discord.Interaction):
                if self.future and not self.future.done():
                    self.future.set_result(None)
                    # Edit back to the parent view
                    if self.parent_view:
                        await interaction.response.edit_message(
                            **self.parent_view.get_content()
                        )
                    else:
                        await interaction.response.edit_message(
                            content=_("Setup canceled."), view=None
                        )

        view = self.new_view()
        view.add_item(MethodSelect())
        if self.method_class and self.method_class.method_param_names():
            view.add_item(ConfigureMethodButton())
        if available_locales():
            view.add_item(LanguageButton())
        if len(self.candidates) < 20:
            view.add_item(AddCandidateButton())
        if self.candidates:
            view.add_item(RemoveCandidateSelect())
        view.add_item(StartElectionButton())
        view.add_item(CancelSetupButton())
        view.add_item(EditButton())

        import time_utils

        title = self.title or _("*No title set.*")
        method = (
            self.method_class.method_description(self.method_params)
            if self.method_class
            else _("*No method set.*")
        )
        desc = truncate(self.description, 300) or _("*No description set.*")
        cands = "\n".join(f"- {c}" for c in self.candidates) or _(
            "*No candidates yet.*"
        )
        end_time = time_utils.format_timestamp_discord(self.end_timestamp)

        fields = [
            _("**Setting up Election**:\n{title}").format(title=title),
            _("**Description**:\n{description}").format(description=desc),
            _("**Method**:\n{method}").format(method=method),
        ]
        # Next to the method, as the Language button is next to Configure Method
        if available_locales():
            fields.append(
                _("**Language**:\n{language}").format(
                    language=language_name(self.locale)
                )
            )
        fields += [
            _("**Candidates**:\n{candidates}").format(candidates=cands),
            _("**Ends**:\n{end_time}").format(end_time=end_time),
        ]
        invalid = self.invalid_reason()
        if invalid:
            fields.append(f":warning: {invalid}")

        return {
            "content": truncate("\n\n".join(fields), MESSAGE_CONTENT_LIMIT),
            "view": view,
        }

    def get_language_message(self) -> dict[str, Any]:
        """Return a message for choosing the election's language."""

        class LanguageSelect(discord.ui.Select):
            def __init__(inner_self, locales: list[str | None]):
                super().__init__(
                    # Show which languages this menu has, e.g. "English … Magyar"
                    placeholder=(
                        f"{language_name(locales[0])} … {language_name(locales[-1])}"
                    ),
                    options=[
                        # Not marked as the default even when it's the current
                        # language, since Discord ignores choosing the default.
                        discord.SelectOption(
                            label=language_name(locale), value=locale or ENGLISH
                        )
                        for locale in locales
                    ],
                )

            async def callback(inner_self, interaction: discord.Interaction):
                value = inner_self.values[0]
                self.locale = None if value == ENGLISH else value
                await interaction.response.edit_message(**self.get_setup_message())

        class BackButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(label=_("← Back"), style=discord.ButtonStyle.secondary)

            async def callback(inner_self, interaction: discord.Interaction):
                await interaction.response.edit_message(**self.get_setup_message())

        # Sorted by name like Discord's own language menu, which puts names in
        # Latin script first.
        locales = sorted(
            [None] + available_locales(), key=lambda l: language_name(l).casefold()
        )
        # Split the languages evenly across as few menus as Discord's limit of
        # 25 options per menu allows.
        menus = math.ceil(len(locales) / 25)
        per_menu = math.ceil(len(locales) / menus)
        view = self.new_view()
        for i in range(0, len(locales), per_menu):
            view.add_item(LanguageSelect(locales[i : i + per_menu]))
        view.add_item(BackButton())
        current = _("**Language**:\n{language}").format(
            language=language_name(self.locale)
        )
        instructions = _(
            "Choose the language for this election's public messages. "
            "Each voter's ballot is in their own language."
        )
        return {"content": f"{current}\n\n{instructions}", "view": view}

    def invalid_reason(self) -> str | None:
        if not self.title:
            return _("No title was set.")
        if not self.method_class:
            return _("No method was set.")
        if not self.candidates or len(self.candidates) < 2:
            return _("At least two candidates are required.")
        param_validation = self.method_class.validate_method_params(
            self.method_params, self.candidates
        )
        if param_validation:
            return param_validation
        return None
