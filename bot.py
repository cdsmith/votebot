import os
import discord
import dotenv
from election import Election
from elections.plurality import PluralityElection
from elections.approval import ApprovalElection
from elections.copeland import CopelandElection
from elections.score import ScoreElection
from elections.star import STARElection

dotenv.load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

METHODS = {
    "Plurality": PluralityElection,
    "Approval": ApprovalElection,
    "Copeland": CopelandElection,
    "Score": ScoreElection,
    "STAR": STARElection,
}

method_choices = [
    discord.app_commands.Choice(name=name, value=name) for name in METHODS
]

ongoing_elections: dict[int, Election] = {}


@client.event
async def on_ready():
    await tree.sync()
    print(f"{client.user} has connected to Discord!")


@tree.command(name="election", description="Start a new election.")
@discord.app_commands.describe(
    method="The voting method (e.g. Plurality, Approval)",
    title="The title of the election",
    description="A description of the election",
    candidates="A comma-separated list of candidates",
)
@discord.app_commands.choices(method=method_choices)
async def start_election(
    interaction: discord.Interaction,
    method: str,
    title: str,
    candidates: str,
    description: str = "",
):
    method_class = METHODS.get(method)
    if not method_class:
        await interaction.response.send_message(
            f"Unknown method `{method}`. Available methods: {', '.join(METHODS.keys())}",
            ephemeral=True,
        )
        return
    candidate_list = [c.strip() for c in candidates.split(",") if c.strip()]
    if len(candidate_list) < 2:
        await interaction.response.send_message(
            "You must provide at least two candidates.", ephemeral=True
        )
        return

    election = method_class(
        title=title, description=description, candidates=candidate_list
    )
    ongoing_elections[interaction.channel_id] = election

    await interaction.response.send_message(**election.get_public_view())


@tree.command(
    name="end_election", description="Ends the current election and shows results."
)
@discord.app_commands.describe(
    details="Whether to show detailed results (if false, just the winner)"
)
async def end_election(interaction: discord.Interaction, details: bool):
    election = ongoing_elections.pop(interaction.channel_id, None)
    if not election:
        await interaction.response.send_message(
            "No active election in this channel.", ephemeral=True
        )
        return

    results_embed = election.get_results(show_details=details)
    await interaction.response.send_message(embed=results_embed)


client.run(TOKEN)
