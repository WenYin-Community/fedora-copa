"""Utility functions"""

import shutil
import sys
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff"""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            wait = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        print(
                            f"  Retry {attempt + 1}/{max_attempts} "
                            f"after {wait:.0f}s: {e}",
                            file=sys.stderr,
                        )
                        time.sleep(wait)
                        wait *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def check_command_exists(command: str) -> bool:
    """Check if command exists"""
    return shutil.which(command) is not None


def get_dnf_binary() -> str:
    """Get available dnf binary"""
    if check_command_exists("dnf5"):
        return "dnf5"
    elif check_command_exists("dnf"):
        return "dnf"
    else:
        print("Error: dnf5 or dnf not found", file=sys.stderr)
        sys.exit(1)


def confirm(prompt: str, default: bool = False) -> bool:
    """Confirmation prompt"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    response = input(prompt + suffix).strip().lower()

    if not response:
        return default

    return response in ("y", "yes")
