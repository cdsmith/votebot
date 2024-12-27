import os
import discord
import dotenv
from election import Election
import methods
from setup import ElectionSetup

dotenv.load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

method_choices = [
    discord.app_commands.Choice(name=name, value=name) for name in methods.NAMED_METHODS
]

ongoing_elections: dict[tuple[int, str], Election] = {}


@client.event
async def on_ready():
    await tree.sync()
    print(f"{client.user} has connected to Discord!")


@tree.command(name="election", description="Create a new election.")
async def create_election(interaction: discord.Interaction):
    result = await ElectionSetup().start(interaction)
    if result:
        channel_id, title, election = result
        key = (channel_id, title)
        if key in ongoing_elections:
            await interaction.response.send_message(
                f"An election with the title `{title}` is already ongoing in this channel.",
                ephemeral=True,
            )
            return
        message = await interaction.channel.send(**election.get_public_view())
        election.original_message = message
        ongoing_elections[key] = election


@tree.command(
    name="end_election",
    description="Ends an election in this channel and shows results.",
)
@discord.app_commands.describe(
    title="The title of the election to end",
    details="Whether to show detailed results (if false, just the winner)",
)
async def end_election(
    interaction: discord.Interaction, title: str, details: bool = True
):
    title = title.strip()
    election = ongoing_elections.pop((interaction.channel_id, title), None)
    if not election:
        await interaction.response.send_message(
            f"No active election with the title `{title}` in this channel.",
            ephemeral=True,
        )
        return
    results_embed = election.get_results(show_details=details).set_footer(
        text=f"Computed using {election.method_description(election.method_params)}"
    )
    await interaction.response.send_message(embed=results_embed)


client.run(TOKEN)
