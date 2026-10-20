"""Tests of the bot's screens: that they fit Discord's limits for Components V2
messages even at their largest, and that their forms update the setup."""

import asyncio

import discord
import pytest

import db
import setup
from electable import ConfirmModal, ElectableView
from elections.approval import ApprovalElection
from elections.star import STARElection
from elections.stv import NUMBER_OF_WINNERS, STVElection
from tests.testutil import assert_fits, labels, texts

LONG = "x" * setup.CANDIDATE_MAX_LENGTH
CANDIDATES = [f"{i:02} {LONG}"[: setup.CANDIDATE_MAX_LENGTH] for i in range(20)]
DESCRIPTION = "d" * setup.DESCRIPTION_MAX_LENGTH
TITLE = "t" * setup.TITLE_MAX_LENGTH


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


class FakeResponse:
    def __init__(self):
        self.edited = None

    async def edit_message(self, **kwargs):
        self.edited = kwargs


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append(content)


class FakeInteraction:
    def __init__(self):
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.channel_id = 1
        self.user = discord.Object(id=2)


def _election(cls, params=None):
    election = cls(
        # Titles must differ within a channel.
        title=f"{cls.__name__} {TITLE}"[: setup.TITLE_MAX_LENGTH],
        description=DESCRIPTION,
        candidates=list(CANDIDATES),
        method_params=params or {},
        channel_id=1,
        creator_id=2,
        end_timestamp=2_000_000_000,
    )
    db.save_election(election)
    return election


def _full_setup():
    s = setup.ElectionSetup()
    s.title = TITLE
    s.description = DESCRIPTION
    s.candidates = list(CANDIDATES)
    s.set_method(STVElection.method_name())
    s.end_timestamp = 2_000_000_000
    return s


def test_largest_screens_fit():
    async def main():
        assert_fits(_full_setup().get_setup_message()["view"])

        for cls in [ApprovalElection, STARElection, STVElection]:
            election = _election(cls, cls.default_method_params())
            assert_fits(election.get_public_view()["view"])
            assert_fits(election.get_public_view(ended_at=2_000_000_000)["view"])

            ballot = election.blank_ballot()
            for page in range(ballot.total_pages()):
                ballot.page = page
                assert_fits(ballot.render_interim(1)["view"])
            assert_fits(ballot.render_submitted()["view"])

            for view in election.get_results("Election **x** has ended!"):
                assert_fits(view)
            db.delete_election(election.election_id)

        view = ElectableView(FakeInteraction())
        for cls in [ApprovalElection, STARElection]:
            _election(cls)
        assert_fits(view.get_content()["view"])
        view.selected_election_id = db.load_elections_by_creator(1, 2)[0]["election_id"]
        assert_fits(view.get_content()["view"])

    asyncio.run(main())


def test_score_ballot_pages():
    async def main():
        ballot = _election(STARElection).blank_ballot()
        assert ballot.total_pages() == 2

    asyncio.run(main())


def test_ranked_ballot_can_remove_a_candidate():
    async def main():
        ballot = _election(STVElection, {NUMBER_OF_WINNERS: "1"}).blank_ballot()
        assert "Remove a candidate from your ranking" not in labels(
            ballot.render_interim(1)["view"]
        )
        ballot.ranking = CANDIDATES[:2]
        assert "Remove a candidate from your ranking" in labels(
            ballot.render_interim(1)["view"]
        )

    asyncio.run(main())


def test_public_view_shows_ended_election():
    async def main():
        election = _election(ApprovalElection)
        open_view = election.get_public_view()["view"]
        ended_view = election.get_public_view(ended_at=2_000_000_000)["view"]
        assert "Vote" in labels(open_view)
        assert "Vote" not in labels(ended_view)
        assert any(t.startswith("**Ended**") for t in texts(ended_view))
        assert any("Election ended" in t for t in texts(ended_view))

    asyncio.run(main())


def test_adding_candidates():
    async def main():
        s = setup.ElectionSetup()
        s.candidates = ["Alice"]
        modal = s.candidates_modal()
        names = ["Alice", "Bob", "", "  Carol  ", "y" * 81] + [f"C{i}" for i in range(30)]
        modal.names._value = "\n".join(names)
        interaction = FakeInteraction()
        await modal.on_submit(interaction)

        assert s.candidates[:3] == ["Alice", "Bob", "Carol"]
        assert len(s.candidates) == setup.MAX_CANDIDATES
        problems = interaction.followup.sent[0]
        assert "**Alice** is already a candidate." in problems
        assert "too long" in problems
        assert "at most 20 candidates" in problems
        assert interaction.response.edited is not None

    asyncio.run(main())


def test_choosing_method_parameters_from_a_list():
    async def main():
        s = _full_setup()
        modal = s.params_modal()
        (label,) = modal.children
        select = label.component
        assert [o.value for o in select.options] == [str(n) for n in range(1, 21)]
        assert [o.value for o in select.options if o.default] == ["1"]
        select._values = ["3"]
        await modal.on_submit(FakeInteraction())
        assert s.method_params == {NUMBER_OF_WINNERS: "3"}

    asyncio.run(main())


def test_languages_fit_one_menu():
    # Discord allows 25 options in a select, and English is one of them.
    assert len(setup.available_locales()) + 1 <= 25


def language_menu(s):
    """The language dropdown on the setup screen."""
    return next(
        item
        for item in s.get_setup_message()["view"].walk_children()
        if isinstance(item, discord.ui.Select)
        and any(o.label == "English" for o in item.options)
    )


def test_choosing_a_language(monkeypatch):
    monkeypatch.setattr(setup, "available_locales", lambda: ["cs", "ja", "pl"])

    async def main():
        s = setup.ElectionSetup()
        s.locale = "pl"
        select = language_menu(s)
        assert [o.label for o in select.options] == ["English", "Polski", "Čeština", "日本語"]
        assert [o.value for o in select.options if o.default] == ["pl"]

        select._values = ["ja"]
        await select.callback(FakeInteraction())
        assert s.locale == "ja"
        assert [o.value for o in language_menu(s).options if o.default] == ["ja"]

        select = language_menu(s)
        select._values = ["en"]
        await select.callback(FakeInteraction())
        assert s.locale is None

    asyncio.run(main())


def test_method_shown_once():
    async def main():
        s = _full_setup()
        view = s.get_setup_message()["view"]
        assert "**Method**" in texts(view)
        assert not any("Instant Runoff" in t for t in texts(view))
        method_menu = next(
            item
            for item in view.walk_children()
            if isinstance(item, discord.ui.Select) and item.placeholder == "Select Method"
        )
        assert [o.value for o in method_menu.options if o.default] == [
            STVElection.method_name()
        ]

    asyncio.run(main())


def test_confirmation_requires_the_box():
    async def main():
        confirmed = []

        async def on_confirm(interaction):
            confirmed.append(True)

        modal = ConfirmModal("Title", "Question?", "Yes", on_confirm)
        assert modal.confirm.required
        modal.confirm._values = []
        await modal.on_submit(FakeInteraction())
        assert not confirmed
        modal.confirm._values = ["yes"]
        await modal.on_submit(FakeInteraction())
        assert confirmed

    asyncio.run(main())
