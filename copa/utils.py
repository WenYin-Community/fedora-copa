"""Utility functions"""

import shutil
import sys


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

    print("Error: dnf5 or dnf not found", file=sys.stderr)
    sys.exit(1)


def confirm(prompt: str, default: bool = False) -> bool:
    """Confirmation prompt"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        response = input(prompt + suffix).strip().lower()
    except EOFError:
        # Non-interactive input (piped/redirected) - fall back to default
        return default

    if not response:
        return default

    return response in ("y", "yes")
