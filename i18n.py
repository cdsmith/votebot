"""Translation of user-facing text.

Text is translated into the language of the current context, which is set with
use_locale().  Mark user-facing strings with _(), or ngettext() when the
wording depends on a count.  Use str.format placeholders rather than f-strings,
so that translators see the whole sentence:

    _("Results for {title}").format(title=election.title)

Because _ is the translation function, don't use it as a throwaway variable
name.

To regenerate the catalog template after changing strings:

    pybabel extract -c Translators: --no-location --project=votebot \\
        -o locales/votebot.pot *.py ballots elections
"""

import contextvars
import functools
import gettext
import os
from contextlib import contextmanager

import discord

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
DOMAIN = "votebot"

# Each language's name in that language, by Discord locale code.  Translations
# may also be for a whole language (e.g. "es" for both "es-ES" and "es-419").
LANGUAGE_NAMES = {
    "bg": "български",
    "cs": "Čeština",
    "de": "Deutsch",
    "el": "Ελληνικά",
    "es": "Español",
    "es-ES": "Español",
    "es-419": "Español, LATAM",
    "fr": "Français",
    "hi": "हिन्दी",
    "hu": "Magyar",
    "id": "Bahasa Indonesia",
    "it": "Italiano",
    "ja": "日本語",
    "ko": "한국어",
    "nl": "Nederlands",
    "pl": "Polski",
    "pt": "Português",
    "pt-BR": "Português do Brasil",
    "ro": "Română",
    "ru": "Русский",
    "sv-SE": "Svenska",
    "th": "ไทย",
    "tr": "Türkçe",
    "uk": "Українська",
    "vi": "Tiếng Việt",
    "zh-CN": "中文",
    "zh-TW": "繁體中文",
}

# Discord locale code (e.g. "pl" or "pt-BR"), or None for English
_current_locale: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "locale", default=None
)


@functools.cache
def _translations(locale: str | None) -> gettext.NullTranslations:
    if locale is None:
        return gettext.NullTranslations()
    # Discord uses codes like "pt-BR", while gettext directories use "pt_BR".
    return gettext.translation(
        DOMAIN, LOCALE_DIR, languages=[locale.replace("-", "_")], fallback=True
    )


@functools.cache
def available_locales() -> list[str]:
    """Locales with translations, not counting English."""
    if not os.path.isdir(LOCALE_DIR):
        return []
    return sorted(
        name.replace("_", "-")
        for name in os.listdir(LOCALE_DIR)
        if os.path.isfile(os.path.join(LOCALE_DIR, name, "LC_MESSAGES", DOMAIN + ".mo"))
    )


def supported_locale(locale: str | None) -> str | None:
    """The available locale that best matches a Discord locale, or None for
    English.  For example, "es-419" matches translations for "es"."""
    if locale is None:
        return None
    for candidate in (locale, locale.split("-")[0]):
        if candidate in available_locales():
            return candidate
    return None


def language_name(locale: str | None) -> str:
    """The name of a locale's language, in that language."""
    if locale is None:
        return "English"
    return LANGUAGE_NAMES.get(locale, locale)


def _(message: str) -> str:
    """Translate a message into the current locale."""
    return _translations(_current_locale.get()).gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate a message whose wording depends on the count n."""
    return _translations(_current_locale.get()).ngettext(singular, plural, n)


def N_(message: str) -> str:
    """Mark a message for translation without translating it yet.

    For strings that also serve as identifiers, such as method names, which
    are stored in English and translated with _() where they are displayed."""
    return message


@contextmanager
def use_locale(locale: str | None):
    """Translate text into the given locale within this block."""
    token = _current_locale.set(locale)
    try:
        yield
    finally:
        _current_locale.reset(token)


def _set_locale_for(interaction: discord.Interaction):
    # Views and modals run interaction_check and then the callback in their
    # own task, so this applies to the rest of the interaction only.
    _current_locale.set(interaction.locale.value)


class CommandTranslator(discord.app_commands.Translator):
    """Translates slash command descriptions for each user's Discord language."""

    async def translate(
        self,
        string: discord.app_commands.locale_str,
        locale: discord.Locale,
        context: discord.app_commands.TranslationContext,
    ) -> str | None:
        with use_locale(locale.value):
            translated = _(string.message)
        # None tells Discord there's no translation, so it uses the original.
        return translated if translated != string.message else None


class LocalizedView(discord.ui.LayoutView):
    """A view whose callbacks show text in the language of the user who
    interacted with it.  All of the bot's messages use these Components V2
    layouts."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        _set_locale_for(interaction)
        return await super().interaction_check(interaction)


class LocalizedModal(discord.ui.Modal):
    """A modal whose submission shows text in the language of the user who
    submitted it."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        _set_locale_for(interaction)
        return await super().interaction_check(interaction)
