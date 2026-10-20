import pytest

from elections.copeland import CopelandElection
from elections.kemeny_young import KemenyYoungElection
from elections.ranked_pairs import RankedPairsElection
from elections.rivestshen import RivestShenGTElection
from elections.stv import STVElection
from elections.tideman_alt import TidemanAlternativeElection
from tests.testutil import PrefillBallot
from layout import pack_text
from text_utils import LAYOUT_TEXT_LIMIT, split_text

CONDORCET_METHODS = [
    CopelandElection,
    KemenyYoungElection,
    RankedPairsElection,
    RivestShenGTElection,
    TidemanAlternativeElection,
]


def ranked(*rankings):
    return [PrefillBallot(ranking=list(r)) for r in rankings]


@pytest.mark.parametrize("method", CONDORCET_METHODS)
def test_condorcet_winner(method):
    # No majority of first choices, but Bob beats everyone head to head.
    election = method("", "", candidates=["Alice", "Bob", "Charlie"], method_params={})
    winners, _ = election.tabulate(
        3 * ranked(["Alice", "Bob", "Charlie"])
        + 2 * ranked(["Bob", "Charlie", "Alice"])
        + 2 * ranked(["Charlie", "Bob", "Alice"])
    )
    assert winners == ["Bob"]


@pytest.mark.parametrize("method", CONDORCET_METHODS)
def test_condorcet_winner_with_truncated_ballots(method):
    # Alice is the Condorcet winner only if ranked candidates are counted as
    # preferred over unranked ones.
    election = method("", "", candidates=["Alice", "Bob", "Charlie"], method_params={})
    winners, _ = election.tabulate(
        4 * ranked(["Alice"])
        + 2 * ranked(["Bob", "Alice"])
        + 2 * ranked(["Charlie", "Alice"])
        + ranked(["Bob", "Charlie"])
    )
    assert winners == ["Alice"]


def test_kemeny_young_rejects_too_many_candidates():
    candidates = [f"C{i}" for i in range(7)]
    assert KemenyYoungElection.validate_method_params({}, candidates)
    assert KemenyYoungElection.validate_method_params({}, candidates[:6]) is None


def test_stv_formats_large_vote_counts():
    election = STVElection(
        "",
        "",
        candidates=["Alice", "Bob", "Charlie"],
        method_params={"Number of Winners": "1"},
    )
    winners, details = election.tabulate(
        123 * ranked(["Alice"]) + 100 * ranked(["Bob"]) + 50 * ranked(["Charlie", "Bob"])
    )
    assert winners == ["Bob"]
    assert "e+" not in details
    assert "Active ballots: 273" in details


def test_split_text():
    text = "\n".join(f"line {i}" for i in range(1000))
    chunks = split_text(text, 100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text

    assert split_text("x" * 250, 100) == ["x" * 100, "x" * 100, "x" * 50]
    assert split_text("", 100) == [""]


def test_long_details_fit_in_messages():
    candidates = [f"Candidate number {i} with a long name" for i in range(20)]
    election = CopelandElection("", "", candidates=candidates, method_params={})
    _, details = election.tabulate(ranked(candidates, reversed(candidates)))
    assert len(details) > LAYOUT_TEXT_LIMIT

    messages = pack_text(["## Heading", details], first_message_used=100)
    assert len(messages) > 1
    assert sum(map(len, messages[0])) + 100 <= LAYOUT_TEXT_LIMIT
    for message in messages:
        assert sum(map(len, message)) <= LAYOUT_TEXT_LIMIT
    # Nothing is lost when splitting.
    pieces = [t for m in messages for t in m]
    assert pieces[0] == "## Heading"
    assert "\n".join(pieces[1:]) == details


