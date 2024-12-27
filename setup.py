import discord
from election import Election
import methods
from typing import Any
import asyncio


class ElectionSetup:
    def __init__(self):
        self.future: asyncio.Future = None
        self.title: str = ""
        self.method_class: type | None = ""
        self.method_params: dict[str, str] = {}
        self.description: str = ""
        self.candidates: list[str] = []

    async def start(
        self, interaction: discord.Interaction
    ) -> tuple[int, str, Election] | None:
        class NewModal(discord.ui.Modal, title="Create Election"):
            title_field = discord.ui.TextInput(
                label="Election Title", default=self.title
            )
            description = discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.paragraph,
                default=self.description,
                required=False,
            )

            async def on_submit(inner_self, interaction: discord.Interaction):
                self.title = inner_self.title_field.value
                self.description = inner_self.description.value
                await interaction.response.send_message(**self.get_setup_message())

        await interaction.response.send_modal(NewModal())
        self.future = asyncio.Future()
        return await self.future

    def get_setup_message(self) -> dict[str, Any]:
        """Return a string describing the current 'setup' state of the Election."""

        class MethodSelect(discord.ui.Select):
            def __init__(_):
                super().__init__(
                    placeholder=self.method_class.method_name()
                    if self.method_class
                    else "Select Method",
                    options=[
                        discord.SelectOption(label=name, value=name)
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
                    label="Configure Method",
                    style=discord.ButtonStyle.primary,
                    row=1,
                )

            async def callback(_, interaction: discord.Interaction):
                class ConfigureMethodModal(discord.ui.Modal):
                    param_fields = {}

                    def __init__(inner_self):
                        super().__init__(title="Configure Method")
                        if self.method_class:
                            for param in self.method_class.method_param_names():
                                field = discord.ui.TextInput(
                                    label=param,
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

        class AddCandidateButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="Add Candidate", style=discord.ButtonStyle.primary, row=2
                )

            async def callback(_, interaction: discord.Interaction):
                class AddCandidateModal(discord.ui.Modal, title="Add a Candidate"):
                    candidate_name = discord.ui.TextInput(
                        label="Candidate Name", max_length=100
                    )

                    async def on_submit(inner_self, interaction: discord.Interaction):
                        new_name = inner_self.candidate_name.value.strip()
                        if new_name in self.candidates:
                            await interaction.response.send_message(
                                content=f"**{new_name}** is already a candidate.",
                                ephemeral=True,
                                delete_after=5,
                            )
                        elif new_name:
                            self.candidates.append(new_name)
                        await interaction.response.edit_message(
                            **self.get_setup_message()
                        )

                await interaction.response.send_modal(AddCandidateModal())

        class RemoveCandidateSelect(discord.ui.Select):
            def __init__(_):
                super().__init__(
                    placeholder="Remove Candidate",
                    options=[
                        discord.SelectOption(label=f"Remove {c}", value=c)
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
            def __init__(_):
                super().__init__(
                    label="Start Election",
                    style=discord.ButtonStyle.success,
                    disabled=bool(self.invalid_reason()),
                    row=4,
                )

            async def callback(_, interaction: discord.Interaction):
                if not self.future or self.future.done():
                    return

                election = self.method_class(
                    title=self.title,
                    description=self.description,
                    candidates=self.candidates,
                    method_params=self.method_params,
                )

                await interaction.response.edit_message(
                    content=f"Election **{self.title}** has started! A public poll has been posted in this channel.",
                    view=None,
                    delete_after=5,
                )

                self.future.set_result((interaction.channel_id, self.title, election))

        class EditButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Edit", style=discord.ButtonStyle.primary, row=4)

            async def callback(_, interaction: discord.Interaction):
                class EditModal(discord.ui.Modal, title="Edit Attributes"):
                    title_field = discord.ui.TextInput(
                        label="Election Title", default=self.title
                    )
                    description = discord.ui.TextInput(
                        label="Description",
                        style=discord.TextStyle.paragraph,
                        default=self.description,
                        required=False,
                    )

                    async def on_submit(inner_self, interaction: discord.Interaction):
                        self.description = inner_self.description.value
                        self.title = inner_self.title_field.value
                        await interaction.response.edit_message(
                            **self.get_setup_message()
                        )

                await interaction.response.send_modal(EditModal())

        class CancelSetupButton(discord.ui.Button):
            def __init__(_):
                super().__init__(
                    label="Cancel", style=discord.ButtonStyle.danger, row=4
                )

            async def callback(_, interaction: discord.Interaction):
                if self.future and not self.future.done():
                    self.future.set_result(None)
                    await interaction.response.edit_message(
                        content="Setup canceled.", view=None
                    )

        view = discord.ui.View(timeout=None)
        view.add_item(MethodSelect())
        if self.method_class and self.method_class.method_param_names():
            view.add_item(ConfigureMethodButton())
        if len(self.candidates) < 20:
            view.add_item(AddCandidateButton())
        if self.candidates:
            view.add_item(RemoveCandidateSelect())
        view.add_item(StartElectionButton())
        view.add_item(CancelSetupButton())
        view.add_item(EditButton())

        title = self.title or "*No title set.*"
        method = (
            self.method_class.method_description(self.method_params)
            if self.method_class
            else "*No method set.*"
        )
        desc = self.description or "*No description set.*"
        cands = "\n".join(f"- {c}" for c in self.candidates) or "*No candidates yet.*"

        fields = [
            f"**Setting up Election**:\n{title}",
            f"**Description**:\n{desc}",
            f"**Method**:\n{method}",
            f"**Candidates**:\n{cands}",
        ]
        invalid = self.invalid_reason()
        if invalid:
            fields.append(f":warning: {invalid}")

        return {
            "content": "\n\n".join(fields),
            "view": view,
        }

    def invalid_reason(self) -> str | None:
        if not self.title:
            return "No title was set."
        if not self.method_class:
            return "No method was set."
        if not self.candidates or len(self.candidates) < 2:
            return "At least two candidates are required."
        param_validation = self.method_class.validate_method_params(
            self.method_params, self.candidates
        )
        if param_validation:
            return param_validation
        return None
