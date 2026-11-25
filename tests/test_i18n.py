"""Every text marked for translation has a Czech one, with the same placeholders."""

import ast
import string
from pathlib import Path

from portfolio.core import i18n
from portfolio.core.i18n import N_, tr
from portfolio.core.i18n_cs import CS
from portfolio.ui.pages import glossary
from portfolio.ui.pages.glossary_cs import SECTIONS_CS

SRC = Path(__file__).parent.parent / "src" / "portfolio"


def marked_texts() -> dict[str, str]:
    """Every literal text passed to tr() or N_(), with where it is."""
    found = {}
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("tr", "N_")
                and node.args
            ):
                text = node.args[0]
                where = f"{path.relative_to(SRC)}:{node.lineno}"
                # A text built at run time could not be looked up: tr() takes a literal,
                # or a variable holding a text marked with N_() where it was defined.
                assert not isinstance(text, ast.JoinedStr), f"f-string passed at {where}"
                if node.func.id == "N_":
                    assert isinstance(text, ast.Constant), f"N_() needs a literal at {where}"
                if isinstance(text, ast.Constant) and isinstance(text.value, str):
                    found.setdefault(text.value, where)
    return found


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def test_every_marked_text_has_a_czech_translation():
    missing = {text: where for text, where in marked_texts().items() if text not in CS}
    assert not missing


def test_the_catalogue_has_no_left_over_texts():
    assert not set(CS) - set(marked_texts())


def test_translations_keep_the_placeholders():
    differing = {e: c for e, c in CS.items() if placeholders(e) != placeholders(c)}
    assert not differing


def test_tr_translates_fills_in_and_falls_back_to_english():
    try:
        assert tr("Overview") == "Overview"
        i18n.set_language("cs")
        assert tr("Overview") == "Přehled"
        assert tr("Type: {name}", name="etf") == "Typ: etf"
        assert tr("a text nobody translated") == "a text nobody translated"
        i18n.set_language("xx")  # unknown: English
        assert i18n.language() == "en"
    finally:
        i18n.set_language("en")
    assert N_("Overview") == "Overview"


def test_the_czech_glossary_has_the_same_terms_as_the_english_one():
    english = [len(terms) for terms in glossary.SECTIONS.values()]
    assert [len(terms) for terms in SECTIONS_CS.values()] == english
    for terms in SECTIONS_CS.values():
        for term in terms:
            assert term.name and term.meaning
