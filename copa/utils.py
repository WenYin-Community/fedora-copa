"""工具函数"""

import shutil
import subprocess
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
    """检查命令是否存在"""
    return shutil.which(command) is not None


def check_dnf5() -> bool:
    """Check if dnf5 is available"""
    return check_command_exists("dnf5")


def check_dnf() -> bool:
    """Check if dnf is available"""
    return check_command_exists("dnf")


def check_copr_cli() -> bool:
    """Check if copr-cli is available"""
    return check_command_exists("copr-cli")


def get_dnf_binary() -> str:
    """Get available dnf binary"""
    if check_dnf5():
        return "dnf5"
    elif check_dnf():
        return "dnf"
    else:
        print("Error: dnf5 or dnf not found", file=sys.stderr)
        sys.exit(1)


def run_command(
    args: list[str],
    sudo: bool = False,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute command"""
    cmd: list[str] = []
    if sudo:
        cmd.append("sudo")
    cmd.extend(args)

    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Return code: {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

    return result


def confirm(prompt: str, default: bool = False) -> bool:
    """确认提示"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    response = input(prompt + suffix).strip().lower()

    if not response:
        return default

    return response in ("y", "yes")


def select_from_list(
    prompt: str,
    options: list[str],
    allow_quit: bool = True,
) -> int | None:
    """Select from a list"""
    for i, option in enumerate(options, 1):
        print(f"  [{i}] {option}")

    if allow_quit:
        print("  [q] 取消")

    while True:
        response = input(prompt).strip().lower()

        if allow_quit and response in ("q", "quit", "cancel"):
            return None

        try:
            choice = int(response)
            if 1 <= choice <= len(options):
                return choice - 1
            print(f"请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print("Enter a valid number or 'q' to cancel")


def format_size(size_bytes: int) -> str:
    """Format file size"""
    size: float = size_bytes
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def print_error(message: str) -> None:
    """Print error message"""
    print(f"错误: {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print warning message"""
    print(f"警告: {message}", file=sys.stderr)


def print_info(message: str) -> None:
    """Print info message"""
    print(message)
