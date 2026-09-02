"""
Test suite for database functionality.
Tests creating elections, casting votes, and retrieving results.

Run with pytest from the project root (PYTHONPATH=. pytest), or directly
with: python3 -m tests.test_db
"""

import os
import random

import pytest

import db
from election import ballot_from_dict, load_election_from_db
from elections.plurality import PluralityElection
from ballots.simple import SimpleBallot


CANDIDATES = ["Alice", "Bob", "Charlie"]
CHANNEL_ID = 12345
TITLE = "Test Election"


def _create_election():
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


@pytest.fixture(scope="module", autouse=True)
def fresh_db(tmp_path_factory):
    """Point db at a fresh temporary database for this module's tests."""
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path_factory.mktemp("db") / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


@pytest.fixture(scope="module")
def election_id():
    """A saved election shared by the tests in this module (which build on
    one another in file order)."""
    return _create_election()


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
    """Test vote counting."""
    for user_id in [1000, 1001, 1002]:
        _cast_vote(election_id, user_id, random.choice(CANDIDATES))

    vote_count = db.get_vote_count(election_id)
    assert vote_count == 4, f"Expected 4 votes, got {vote_count}"  # 999 + 3 new users


def test_election_results(election_id):
    """Test computing election results."""
    election = load_election_from_db(election_id)

    ballot_dicts = db.load_all_ballots(election_id, is_submitted=True)
    assert len(ballot_dicts) == 4

    ballots = [ballot_from_dict(bd, election_id) for bd in ballot_dicts]

    winners, details = election.tabulate(ballots)
    assert winners
    assert details


def test_election_closing(election_id):
    """Test closing an election."""
    db.mark_election_closed(election_id)
    election = load_election_from_db(election_id)

    assert election.open is False, "Election should be closed"


def test_natural_key_lookup(election_id):
    """Test loading election by channel_id and title."""
    election_data = db.load_election_by_natural_key(CHANNEL_ID, TITLE)
    assert election_data is not None, "Failed to load by natural key"
    assert election_data["title"] == TITLE
    assert election_data["election_id"] == election_id


def main():
    """Run this module's tests via pytest against a temporary database."""
    return pytest.main([os.path.abspath(__file__), "-v"])


if __name__ == "__main__":
    exit(main())
