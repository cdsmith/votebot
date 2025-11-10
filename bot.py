import os
import discord
import dotenv
from election import load_election_from_db, set_client
import methods
from setup import ElectionSetup
import db

dotenv.load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# Set client reference for election.py to use
set_client(client)

method_choices = [
    discord.app_commands.Choice(name=name, value=name) for name in methods.NAMED_METHODS
]


@client.event
async def on_ready():
    # Initialize database
    db.init_db()

    # Re-attach Vote buttons to existing elections
    elections = db.load_all_elections()
    for election_data in elections:
        election = load_election_from_db(election_data["election_id"])
        if election.message_id:
            channel = client.get_channel(election.channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(election.message_id)
                    await message.edit(**election.get_public_view())
                except discord.NotFound:
                    pass

    await tree.sync()
    print(f"{client.user} has connected to Discord!")


@tree.command(name="election", description="Create a new election.")
async def create_election(interaction: discord.Interaction):
    result = await ElectionSetup().start(interaction)
    if result:
        channel_id, title, election = result

        # Check if election already exists in database
        existing = db.load_election_by_natural_key(channel_id, title)
        if existing:
            await interaction.response.send_message(
                f"An election with the title `{title}` is already ongoing in this channel.",
                ephemeral=True,
            )
            return

        # Set channel_id and save to database
        election.channel_id = channel_id
        db.save_election(election)

        # Post public message
        message = await interaction.channel.send(**election.get_public_view())
        election.message_id = message.id
        db.save_election(election)  # Update with message_id


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

    # Load election from database
    election_data = db.load_election_by_natural_key(interaction.channel_id, title)
    if not election_data:
        await interaction.response.send_message(
            f"No active election with the title `{title}` in this channel.",
            ephemeral=True,
        )
        return

    election = load_election_from_db(election_data["election_id"])
    if not election:
        await interaction.response.send_message(
            f"Error loading election `{title}`.",
            ephemeral=True,
        )
        return

    results_embed = election.get_results(show_details=details).set_footer(
        text=f"Computed using {election.method_description(election.method_params)}"
    )
    await interaction.response.send_message(embed=results_embed)

    # Delete the election from database (matching old behavior)
    db.delete_election(election.election_id)


client.run(TOKEN)
