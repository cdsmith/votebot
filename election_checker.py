"""Background task for checking and ending expired elections."""

import asyncio
import time
import discord
import db
from election import load_election_from_db, end_election_and_update_message
from i18n import _, use_locale


# Will be set by bot.py
client = None

# Maximum time to sleep between checks
MAX_SLEEP_SECONDS = 60

# Maximum delay between attempts to end an election that keeps failing
MAX_RETRY_SECONDS = 3600

# Elections that failed to end: election ID -> (failure count, next attempt time)
_failures: dict[int, tuple[int, int]] = {}

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


async def notify_creator(election):
    """Tell an election's creator that its results couldn't be posted, since
    otherwise nobody may notice."""
    if not election.creator_id:
        return  # Created before creators were recorded
    try:
        user = await client.fetch_user(election.creator_id)
        with use_locale(election.locale):
            await user.send(
                _(
                    "The results of the election **{title}** couldn't be posted "
                    "in {channel}. Please make sure the bot can see that channel "
                    "and send messages there. It will keep trying."
                ).format(title=election.title, channel=f"<#{election.channel_id}>")
            )
    except discord.HTTPException as e:
        # For example, the creator doesn't accept direct messages.
        print(f"Couldn't notify the creator of election {election.election_id}: {e}")


async def check_expired_elections() -> int:
    """End any expired elections, and return how long to sleep before the next
    check.

    The sleep time is based on the next election end time, so elections end
    promptly rather than waiting for a fixed polling interval.
    """
    # Results are only kept for a limited time.
    db.delete_old_results()

    # Load only elections ending soon (or already expired)
    elections_ending_soon = db.load_elections_ending_soon(
        within_seconds=MAX_SLEEP_SECONDS
    )
    current_time = int(time.time())
    next_end = current_time + MAX_SLEEP_SECONDS

    # End expired elections
    for election_data in elections_ending_soon:
        if election_data["end_timestamp"] <= current_time:
            election_id = election_data["election_id"]
            count, next_attempt = _failures.get(election_id, (0, 0))
            if current_time < next_attempt:
                continue
            election = load_election_from_db(election_id)
            if not election:
                continue

            try:
                # End the election using shared logic
                channel = client.get_channel(election.channel_id)
                if not channel:
                    raise RuntimeError(f"Channel {election.channel_id} not found")
                await end_election_and_update_message(
                    election, channel, include_announcement=True
                )
                _failures.pop(election_id, None)
            except Exception as e:
                # Back off exponentially, so a persistent failure (such as a
                # missing permission) doesn't retry every minute forever.
                count += 1
                delay = min(MAX_SLEEP_SECONDS * 2 ** (count - 1), MAX_RETRY_SECONDS)
                _failures[election_id] = (count, current_time + delay)
                print(
                    f"Error ending election {election_id} (attempt {count}, "
                    f"retrying in {delay}s): {e}"
                )
                if count == 1:
                    await notify_creator(election)
        else:
            next_end = min(next_end, election_data["end_timestamp"])

    return min(MAX_SLEEP_SECONDS, max(1, next_end - int(time.time()) + 1))
