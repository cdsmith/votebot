"""
Test suite for database functionality.
Tests creating elections, casting votes, and retrieving results.

Run from project root with: python3 -m tests.test_db
"""

import os
import random

import db
from election import load_election_from_db
from elections.plurality import PluralityElection
from ballots.simple import SimpleBallot


def test_election_persistence():
    """Test that elections can be saved and loaded from the database."""
    print("Testing election persistence...")

    # Create an election
    election = PluralityElection(
        title="Test Election",
        description="This is a test election",
        candidates=["Alice", "Bob", "Charlie"],
        method_params={},
        election_id=None,
        channel_id=12345,
        creator_id=123456789,
        end_timestamp=None,
    )

    # Save to database
    election_id = db.save_election(election)
    print(f"✓ Created election with ID: {election_id}")

    # Load from database
    from election import load_election_from_db

    loaded_election = load_election_from_db(election_id)

    assert loaded_election is not None, "Failed to load election"
    assert loaded_election.title == "Test Election"
    assert loaded_election.channel_id == 12345
    assert len(loaded_election.candidates) == 3
    print("✓ Election loaded successfully")

    return election_id


def test_ballot_persistence(election_id):
    """Test that ballots can be saved and loaded."""
    print("\nTesting ballot persistence...")

    # Create a ballot
    candidates = ["Alice", "Bob", "Charlie"]
    random.shuffle(candidates)
    ballot = SimpleBallot(election_id, candidates, multiple_votes=False)
    ballot.votes = {"Alice"}
    ballot.session_id = 12345678

    # Save ballot
    db.save_ballot(ballot, election_id, user_id=999, is_submitted=False)
    print(f"✓ Created interim ballot with ID: {ballot.ballot_id}")

    # Load ballot
    ballot_data = db.load_user_ballot(election_id, 999, is_submitted=False)
    assert ballot_data is not None, "Failed to load ballot"
    assert ballot_data["session_id"] == 12345678
    print("✓ Ballot loaded successfully")

    # Submit ballot
    db.submit_ballot(election_id, 999, ballot)
    print("✓ Ballot submitted")

    # Verify it moved to submitted
    interim = db.load_user_ballot(election_id, 999, is_submitted=False)
    submitted = db.load_user_ballot(election_id, 999, is_submitted=True)

    assert interim is None, "Interim ballot should be deleted"
    assert submitted is not None, "Submitted ballot should exist"
    print("✓ Ballot correctly moved to submitted")


def test_vote_count(election_id):
    """Test vote counting."""
    print("\nTesting vote count...")

    # Add more votes
    for user_id in [1000, 1001, 1002]:
        candidates = ["Alice", "Bob", "Charlie"]
        random.shuffle(candidates)
        ballot = SimpleBallot(election_id, candidates, multiple_votes=False)
        ballot.votes = {random.choice(["Alice", "Bob", "Charlie"])}
        ballot.session_id = user_id
        db.save_ballot(ballot, election_id, user_id, is_submitted=False)
        db.submit_ballot(election_id, user_id, ballot)

    vote_count = db.get_vote_count(election_id)
    print(f"✓ Vote count: {vote_count} votes")
    assert vote_count == 4, f"Expected 4 votes, got {vote_count}"  # 999 + 3 new users


def test_election_results(election_id):
    """Test computing election results."""
    print("\nTesting election results...")

    from election import load_election_from_db

    election = load_election_from_db(election_id)

    # Load all ballots
    ballot_dicts = db.load_all_ballots(election_id, is_submitted=True)
    print(f"✓ Loaded {len(ballot_dicts)} ballots")

    # Reconstruct ballots
    from election import ballot_from_dict

    ballots = [ballot_from_dict(bd, election_id) for bd in ballot_dicts]

    # Tabulate
    winners, details = election.tabulate(ballots)
    print(f"✓ Winners: {winners}")
    print(f"✓ Details:\n{details}")


def test_election_closing(election_id):
    """Test closing an election."""
    print("\nTesting election closing...")

    db.mark_election_closed(election_id)
    from election import load_election_from_db

    election = load_election_from_db(election_id)

    assert election.open == False, "Election should be closed"
    print("✓ Election closed successfully")


def test_natural_key_lookup():
    """Test loading election by channel_id and title."""
    print("\nTesting natural key lookup...")

    election_data = db.load_election_by_natural_key(12345, "Test Election")
    assert election_data is not None, "Failed to load by natural key"
    assert election_data["title"] == "Test Election"
    print("✓ Natural key lookup successful")


def main():
    print("=" * 60)
    print("Database Test Suite")
    print("=" * 60)

    # Clean up any existing test data first
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
        print("✓ Cleaned up old test database")

    # Initialize database
    db.init_db()
    print("✓ Database initialized\n")

    try:
        # Run tests
        election_id = test_election_persistence()
        test_ballot_persistence(election_id)
        test_vote_count(election_id)
        test_election_results(election_id)
        test_election_closing(election_id)
        test_natural_key_lookup()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
