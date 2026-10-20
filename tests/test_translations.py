"""Checks that translations can't break the bot.

A translation whose placeholders differ from the English text would make
.format() fail at runtime, e.g. while posting results.
"""

import gettext
import pathlib
import string

import pytest

import i18n

LOCALES = sorted(
    p.parent.parent.name
    for p in pathlib.Path(i18n.LOCALE_DIR).glob(f"*/LC_MESSAGES/{i18n.DOMAIN}.mo")
)

# Text that the bot must parse, so it can't be translated
UNTRANSLATABLE = ["2d", "3h30m", "2025-12-25 14:30"]

# Discord's length limits for fixed text: form titles and field labels allow
# 45 characters, and buttons 80.  Field descriptions, checkbox options and
# select placeholders allow 100.
MODAL_TEXT = [
    "Create Election",
    "Configure Method",
    "Add Candidate",
    "Edit Attributes",
    "Language",
    "Reschedule Election",
    "Confirm End Election",
    "Confirm Delete Election",
    "Election Title",
    "Description",
    "End Time (optional)",
    "Method",
    "Candidate Names",
    "New End Time",
    "End this election now?",
    "Delete this election?",
    "Number of Winners",
]
BUTTON_TEXT = [
    "Vote",
    "Details",
    "Next Page",
    "Prev Page",
    "Submit Vote",
    "Start Over",
    "← Back",
    "Create New Election",
    "Reschedule",
    "End Now",
    "Partial Results",
    "Delete",
    "Edit",
    "Add Candidate",
    "Start Election",
    "Cancel",
]
SHORT_TEXT = [
    "Examples: 2d, 3h30m, 2025-12-25 14:30",
    "One per line",
    "Yes, end it and post the results",
    "Yes, delete it without posting results",
    "Select Method",
    "Select an election to manage",
    "Remove Candidate",
    "Remove a candidate from your ranking",
    "Only me",
    "Anyone who can use /electable here",
    "The election shows you as the person running it.",
    "The election doesn't show who is running it.",
]


def _fields(text: str) -> set[tuple[str, str]]:
    """The placeholders in a format string, with their format specs."""
    return {
        (name, spec)
        for _literal, name, spec, _conversion in string.Formatter().parse(text)
        if name is not None
    }


def _entries(locale: str):
    """(English, translation) pairs from a locale's compiled catalog."""
    with open(
        pathlib.Path(i18n.LOCALE_DIR, locale, "LC_MESSAGES", f"{i18n.DOMAIN}.mo"), "rb"
    ) as f:
        catalog = gettext.GNUTranslations(f)._catalog
    for key, translation in catalog.items():
        if key == "":
            continue  # Header
        if isinstance(key, tuple):  # Plural: (singular, form index)
            yield key[0], translation
        else:
            yield key, translation


def test_there_are_translations():
    assert LOCALES


@pytest.mark.parametrize("locale", LOCALES)
def test_placeholders_match(locale):
    # Plural forms are checked against the singular English text, whose
    # placeholders match the plural's.  Forms must keep the count, since in
    # many languages the "singular" form is also used for counts like 21.
    for english, translation in _entries(locale):
        assert _fields(translation) == _fields(english), (english, translation)


@pytest.mark.parametrize("locale", LOCALES)
def test_untranslatable_text_is_kept(locale):
    for english, translation in _entries(locale):
        for text in UNTRANSLATABLE:
            if text in english:
                assert text in translation, (english, translation)


@pytest.mark.parametrize("locale", LOCALES)
def test_catalog_is_found(locale):
    assert locale.replace("_", "-") in i18n.available_locales()
    translations = i18n._translations(locale.replace("_", "-"))
    assert isinstance(translations, gettext.GNUTranslations)


@pytest.mark.parametrize("locale", LOCALES)
def test_fits_discord_limits(locale):
    translations = dict(_entries(locale))
    for english in MODAL_TEXT:
        assert len(translations.get(english, english)) <= 45, english
    for english in BUTTON_TEXT:
        assert len(translations.get(english, english)) <= 80, english
    for english in SHORT_TEXT:
        assert len(translations.get(english, english)) <= 100, english
