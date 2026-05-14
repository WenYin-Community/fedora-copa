"""工具函数"""

import shutil
import subprocess
import sys
from typing import Optional


def check_command_exists(command: str) -> bool:
    """检查命令是否存在"""
    return shutil.which(command) is not None


def check_dnf5() -> bool:
    """检查 dnf5 是否可用"""
    return check_command_exists("dnf5")


def check_dnf() -> bool:
    """检查 dnf 是否可用"""
    return check_command_exists("dnf")


def check_copr_cli() -> bool:
    """检查 copr-cli 是否可用"""
    return check_command_exists("copr-cli")


def get_dnf_binary() -> str:
    """获取可用的 dnf 二进制文件"""
    if check_dnf5():
        return "dnf5"
    elif check_dnf():
        return "dnf"
    else:
        print("错误: 未找到 dnf5 或 dnf", file=sys.stderr)
        sys.exit(1)


def run_command(
    args: list[str],
    sudo: bool = False,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """执行命令"""
    cmd = []
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
            f"命令执行失败: {' '.join(cmd)}\n"
            f"返回码: {result.returncode}\n"
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
) -> Optional[int]:
    """从列表中选择"""
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
            print("请输入有效的数字或 'q' 取消")


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_error(message: str) -> None:
    """打印错误信息"""
    print(f"错误: {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    """打印警告信息"""
    print(f"警告: {message}", file=sys.stderr)


def print_info(message: str) -> None:
    """打印信息"""
    print(message)
