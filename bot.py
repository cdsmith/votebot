import os
import discord
import dotenv
from election import set_client
import methods
import db
import electable
import election_checker
from i18n import N_, CommandTranslator

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


# Discord error codes for things that no longer exist
UNKNOWN_CHANNEL = 10003
UNKNOWN_MESSAGE = 10008

# on_ready runs again after reconnects, but registered views survive those,
# so startup work only needs to happen once.
_started = False


@client.event
async def on_ready():
    global _started
    if _started:
        return
    _started = True

    # Initialize database
    db.init_db()

    # Details buttons on results messages work by their custom IDs.
    from election import DetailsButton

    client.add_dynamic_items(DetailsButton)

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
                except discord.NotFound as e:
                    # The post or its channel was deleted while the bot was
                    # offline.  The post is the election, so it's gone too.
                    if e.code in (UNKNOWN_CHANNEL, UNKNOWN_MESSAGE):
                        db.delete_election(election.election_id)
                        print(f"Deleted election {election.election_id}: post is gone")
                except discord.HTTPException as e:
                    print(f"Error restoring election {election.election_id}: {e}")

    # Start background task for checking expired elections
    election_checker.start()

    await tree.set_translator(CommandTranslator())
    await tree.sync()
    print(f"{client.user} has connected to Discord!")


# An election's public post is the election, so deleting the post (which
# takes Manage Messages, or the bot itself) or its channel deletes the election.


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    db.delete_elections_by_message([payload.message_id])


@client.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    db.delete_elections_by_message(payload.message_ids)


@client.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    db.delete_elections_in_channel(channel.id)


@client.event
async def on_raw_thread_delete(payload: discord.RawThreadDeleteEvent):
    db.delete_elections_in_channel(payload.thread_id)


@client.event
async def on_guild_remove(guild: discord.Guild):
    # The bot was removed from the server, so its elections there can never
    # finish.  The privacy policy promises they're deleted.
    for channel in [*guild.channels, *guild.threads]:
        db.delete_elections_in_channel(channel.id)


@tree.command(name="electable", description=N_("Manage your elections."))
async def electable_command(interaction: discord.Interaction):
    """Unified command for managing elections."""
    await electable.show_electable(interaction)


client.run(TOKEN)
