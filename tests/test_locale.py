"""Tests that public messages use the election's language, and private screens
use the language of the user interacting with them."""

import asyncio
import gettext
import time

import discord
import pytest

import db
import election as election_module
import i18n
import setup
from election import end_election_and_update_message, load_election_from_db
from elections.plurality import PluralityElection
from i18n import LocalizedView, _, use_locale

POLISH = {
    "Vote": "Głosuj",
    "Candidates": "Kandydaci",
    "Ends": "Koniec",
    "Ended": "Zakończono",
    "Results for {title}": "Wyniki: {title}",
    "Language": "Język",
}


class FakeTranslations(gettext.NullTranslations):
    def gettext(self, message):
        return POLISH.get(message, message)


@pytest.fixture(autouse=True)
def polish(monkeypatch, tmp_path):
    """Pretend Polish is the only translation, and use a fresh database."""
    monkeypatch.setattr(
        i18n,
        "_translations",
        lambda locale: FakeTranslations() if locale == "pl" else gettext.NullTranslations(),
    )
    monkeypatch.setattr(i18n, "available_locales", lambda: ["pl"])
    monkeypatch.setattr(setup, "available_locales", lambda: ["pl"])
    # Results cached by other tests, whose election IDs are reused here
    monkeypatch.setattr(election_module, "_unposted_results", {})
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "votebot_test.db")
    db.init_db()
    yield
    db.DB_PATH = original


def _create_election(locale, end_timestamp=None):
    election = PluralityElection(
        title="Big Election",
        description="",
        candidates=["Alice", "Bob"],
        method_params={},
        channel_id=1,
        end_timestamp=end_timestamp,
        locale=locale,
    )
    db.save_election(election)
    return election


class FakeInteraction:
    def __init__(self, locale):
        self.locale = discord.Locale(locale)


class FakeMessage:
    def __init__(self, embed):
        self.id = 1
        self.embeds = [embed]
        self.edited = None

    async def edit(self, **kwargs):
        self.edited = kwargs


class FakeChannel:
    def __init__(self, message=None):
        self.message = message
        self.sent = []

    async def send(self, content=None, embeds=()):
        self.sent.append((content, embeds))

    async def fetch_message(self, message_id):
        return self.message


def test_locale_is_saved():
    election = _create_election("pl")
    assert load_election_from_db(election.election_id).locale == "pl"


def test_supported_locale():
    assert i18n.supported_locale("pl") == "pl"
    assert i18n.supported_locale("en-US") is None
    assert i18n.supported_locale(None) is None


def test_supported_locale_matches_language(monkeypatch):
    monkeypatch.setattr(i18n, "available_locales", lambda: ["es", "pt-BR"])
    assert i18n.supported_locale("es-419") == "es"
    assert i18n.supported_locale("pt-BR") == "pt-BR"
    assert i18n.supported_locale("pt") is None


def test_public_view_uses_election_language():
    election = _create_election("pl")

    async def main():
        # Even when a user with another language causes the update
        with use_locale("en-US"):
            return election.get_public_view()

    view = asyncio.run(main())
    assert view["embed"].fields[0].name == "Kandydaci"
    assert view["view"].children[0].label == "Głosuj"


def test_results_use_election_language():
    election = _create_election("pl", end_timestamp=int(time.time()) + 3600)

    async def main():
        message = FakeMessage(election.get_public_view()["embed"])
        election.message_id = message.id
        channel = FakeChannel(message)
        # Ended by a user whose screen is in another language
        with use_locale("en-US"):
            await end_election_and_update_message(election, channel)
        return message, channel

    message, channel = asyncio.run(main())

    _, embeds = channel.sent[0]
    assert embeds[0].title == "Wyniki: Big Election"
    # The original message's end time is relabeled in its own language.
    names = [f.name for f in message.edited["embed"].fields]
    assert "Zakończono" in names and "Koniec" not in names


def test_views_use_interacting_users_language():
    async def interact(locale):
        view = LocalizedView()
        await view.interaction_check(FakeInteraction(locale))
        return _("Vote")

    async def main():
        # Each interaction runs in its own task, as discord.py does.
        results = await asyncio.gather(
            asyncio.create_task(interact("pl")), asyncio.create_task(interact("en-US"))
        )
        # The language doesn't leak out of the interaction.
        return results, _("Vote")

    assert asyncio.run(main()) == (["Głosuj", "Vote"], "Vote")


def test_language_choice_in_setup():
    async def main():
        s = setup.ElectionSetup()
        message = s.get_setup_message()
        assert "Polski" not in message["content"]
        assert "English" in message["content"]
        assert any(
            getattr(item, "label", None) == "Language" for item in message["view"].children
        )

        s.locale = "pl"
        message = s.get_language_message()
        assert "Polski" in message["content"]
        select, back = message["view"].children
        assert [o.label for o in select.options] == ["English", "Polski"]
        assert [o.value for o in select.options] == ["en", "pl"]
        # Discord ignores choosing the default, so the current language isn't one.
        assert not any(o.default for o in select.options)
        assert back.label == "← Back"

        s.locale = "pl"
        assert "Polski" in s.get_setup_message()["content"]

    asyncio.run(main())


def test_language_button_hidden_without_translations(monkeypatch):
    monkeypatch.setattr(setup, "available_locales", lambda: [])

    async def main():
        message = setup.ElectionSetup().get_setup_message()
        assert not any(
            getattr(item, "label", None) == "Language" for item in message["view"].children
        )
        assert "English" not in message["content"]

    asyncio.run(main())
