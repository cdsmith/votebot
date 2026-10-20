import discord
import db
from election import Election
import methods
from typing import Any, Callable
import asyncio
import time
import time_utils
from i18n import (
    LocalizedModal,
    LocalizedView,
    _,
    available_locales,
    language_name,
    ngettext,
    supported_locale,
)
from layout import notice
from text_utils import SELECT_OPTION_LIMIT, truncate

# Input limits chosen to fit Discord's limits wherever these are displayed:
# button labels (80), select option labels (100), and headings.
TITLE_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 2000
CANDIDATE_MAX_LENGTH = 80
MAX_CANDIDATES = 20

# Select value for English, which has no locale code (Discord doesn't allow
# empty values)
ENGLISH = "en"

# How long an idle setup stays usable
SETUP_TIMEOUT_SECONDS = 3600


class OpenModalButton(discord.ui.Button):
    """A button that opens a form."""

    def __init__(self, label: str, make_modal: Callable[[], discord.ui.Modal], **kwargs):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, **kwargs)
        self.make_modal = make_modal

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(self.make_modal())


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
        self.channel_id: int | None = None
        self.shared: bool = False  # Managed by anyone who can use /electable
        self.current_view: discord.ui.View | None = None  # Most recently rendered view

    def abandon(self):
        """Give up on this setup, e.g. after it has been idle too long."""
        if self.future and not self.future.done():
            self.future.set_result(None)

    def new_view(self) -> discord.ui.LayoutView:
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

    def set_method(self, method: str):
        """Choose the election method by name."""
        if not self.method_class or self.method_class.method_name() != method:
            self.method_class = methods.NAMED_METHODS[method]
            self.method_params = self.method_class.default_method_params()

    def method_options(self) -> list[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=_(name),
                value=name,
                default=bool(self.method_class)
                and self.method_class.method_name() == name,
            )
            for name in methods.NAMED_METHODS
        ]

    def set_end_time(self, end_time_str: str) -> str | None:
        """Set the end time from what the user typed, returning an error
        message if it isn't valid."""
        end_timestamp, error = time_utils.validate_time_input(end_time_str)
        if not error:
            self.end_time_str = end_time_str
            self.end_timestamp = end_timestamp
        return error

    def end_time_label(self, text_input: discord.ui.TextInput) -> discord.ui.Label:
        return discord.ui.Label(
            text=_("End Time (optional)"),
            # Translators: keep the examples as they are; only these formats can be parsed.
            description=_("Examples: 2d, 3h30m, 2025-12-25 14:30"),
            component=text_input,
        )

    async def start(
        self, interaction: discord.Interaction, parent_view=None
    ) -> tuple[int, str, Election] | None:
        self.parent_view = parent_view
        self.channel_id = interaction.channel_id
        # Public messages default to the server's language.
        if interaction.guild_locale:
            self.locale = supported_locale(interaction.guild_locale.value)

        class NewModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(
                    title=_("Create Election"), timeout=SETUP_TIMEOUT_SECONDS
                )
                inner_self.title_field = discord.ui.TextInput(
                    default=self.title, max_length=TITLE_MAX_LENGTH
                )
                inner_self.description = discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    default=self.description,
                    required=False,
                    max_length=DESCRIPTION_MAX_LENGTH,
                )
                inner_self.end_time = discord.ui.TextInput(
                    default=self.end_time_str, required=False
                )
                inner_self.method = discord.ui.Select(
                    placeholder=_("Select Method"),
                    options=self.method_options(),
                    required=False,
                )
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("Election Title"), component=inner_self.title_field
                    )
                )
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("Description"), component=inner_self.description
                    )
                )
                inner_self.add_item(self.end_time_label(inner_self.end_time))
                inner_self.add_item(
                    discord.ui.Label(text=_("Method"), component=inner_self.method)
                )

            async def on_submit(inner_self, interaction: discord.Interaction):
                self.title = inner_self.title_field.value
                self.description = inner_self.description.value
                if inner_self.method.values:
                    self.set_method(inner_self.method.values[0])
                error = self.set_end_time(inner_self.end_time.value)
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
        await interaction.response.send_modal(NewModal())
        try:
            return await self.future
        finally:
            if self.current_view:
                self.current_view.stop()

    def title_modal(self) -> discord.ui.Modal:
        """A form to edit the title and description."""

        class TitleModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(title=_("Edit Attributes"))
                inner_self.title_field = discord.ui.TextInput(
                    default=self.title, max_length=TITLE_MAX_LENGTH
                )
                inner_self.description = discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    default=self.description,
                    required=False,
                    max_length=DESCRIPTION_MAX_LENGTH,
                )
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("Election Title"), component=inner_self.title_field
                    )
                )
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("Description"), component=inner_self.description
                    )
                )

            async def on_submit(inner_self, interaction: discord.Interaction):
                self.title = inner_self.title_field.value
                self.description = inner_self.description.value
                await interaction.response.edit_message(**self.get_setup_message())

        return TitleModal()

    def end_time_modal(self) -> discord.ui.Modal:
        """A form to edit the end time."""

        class EndTimeModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(title=_("Edit Attributes"))
                inner_self.end_time = discord.ui.TextInput(
                    default=self.end_time_str, required=False
                )
                inner_self.add_item(self.end_time_label(inner_self.end_time))

            async def on_submit(inner_self, interaction: discord.Interaction):
                error = self.set_end_time(inner_self.end_time.value)
                if error:
                    await interaction.response.send_message(
                        _("Error: {error}").format(error=error),
                        ephemeral=True,
                        delete_after=10,
                    )
                    return
                await interaction.response.edit_message(**self.get_setup_message())

        return EndTimeModal()

    def params_modal(self) -> discord.ui.Modal:
        """A form to configure the method's parameters."""

        class ParamsModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(title=_("Configure Method"))
                inner_self.fields = {}
                for param in self.method_class.method_param_names():
                    current = self.method_params.get(param, "")
                    choices = self.method_class.method_param_choices(
                        param, self.candidates
                    )
                    if choices and len(choices) <= 25:
                        field = discord.ui.Select(
                            options=[
                                discord.SelectOption(
                                    label=c, value=c, default=c == current
                                )
                                for c in choices
                            ]
                        )
                    else:
                        field = discord.ui.TextInput(default=current)
                    inner_self.fields[param] = field
                    inner_self.add_item(
                        discord.ui.Label(text=_(param), component=field)
                    )

            async def on_submit(inner_self, interaction: discord.Interaction):
                for param, field in inner_self.fields.items():
                    if isinstance(field, discord.ui.Select):
                        if field.values:
                            self.method_params[param] = field.values[0]
                    else:
                        self.method_params[param] = field.value
                await interaction.response.edit_message(**self.get_setup_message())

        return ParamsModal()

    def candidates_modal(self) -> discord.ui.Modal:
        """A form to add candidates, one per line."""

        class CandidatesModal(LocalizedModal):
            def __init__(inner_self):
                super().__init__(title=_("Add Candidate"))
                inner_self.names = discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    max_length=MAX_CANDIDATES * (CANDIDATE_MAX_LENGTH + 1),
                )
                inner_self.add_item(
                    discord.ui.Label(
                        text=_("Candidate Names"),
                        description=_("One per line"),
                        component=inner_self.names,
                    )
                )

            async def on_submit(inner_self, interaction: discord.Interaction):
                problems = []
                for line in inner_self.names.value.split("\n"):
                    name = line.strip()
                    if not name:
                        continue
                    if name in self.candidates:
                        problems.append(
                            _("**{name}** is already a candidate.").format(name=name)
                        )
                    elif len(name) > CANDIDATE_MAX_LENGTH:
                        problems.append(
                            ngettext(
                                "**{name}** is too long. Candidate names can have "
                                "at most {n} character.",
                                "**{name}** is too long. Candidate names can have "
                                "at most {n} characters.",
                                CANDIDATE_MAX_LENGTH,
                            ).format(
                                name=truncate(name, CANDIDATE_MAX_LENGTH),
                                n=CANDIDATE_MAX_LENGTH,
                            )
                        )
                    elif len(self.candidates) >= MAX_CANDIDATES:
                        problems.append(
                            ngettext(
                                "An election can have at most {n} candidate.",
                                "An election can have at most {n} candidates.",
                                MAX_CANDIDATES,
                            ).format(n=MAX_CANDIDATES)
                        )
                        break
                    else:
                        self.candidates.append(name)
                await interaction.response.edit_message(**self.get_setup_message())
                if problems:
                    await interaction.followup.send("\n".join(problems), ephemeral=True)

        return CandidatesModal()

    def get_setup_message(self) -> dict[str, Any]:
        """Return the message showing the current setup of the election."""

        class MethodSelect(discord.ui.Select):
            def __init__(inner_self):
                super().__init__(
                    placeholder=_("Select Method"), options=self.method_options()
                )

            async def callback(inner_self, interaction: discord.Interaction):
                self.set_method(inner_self.values[0])
                await interaction.response.edit_message(**self.get_setup_message())

        class LanguageSelect(discord.ui.Select):
            def __init__(inner_self):
                # Sorted by name like Discord's own language menu, which puts
                # names in Latin script first.
                locales = sorted(
                    [None] + available_locales(),
                    key=lambda l: language_name(l).casefold(),
                )
                super().__init__(
                    options=[
                        discord.SelectOption(
                            label=language_name(locale),
                            value=locale or ENGLISH,
                            default=locale == self.locale,
                        )
                        for locale in locales
                    ]
                )

            async def callback(inner_self, interaction: discord.Interaction):
                value = inner_self.values[0]
                self.locale = None if value == ENGLISH else value
                await interaction.response.edit_message(**self.get_setup_message())

        class ManagerSelect(discord.ui.Select):
            def __init__(inner_self):
                super().__init__(
                    options=[
                        discord.SelectOption(
                            label=_("Only me"),
                            description=_(
                                "The election shows you as the person running it."
                            ),
                            value="personal",
                            default=not self.shared,
                        ),
                        discord.SelectOption(
                            label=_("Anyone who can use /electable here"),
                            description=_(
                                "The election doesn't show who is running it."
                            ),
                            value="shared",
                            default=self.shared,
                        ),
                    ]
                )

            async def callback(inner_self, interaction: discord.Interaction):
                self.shared = inner_self.values[0] == "shared"
                await interaction.response.edit_message(**self.get_setup_message())

        class RemoveCandidateSelect(discord.ui.Select):
            def __init__(inner_self):
                super().__init__(
                    placeholder=_("Remove Candidate"),
                    min_values=1,
                    max_values=len(self.candidates),
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
                )

            async def callback(inner_self, interaction: discord.Interaction):
                for name in inner_self.values:
                    if name in self.candidates:
                        self.candidates.remove(name)
                await interaction.response.edit_message(**self.get_setup_message())

        class StartElectionButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(
                    label=_("Start Election"),
                    style=discord.ButtonStyle.success,
                    disabled=bool(self.invalid_reason()),
                )

            async def callback(inner_self, interaction: discord.Interaction):
                if not self.future or self.future.done():
                    return

                # Check if scheduled end time has already passed
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
                    shared=self.shared,
                )

                # Return the election to the caller - don't edit the message here
                # The caller will handle updating the view
                self.future.set_result(
                    (interaction.channel_id, self.title, election, interaction)
                )

        class CancelSetupButton(discord.ui.Button):
            def __init__(inner_self):
                super().__init__(label=_("Cancel"), style=discord.ButtonStyle.danger)

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
                            view=notice(_("Setup canceled."))
                        )

        title = self.title or _("*No title set.*")
        desc = truncate(self.description, 300) or _("*No description set.*")
        cands = "\n".join(f"- {c}" for c in self.candidates) or _(
            "*No candidates yet.*"
        )
        end_time = time_utils.format_timestamp_discord(self.end_timestamp)

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    _("**Setting up Election**:\n{title}").format(title=title)
                ),
                discord.ui.TextDisplay(
                    _("**Description**:\n{description}").format(description=desc)
                ),
                accessory=OpenModalButton(_("Edit"), self.title_modal),
            ),
            discord.ui.Separator(),
            # The dropdowns show the current choices, so these are just headings.
            discord.ui.TextDisplay("**{}**".format(_("Method"))),
            discord.ui.ActionRow(MethodSelect()),
        )
        if self.method_class and self.method_class.method_param_names():
            params = "\n".join(
                "**{}**: {}".format(_(param), self.method_params.get(param, ""))
                for param in self.method_class.method_param_names()
            )
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(params),
                    accessory=OpenModalButton(_("Edit"), self.params_modal),
                )
            )
        if available_locales():
            container.add_item(discord.ui.TextDisplay("**{}**".format(_("Language"))))
            container.add_item(discord.ui.ActionRow(LanguageSelect()))
        container.add_item(
            discord.ui.TextDisplay("**{}**".format(_("Who can manage this election")))
        )
        container.add_item(discord.ui.ActionRow(ManagerSelect()))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    _("**Candidates**:\n{candidates}").format(candidates=cands)
                ),
                accessory=OpenModalButton(
                    _("Add Candidate"),
                    self.candidates_modal,
                    disabled=len(self.candidates) >= MAX_CANDIDATES,
                ),
            )
        )
        if self.candidates:
            container.add_item(discord.ui.ActionRow(RemoveCandidateSelect()))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    _("**Ends**:\n{end_time}").format(end_time=end_time)
                ),
                accessory=OpenModalButton(_("Edit"), self.end_time_modal),
            )
        )

        view = self.new_view()
        view.add_item(container)
        invalid = self.invalid_reason()
        if invalid:
            view.add_item(discord.ui.TextDisplay(f":warning: {invalid}"))
        view.add_item(discord.ui.ActionRow(StartElectionButton(), CancelSetupButton()))
        return {"view": view}

    def invalid_reason(self) -> str | None:
        if not self.title:
            return _("No title was set.")
        if self.channel_id and db.load_election_by_natural_key(
            self.channel_id, self.title
        ):
            return _(
                "An election with the title `{title}` is already ongoing in "
                "this channel."
            ).format(title=self.title)
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
