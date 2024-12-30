from elections.tideman_alt import TidemanAlternativeElection
from testutil import PrefillBallot


def test_tideman_alternative_simple_majority():
    # Alice wins immediately with a majority
    election = TidemanAlternativeElection(
        "", "", candidates=["Alice", "Bob", "Charlie"], method_params={}
    )
    winners, _ = election.tabulate(
        [
            PrefillBallot(ranking=["Alice", "Bob", "Charlie"]),
            PrefillBallot(ranking=["Alice"]),
            PrefillBallot(ranking=["Alice", "Charlie"]),
        ]
    )
    assert winners == ["Alice"]


def test_tideman_alternative_condorcet_winner():
    # No immediate majority; but Alice is the Condorcet winner.
    election = TidemanAlternativeElection(
        "", "", candidates=["Alice", "Bob", "Charlie"], method_params={}
    )
    winners, _ = election.tabulate(
        [
            PrefillBallot(ranking=["Alice", "Bob", "Charlie"]),
            PrefillBallot(ranking=["Alice", "Charlie", "Bob"]),
            PrefillBallot(ranking=["Bob", "Alice", "Charlie"]),
            PrefillBallot(ranking=["Bob", "Alice", "Charlie"]),
            PrefillBallot(ranking=["Charlie", "Alice", "Bob"]),
        ]
    )
    assert winners == ["Alice"]


def test_tideman_alternative_condorcet_cycle():
    # Three-way Condorcet cycle, but Charlie has fewest 1st place votes.  Alice > Bob.
    election = TidemanAlternativeElection(
        "", "", candidates=["Alice", "Bob", "Charlie"], method_params={}
    )
    winners, _ = election.tabulate(
        4 * [PrefillBallot(ranking=["Alice", "Bob", "Charlie"])]
        + 3 * [PrefillBallot(ranking=["Bob", "Charlie", "Alice"])]
        + 2 * [PrefillBallot(ranking=["Charlie", "Alice", "Bob"])]
    )
    assert winners == ["Alice"]


def test_tideman_alternative_condorcet_cycle_after_elim():
    # Doug is a Condorcet loser who needs to be eliminated first.
    election = TidemanAlternativeElection(
        "", "", candidates=["Alice", "Bob", "Charlie", "Doug"], method_params={}
    )
    winners, _ = election.tabulate(
        4 * [PrefillBallot(ranking=["Doug", "Alice", "Bob", "Charlie"])]
        + 3 * [PrefillBallot(ranking=["Bob", "Charlie", "Alice", "Doug"])]
        + 2 * [PrefillBallot(ranking=["Charlie", "Alice", "Bob", "Doug"])]
    )
    assert winners == ["Alice"]
