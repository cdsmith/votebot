"""Background task for checking and ending expired elections."""

import discord
from discord.ext import tasks
import db
from election import load_election_from_db, end_election_and_update_message


# Will be set by bot.py
client = None


def set_client(discord_client):
    """Set the Discord client reference."""
    global client
    client = discord_client


@tasks.loop(seconds=60)
async def check_expired_elections():
    """Background task to check for and end expired elections.

    This task dynamically adjusts its sleep time based on the next election end time,
    waking up immediately when an election ends rather than polling at fixed intervals.
    """
    import time

    # Load only elections ending within the next 60 seconds (or already expired)
    elections_ending_soon = db.load_elections_ending_soon(within_seconds=60)
    current_time = int(time.time())
    next_end = current_time + 60

    # End expired elections
    for election_data in elections_ending_soon:
        if election_data["end_timestamp"] <= current_time:
            election = load_election_from_db(election_data["election_id"])
            if not election:
                continue

            try:
                # End the election using shared logic
                channel = client.get_channel(election.channel_id)
                if channel:
                    await end_election_and_update_message(
                        election, channel, include_announcement=True
                    )
            except Exception as e:
                print(f"Error ending election {election.election_id}: {e}")
        else:
            next_end = min(next_end, election_data["end_timestamp"])

    sleep_seconds = min(60, max(1, next_end - current_time + 1))
    check_expired_elections.change_interval(seconds=sleep_seconds)


def trigger_check():
    """Trigger the election check task to run immediately."""
    if check_expired_elections.is_running():
        check_expired_elections.restart()
