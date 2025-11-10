import os
import discord
import dotenv
from election import set_client
import methods
import db
import electable
import election_checker

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

    # Set client reference for election_checker to use
    election_checker.set_client(client)

    # Re-attach Vote buttons to existing elections
    from election import load_election_from_db

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

    # Start background task for checking expired elections
    if not election_checker.check_expired_elections.is_running():
        election_checker.check_expired_elections.start()

    await tree.sync()
    print(f"{client.user} has connected to Discord!")


@tree.command(name="electable", description="Manage your elections.")
async def electable_command(interaction: discord.Interaction):
    """Unified command for managing elections."""
    await electable.show_electable(interaction)


client.run(TOKEN)
