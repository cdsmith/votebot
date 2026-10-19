import asyncio

import discord
import pytest

import db
from election import end_election_and_update_message, load_election_from_db
from elections.copeland import CopelandElection
from text_utils import EMBED_TOTAL_LIMIT, EMBEDS_PER_MESSAGE

CANDIDATES = [f"Candidate number {i} with a long name" for i in range(20)]


class FakeChannel:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    async def send(self, content=None, embeds=()):
        if self.fail:
            raise discord.HTTPException(_FakeResponse(), "Invalid Form Body")
        self.sent.append((content, embeds))


class _FakeResponse:
    status = 400
    reason = "Bad Request"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


def _create_election():
    election = CopelandElection(
        title="Big Election",
        description="",
        candidates=list(CANDIDATES),
        method_params={},
        channel_id=1,
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
