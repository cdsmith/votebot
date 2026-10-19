"""
Test suite for database functionality.
Tests creating elections, casting votes, and retrieving results.

Run with pytest from the project root (PYTHONPATH=. pytest), or directly
with: python3 -m tests.test_db
"""

import json
import os
import random

import pytest

import db
from election import ballot_from_dict, load_election_from_db
from elections.approval import ApprovalElection
from elections.plurality import PluralityElection
from elections.star import STARElection
from elections.stv import STVElection
from ballots.simple import SimpleBallot


CANDIDATES = ["Alice", "Bob", "Charlie"]
CHANNEL_ID = 12345
TITLE = "Test Election"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Point db at a fresh temporary database for each test."""
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


@pytest.fixture
def election_id():
    """Create and save a test election, returning its ID."""
    election = PluralityElection(
        title=TITLE,
        description="This is a test election",
        candidates=list(CANDIDATES),
        method_params={},
        election_id=None,
        channel_id=CHANNEL_ID,
        creator_id=123456789,
        end_timestamp=None,
    )
    return db.save_election(election)


def _cast_vote(election_id, user_id, choice):
    candidates = list(CANDIDATES)
    random.shuffle(candidates)
    ballot = SimpleBallot(election_id, candidates, multiple_votes=False)
    ballot.votes = {choice}
    ballot.session_id = user_id
    db.save_ballot(ballot, election_id, user_id, is_submitted=False)
    db.submit_ballot(election_id, user_id, ballot)


def test_election_persistence(election_id):
    """Test that elections can be saved and loaded from the database."""
    loaded_election = load_election_from_db(election_id)

    assert loaded_election is not None, "Failed to load election"
    assert loaded_election.title == TITLE
    assert loaded_election.channel_id == CHANNEL_ID
    assert len(loaded_election.candidates) == 3


def test_ballot_persistence(election_id):
    """Test that ballots can be saved and loaded."""
    candidates = list(CANDIDATES)
    random.shuffle(candidates)
    ballot = SimpleBallot(election_id, candidates, multiple_votes=False)
    ballot.votes = {"Alice"}
    ballot.session_id = 12345678

    # Save ballot
    db.save_ballot(ballot, election_id, user_id=999, is_submitted=False)

    # Load ballot
    ballot_data = db.load_user_ballot(election_id, 999, is_submitted=False)
    assert ballot_data is not None, "Failed to load ballot"
    assert ballot_data["session_id"] == 12345678

    # Submit ballot
    db.submit_ballot(election_id, 999, ballot)

    # Verify it moved to submitted
    interim = db.load_user_ballot(election_id, 999, is_submitted=False)
    submitted = db.load_user_ballot(election_id, 999, is_submitted=True)

    assert interim is None, "Interim ballot should be deleted"
    assert submitted is not None, "Submitted ballot should exist"


def test_vote_count(election_id):
    """Test vote counting, including that re-submitting replaces a vote."""
    for user_id in [1000, 1001, 1002]:
        _cast_vote(election_id, user_id, random.choice(CANDIDATES))
    _cast_vote(election_id, 1000, "Bob")

    assert db.get_vote_count(election_id) == 3


def test_election_results(election_id):
    """Test computing election results."""
    for user_id, choice in [(1000, "Alice"), (1001, "Alice"), (1002, "Bob")]:
        _cast_vote(election_id, user_id, choice)

    election = load_election_from_db(election_id)
    ballot_dicts = db.load_all_ballots(election_id, is_submitted=True)
    assert len(ballot_dicts) == 3

    ballots = [ballot_from_dict(bd, election_id) for bd in ballot_dicts]

    winners, details = election.tabulate(ballots)
    assert winners == ["Alice"]
    assert details


def test_natural_key_lookup(election_id):
    """Test loading election by channel_id and title."""
    election_data = db.load_election_by_natural_key(CHANNEL_ID, TITLE)
    assert election_data is not None, "Failed to load by natural key"
    assert election_data["title"] == TITLE
    assert election_data["election_id"] == election_id


# Ballots exactly as stored by earlier versions, which must keep loading.
STORED_BALLOTS = [
    (
        ApprovalElection,
        {},
        "ballots.simple.SimpleBallot",
        {
            "votes": ["Alice", "Charlie"],
            "multiple_votes": True,
            "page": 0,
            "visited_pages": [0],
            "candidates": ["Charlie", "Alice", "Bob"],
            "session_id": 1,
        },
        ["Alice", "Charlie"],
    ),
    (
        STVElection,
        {"Number of Winners": "1"},
        "ballots.ranked.RankedBallot",
        {
            "ranking": ["Bob", "Alice"],
            "page": 0,
            "visited_pages": [0],
            "candidates": ["Alice", "Charlie", "Bob"],
            "session_id": 1,
        },
        ["Bob"],
    ),
    (
        STARElection,
        {},
        "ballots.score.ScoreBallot",
        {
            "ratings": {"Alice": 2, "Bob": 5, "Charlie": 0},
            "page": 0,
            "visited_pages": [0],
            "candidates": ["Bob", "Alice", "Charlie"],
            "session_id": 1,
        },
        ["Bob"],
    ),
]


@pytest.mark.parametrize("method, params, ballot_type, data, expected", STORED_BALLOTS)
def test_stored_ballots_load(method, params, ballot_type, data, expected):
    election = method(
        title=TITLE,
        description="",
        candidates=list(CANDIDATES),
        method_params=params,
        channel_id=CHANNEL_ID,
    )
    election_id = db.save_election(election)
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO ballots (election_id, user_id, ballot_type, ballot_data,
                                 is_submitted)
            VALUES (?, ?, ?, ?, 1)
            """,
            (election_id, 1000, ballot_type, json.dumps(data)),
        )

    election = load_election_from_db(election_id)
    ballots = [
        ballot_from_dict(bd, election_id)
        for bd in db.load_all_ballots(election_id, is_submitted=True)
    ]
    winners, _ = election.tabulate(ballots)
    assert sorted(winners) == expected
    assert ballots[0].to_markdown()


def main():
    """Run this module's tests via pytest against a temporary database."""
    return pytest.main([os.path.abspath(__file__), "-v"])


if __name__ == "__main__":
    exit(main())
