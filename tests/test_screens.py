"""Tests of the bot's screens: that they fit Discord's limits for Components V2
messages even at their largest, and that their forms update the setup."""

import asyncio

import discord
import pytest

import db
import setup
from electable import ConfirmModal, ElectableView
from election import DetailsButton, text_views
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

            view, result_id = election.get_results("Election **x** has ended!")
            assert_fits(view)
            for details in text_views(db.load_results(result_id)):
                assert_fits(details)
            assert_fits(election.get_info()["view"])
            db.delete_election(election.election_id)

        view = ElectableView(1, 2)
        for cls in [ApprovalElection, STARElection]:
            _election(cls)
        assert_fits(view.get_content()["view"])
        view.selected_election_id = db.load_elections_in_channel(1)[0]["election_id"]
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


def test_duplicate_title_is_caught_during_setup():
    async def main():
        _election(ApprovalElection)
        s = _full_setup()
        s.channel_id = 1
        assert s.invalid_reason() is None
        s.title = db.load_elections_in_channel(1)[0]["title"]
        assert "already ongoing" in s.invalid_reason()
        start = next(
            item
            for item in s.get_setup_message()["view"].walk_children()
            if isinstance(item, discord.ui.Button) and item.label == "Start Election"
        )
        assert start.disabled

    asyncio.run(main())


def test_electable_view_continues_after_timing_out():
    async def main():
        view = ElectableView(1, 2)
        assert view.get_content()["view"] is view
        view.stop()  # As when it times out during a long setup
        fresh = view.get_content()["view"]
        assert fresh is not view and not fresh.is_finished()

    asyncio.run(main())


def _personal_and_shared():
    mine = _election(ApprovalElection)
    theirs = _election(STARElection)
    theirs.creator_id = 3
    db.save_election(theirs)
    shared = _election(STVElection, {NUMBER_OF_WINNERS: "1"})
    shared.creator_id = 3
    shared.shared = True
    db.save_election(shared)
    return mine, theirs, shared


def _listed(view: ElectableView) -> set[int]:
    view.get_content()
    return {
        int(option.value)
        for item in view.walk_children()
        if isinstance(item, discord.ui.Select)
        for option in item.options
    }


def test_who_can_manage_elections():
    async def main():
        mine, theirs, shared = _personal_and_shared()
        # Personal elections are only listed for their creators, shared ones
        # for everyone, and everything for people who manage the server.
        assert _listed(ElectableView(1, 2)) == {mine.election_id, shared.election_id}
        assert _listed(ElectableView(1, 3)) == {theirs.election_id, shared.election_id}
        assert _listed(ElectableView(1, 4, manages_all=True)) == {
            mine.election_id,
            theirs.election_id,
            shared.election_id,
        }

        # Someone else's personal election can't be opened.
        view = ElectableView(1, 2)
        view.selected_election_id = theirs.election_id
        view.get_content()
        assert view.selected_election_id is None

    asyncio.run(main())


def test_post_shows_who_runs_personal_elections():
    async def main():
        mine, theirs, shared = _personal_and_shared()
        post = mine.get_public_view()
        assert "-# Run by <@2>" in texts(post["view"])
        assert post["allowed_mentions"].users is False
        assert not any("Run by" in t for t in texts(shared.get_public_view()["view"]))

    asyncio.run(main())


def test_choosing_who_can_manage():
    async def main():
        s = _full_setup()
        select = next(
            item
            for item in s.get_setup_message()["view"].walk_children()
            if isinstance(item, discord.ui.Select)
            and any(o.value == "shared" for o in item.options)
        )
        assert [o.value for o in select.options if o.default] == ["personal"]
        select._values = ["shared"]
        await select.callback(FakeInteraction())
        assert s.shared

    asyncio.run(main())


def test_deleting_the_post_or_channel_deletes_the_election():
    async def main():
        mine, theirs, shared = _personal_and_shared()
        for i, election in enumerate([mine, theirs, shared]):
            election.message_id = 100 + i
            db.save_election(election)
        assert db.delete_elections_by_message([100, 999]) == 1
        assert db.load_election(mine.election_id) is None
        assert db.delete_elections_in_channel(1) == 2
        assert db.load_elections_in_channel(1) == []

    asyncio.run(main())


