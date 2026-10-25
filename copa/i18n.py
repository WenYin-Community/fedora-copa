"""Minimal locale-aware translation support.

The source strings stay English (also used as catalog keys). When the system
locale is zh_CN, ``tr()`` returns the Chinese translation from
``copa/locales/zh_CN.json``. Every other locale falls back to English.
"""

import json
import locale
import os
from importlib import resources

_CATALOG: dict[str, str] | None = None


def _normalize_locale(value: str | None) -> str:
    """Normalize a locale string to ``language_COUNTRY`` (lowercase)."""
    if not value:
        return ""
    name = value.split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    return name.replace("-", "_").lower()


def current_locale() -> str:
    """Return the effective locale name, honoring POSIX precedence."""
    for variable in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(variable)
        if value:
            return _normalize_locale(value)
    try:
        return _normalize_locale(locale.getlocale()[0])
    except (TypeError, ValueError):
        return ""


def is_chinese() -> bool:
    """Whether the effective locale is Simplified Chinese (zh_CN)."""
    return current_locale() == "zh_cn"


def _load_catalog() -> dict[str, str]:
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG
    try:
        path = resources.files("copa") / "locales" / "zh_CN.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _CATALOG = data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, ValueError, TypeError):
        _CATALOG = {}
    return _CATALOG


def tr(message: str, **kwargs: object) -> str:
    """Translate an English message when the locale is zh_CN.

    ``kwargs`` are applied with ``str.format`` after translation, so templates
    must use the same named placeholders in both languages.
    """
    template = message
    if is_chinese():
        template = _load_catalog().get(message, message)
    if kwargs:
        return template.format(**kwargs)
    return template
