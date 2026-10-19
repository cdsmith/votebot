import ast
import gettext
import pathlib
import subprocess

import pytest

import i18n
from i18n import _, ngettext, use_locale

ROOT = pathlib.Path(__file__).parent.parent
# The project's own modules: files git tracks or would track, so that installed
# packages in a local virtualenv are never included.
SOURCES = [
    ROOT / name
    for name in subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not name.startswith("tests/")
]


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_translated_strings_are_constant(path):
    """Text built before translation (e.g. with an f-string) can't be found in
    the catalog.  Only fixed strings, or identifiers like method names, may be
    passed to _()."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in (
            "_",
            "ngettext",
            "N_",
        ):
            for arg in node.args[:2] if node.func.id == "ngettext" else node.args[:1]:
                assert not isinstance(arg, (ast.JoinedStr, ast.BinOp)), (
                    f"{path.name}:{node.lineno}: build text after translating, "
                    "with .format()"
                )
                if isinstance(arg, ast.Call):
                    assert getattr(arg.func, "attr", None) != "format", (
                        f"{path.name}:{node.lineno}: call .format() after _()"
                    )


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_underscore_is_not_shadowed(path):
    """Assigning to _ in a function hides the translation function there."""
    tree = ast.parse(path.read_text())
    # Comprehension variables have their own scope, so they're harmless.
    comprehension_targets = {
        id(name)
        for node in ast.walk(tree)
        if isinstance(node, ast.comprehension)
        for name in ast.walk(node.target)
    }
    for node in ast.walk(tree):
        shadows = (isinstance(node, ast.arg) and node.arg == "_") or (
            isinstance(node, ast.Name)
            and node.id == "_"
            and isinstance(node.ctx, ast.Store)
            and id(node) not in comprehension_targets
        )
        assert not shadows, f"{path.name}:{node.lineno}: _ is the translation function"


def test_english_by_default():
    assert _("Vote") == "Vote"
    assert ngettext("{n} vote", "{n} votes", 1) == "{n} vote"
    assert ngettext("{n} vote", "{n} votes", 2) == "{n} votes"
    with use_locale("en-GB"):  # No catalog, so the English text
        assert _("Vote") == "Vote"


class FakeTranslations(gettext.NullTranslations):
    def gettext(self, message):
        return {"Vote": "Głosuj"}.get(message, message)


def test_use_locale(monkeypatch):
    monkeypatch.setattr(
        i18n,
        "_translations",
        lambda locale: FakeTranslations() if locale == "pl" else gettext.NullTranslations(),
    )
    with use_locale("pl"):
        assert _("Vote") == "Głosuj"
        with use_locale(None):
            assert _("Vote") == "Vote"
        assert _("Vote") == "Głosuj"
    assert _("Vote") == "Vote"