def test_ballot_for_a_deleted_election():
    async def main():
        election = _election(ApprovalElection)
        ballot = election.blank_ballot()
        ballot.render_interim(1)
        db.delete_election(election.election_id)
        interaction = FakeInteraction()
        await ballot.modify(lambda: None, interaction, 1)
        assert texts(interaction.response.edited["view"]) == [
            "This election no longer exists."
        ]

    asyncio.run(main())


def test_vote_count_update_finds_post_gone(monkeypatch):
    import election as election_module

    class Gone:
        status = 404
        reason = "Not Found"

    class Channel:
        async def fetch_message(self, message_id):
            raise discord.NotFound(Gone(), {"code": 10008, "message": "Unknown Message"})

    class Client:
        def get_channel(self, channel_id):
            return Channel()

    monkeypatch.setattr(election_module, "_client", Client())

    async def main():
        election = _election(ApprovalElection)
        election.message_id = 100
        await election.update_vote_count()
        assert db.load_election(election.election_id) is None

    asyncio.run(main())



class FakeFollowupViews:
    def __init__(self):
        self.sent = []

    async def send(self, view=None, ephemeral=False):
        assert ephemeral
        self.sent.append(view)


class FakeSendResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content=None, view=None, ephemeral=False):
        assert ephemeral
        self.sent.append(view or content)


class FakeClickInteraction:
    locale = discord.Locale("en-US")

    def __init__(self):
        self.response = FakeSendResponse()
        self.followup = FakeFollowupViews()


def test_details_button_shows_results_privately():
    async def main():
        result_id = db.save_results(["## Results", "x" * 9000])
        interaction = FakeClickInteraction()
        await DetailsButton(result_id).callback(interaction)
        views = interaction.response.sent + interaction.followup.sent
        assert len(views) > 1
        assert "## Results" in texts(views[0])

        interaction = FakeClickInteraction()
        await DetailsButton(999).callback(interaction)
        assert interaction.response.sent == ["These results are no longer available."]

    asyncio.run(main())


def test_post_shows_method_on_request():
    async def main():
        election = _election(STVElection, {NUMBER_OF_WINNERS: "1"})
        post = election.get_public_view()["view"]
        assert not any("Instant Runoff" in t for t in texts(post))
        assert labels(post)[-2:] == ["Vote", "Details"]
        info = election.get_info()["view"]
        assert "**Method**:\nInstant Runoff" in texts(info)

        ended = election.get_public_view(ended_at=2_000_000_000, result_id=5)["view"]
        assert labels(ended) == ["Details"]

    asyncio.run(main())


def test_old_results_are_deleted(monkeypatch):
    old = db.save_results(["old"])
    new = db.save_results(["new"])
    with db.transaction() as conn:
        conn.execute(
            "UPDATE results SET created = created - ? WHERE result_id = ?",
            (db.RESULTS_RETENTION_SECONDS, old),
        )
    assert db.delete_old_results() == 1
    assert db.load_results(old) is None
    assert db.load_results(new) == ["new"]


def test_partial_results():
    async def main():
        election = _election(ApprovalElection)
        for user, votes in enumerate([{CANDIDATES[0]}, {CANDIDATES[0], CANDIDATES[1]}]):
            ballot = election.blank_ballot()
            ballot.votes = votes
            db.save_ballot(ballot, election.election_id, user, is_submitted=False)
            db.submit_ballot(election.election_id, user, ballot)

        views = election.get_partial_results()
        for view in views:
            assert_fits(view)
        shown = [t for view in views for t in texts(view)]
        # Clearly unofficial at the start and the end
        assert shown[0].startswith("## :warning: Unofficial partial results")
        assert "Unofficial partial results" in shown[-1]
        assert any(t.startswith("**Currently leading**") for t in shown)
        assert "-# 2 votes cast" in shown

        # Nothing is saved, and the election goes on.
        assert db.load_results(1) is None
        assert db.load_election(election.election_id) is not None

        view = ElectableView(1, 2)
        view.selected_election_id = election.election_id
        assert "Partial Results" in labels(view.get_content()["view"])

    asyncio.run(main())
