"""Texts in the user's language.

English is the source language: every text is written in English in the code and wrapped in
``tr()``, which looks it up in the catalogue of the current language (``i18n_cs.CS``) and
falls back to the English text. Texts kept in constants are marked with ``N_()``, which does
nothing, and translated with ``tr()`` where they are shown. ``tests/test_i18n.py`` checks
that every marked text has a translation with the same placeholders.

The language is a context variable, set at the start of every run of the page, so two
browser tabs in different languages do not mix.
"""

from contextvars import ContextVar

from portfolio.core.i18n_cs import CS

LANGUAGES = {"cs": "Čeština", "en": "English"}
DEFAULT = "en"

_CATALOGUES = {"cs": CS}
_current: ContextVar[str] = ContextVar("language", default=DEFAULT)


def set_language(code: str) -> None:
    _current.set(code if code in LANGUAGES else DEFAULT)


def language() -> str:
    return _current.get()


def tr(text: str, /, **params) -> str:
    """``text`` in the current language, with ``{name}`` placeholders filled from ``params``."""
    translated = _CATALOGUES.get(_current.get(), {}).get(text, text)
    return translated.format(**params) if params else translated


def N_(text: str) -> str:  # noqa: N802 - the usual name of the gettext marker
    """Marks a text for translation where it is defined; ``tr()`` translates it when shown."""
    return text
