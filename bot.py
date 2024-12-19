import os
import discord
import dotenv
from election import Election
from elections.plurality import PluralityElection
from elections.approval import ApprovalElection
from elections.copeland import CopelandElection
from elections.score import ScoreElection
from elections.star import STARElection
from elections.irv import IRVElection
from elections.ranked_pairs import RankedPairsElection
from elections.rivestshen import RivestShenGTElection
from elections.tideman_alt import TidemanAlternativeElection

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
    "IRV": IRVElection,
    "Ranked Pairs": RankedPairsElection,
    "Rivest-Shen GT": RivestShenGTElection,
    "Tideman's Alternative Method": TidemanAlternativeElection,
}

method_choices = [
    discord.app_commands.Choice(name=name, value=name) for name in METHODS
]

ongoing_elections: dict[tuple[int, str], Election] = {}


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
    title = title.strip()
    if (interaction.channel_id, title) in ongoing_elections:
        await interaction.response.send_message(
            f"An election with the title `{title}` is already ongoing in this channel.",
            ephemeral=True,
        )
        return

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
    ongoing_elections[(interaction.channel_id, title)] = election

    await interaction.response.send_message(**election.get_public_view())
    election.original_message = await interaction.original_response()


@tree.command(
    name="end_election", description="Ends an election in this channel and shows results."
)
@discord.app_commands.describe(
    title="The title of the election to end",
    details="Whether to show detailed results (if false, just the winner)"
)
async def end_election(interaction: discord.Interaction, title: str, details: bool = True):
    title = title.strip()
    election = ongoing_elections.pop((interaction.channel_id, title), None)
    if not election:
        await interaction.response.send_message(
            f"No active election with the title `{title}` in this channel.",
            ephemeral=True,
        )
        return
    results_embed = election.get_results(show_details=details).set_footer(text=f"Computed using {election.name()}")
    await interaction.response.send_message(embed=results_embed)


client.run(TOKEN)
