import asyncio
import time

import discord
import pytest

import db
import election as election_module
import election_checker
from election import end_election_and_update_message, load_election_from_db
from elections.copeland import CopelandElection
from text_utils import EMBED_TOTAL_LIMIT, EMBEDS_PER_MESSAGE

CANDIDATES = [f"Candidate number {i} with a long name" for i in range(20)]


class FakeChannel:
    def __init__(self, fail=False, fail_after=None):
        self.fail = fail
        self.fail_after = fail_after
        self.sent = []
        self.attempts = 0

    async def send(self, content=None, embeds=()):
        self.attempts += 1
        if self.fail or (self.fail_after is not None and len(self.sent) >= self.fail_after):
            raise discord.HTTPException(_FakeResponse(), "Invalid Form Body")
        self.sent.append((content, embeds))


class FakeClient:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, channel_id):
        return self.channel


class _FakeResponse:
    status = 400
    reason = "Bad Request"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    # Each test's fresh database reuses election IDs, so clear cached results.
    monkeypatch.setattr(election_module, "_unposted_results", {})
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


def _create_election(end_timestamp=None):
    election = CopelandElection(
        title="Big Election",
        description="",
        candidates=list(CANDIDATES),
        method_params={},
        channel_id=1,
        end_timestamp=end_timestamp,
    )
    return db.save_election(election)


def test_long_results_are_split_across_messages():
    election_id = _create_election()
    channel = FakeChannel()
    asyncio.run(
        end_election_and_update_message(
            load_election_from_db(election_id), channel, include_announcement=True
        )
    )

    assert len(channel.sent) >= 1
    assert channel.sent[0][0] is not None  # Announcement on the first message
    for _, embeds in channel.sent:
        assert len(embeds) <= EMBEDS_PER_MESSAGE
        assert sum(len(e) for e in embeds) <= EMBED_TOTAL_LIMIT
        for embed in embeds:
            for field in embed.fields:
                assert len(field.value) <= 1024
    assert load_election_from_db(election_id) is None


def test_failed_post_keeps_election_open():
    election_id = _create_election()
    with pytest.raises(discord.HTTPException):
        asyncio.run(
            end_election_and_update_message(
                load_election_from_db(election_id), FakeChannel(fail=True)
            )
        )

    election = load_election_from_db(election_id)
    assert election is not None
    assert election.open


def test_init_db_removes_stuck_closed_elections():
    election_id = _create_election()
    election = load_election_from_db(election_id)
    election.open = False
    db.save_election(election)

    db.init_db()
    assert load_election_from_db(election_id) is None


def test_retry_after_partial_post_resumes():
    election_id = _create_election()
    channel = FakeChannel(fail_after=1)
    with pytest.raises(discord.HTTPException):
        asyncio.run(
            end_election_and_update_message(load_election_from_db(election_id), channel)
        )
    assert len(channel.sent) == 1
    first = channel.sent[0]

    channel.fail_after = None
    asyncio.run(
        end_election_and_update_message(load_election_from_db(election_id), channel)
    )
    assert channel.sent[0] is first
    assert len(channel.sent) > 1
    assert first not in channel.sent[1:]
    assert load_election_from_db(election_id) is None


def test_voting_closes_at_end_time():
    election_id = _create_election()
    assert load_election_from_db(election_id).accepting_votes()

    db.delete_election(election_id)
    election_id = _create_election(end_timestamp=int(time.time()) - 1)
    assert not load_election_from_db(election_id).accepting_votes()


def test_checker_backs_off_after_failure(monkeypatch):
    monkeypatch.setattr(election_checker, "_failures", {})
    election_id = _create_election(end_timestamp=int(time.time()) - 1)
    channel = FakeChannel(fail=True)
    election_checker.set_client(FakeClient(channel))

    asyncio.run(election_checker.check_expired_elections())
    assert channel.attempts == 1

    # An immediate second check doesn't retry yet.
    asyncio.run(election_checker.check_expired_elections())
    assert channel.attempts == 1
    assert load_election_from_db(election_id) is not None
