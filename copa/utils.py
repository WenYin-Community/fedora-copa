"""Utility functions"""

import shutil
import sys

from copa.i18n import tr

# Input aliases use escapes so CLI source files stay ASCII-only.
YES_ANSWERS = frozenset({"y", "yes", "\u662f", "\u662f\u7684", "\u597d", "\u786e\u5b9a"})
NO_ANSWERS = frozenset({"n", "no", "\u5426", "\u4e0d", "\u4e0d\u662f", "\u53d6\u6d88"})
CANCEL_ANSWERS = frozenset({"q", "quit", "\u9000\u51fa", "\u53d6\u6d88"})
SEARCH_ANSWERS = frozenset({"s", "\u641c\u7d22"})


def check_command_exists(command: str) -> bool:
    """Check if command exists"""
    return shutil.which(command) is not None


def get_dnf_binary(
    prefer_dnf5: bool = True, fallback_to_dnf: bool = True
) -> str:
    """Get available dnf binary, honoring backend preferences."""
    candidates = (["dnf5", "dnf"] if prefer_dnf5 else ["dnf", "dnf5"])
    if not fallback_to_dnf:
        candidates = candidates[:1]

    for command in candidates:
        if check_command_exists(command):
            return command

    print(tr("Error: dnf5 or dnf not found"), file=sys.stderr)
    sys.exit(1)


def read_input(prompt: str) -> str | None:
    """Read a line of input, returning None when stdin is closed."""
    try:
        return input(prompt)
    except EOFError:
        return None


def confirm(prompt: str, default: bool = False) -> bool:
    """Confirmation prompt (accepts English and Chinese answers)."""
    suffix = tr(" [Y/n]: ") if default else tr(" [y/N]: ")
    try:
        response = input(prompt + suffix).strip().lower()
    except EOFError:
        # Non-interactive input (piped/redirected) - fall back to default
        return default

    if not response:
        return default

    if response in YES_ANSWERS:
        return True
    if response in NO_ANSWERS:
        return False
    return False
