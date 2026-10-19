"""Background task for checking and ending expired elections."""

import asyncio
import time
import db
from election import load_election_from_db, end_election_and_update_message


# Will be set by bot.py
client = None

# Maximum time to sleep between checks
MAX_SLEEP_SECONDS = 60

_wake = asyncio.Event()
_task: asyncio.Task | None = None


def set_client(discord_client):
    """Set the Discord client reference."""
    global client
    client = discord_client


def start():
    """Start the background checker, if it isn't already running."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_run())


def trigger_check():
    """Wake the checker to run immediately, e.g. after an end time changes.

    Unlike restarting the task, this never interrupts a check in progress."""
    _wake.set()


async def _run():
    while True:
        # Clear before checking, so a trigger that arrives during the check
        # causes another check rather than being lost.
        _wake.clear()
        try:
            sleep_seconds = await check_expired_elections()
        except Exception as e:
            print(f"Error checking expired elections: {e}")
            sleep_seconds = MAX_SLEEP_SECONDS
        try:
            await asyncio.wait_for(_wake.wait(), timeout=sleep_seconds)
        except asyncio.TimeoutError:
            pass


async def check_expired_elections() -> int:
    """End any expired elections, and return how long to sleep before the next
    check.

    The sleep time is based on the next election end time, so elections end
    promptly rather than waiting for a fixed polling interval.
    """
    # Load only elections ending soon (or already expired)
    elections_ending_soon = db.load_elections_ending_soon(
        within_seconds=MAX_SLEEP_SECONDS
    )
    current_time = int(time.time())
    next_end = current_time + MAX_SLEEP_SECONDS

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

    return min(MAX_SLEEP_SECONDS, max(1, next_end - int(time.time()) + 1))
