"""命令行入口"""

import argparse
import sys
from typing import Optional

from copa import __app_name__, __version__


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="DNF5 风格的 Fedora Copr 软件包助手",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索软件包")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("--official-only", action="store_true", help="只搜索 Fedora 官方源")
    search_parser.add_argument("--rpmfusion-only", action="store_true", help="只搜索 RPM Fusion")
    search_parser.add_argument("--copr-only", action="store_true", help="只搜索 Copr")
    search_parser.add_argument("--json", action="store_true", help="JSON 输出")

    # install 命令
    install_parser = subparsers.add_parser("install", help="安装软件包")
    install_parser.add_argument("package", help="要安装的软件包名")
    install_parser.add_argument("--official-only", action="store_true", help="只从 Fedora 官方源安装")
    install_parser.add_argument("--rpmfusion-only", action="store_true", help="只从 RPM Fusion 安装")
    install_parser.add_argument("--copr-only", action="store_true", help="只从 Copr 安装")
    install_parser.add_argument("--copr", metavar="OWNER/PROJECT", help="使用指定的 Copr 仓库")
    install_parser.add_argument("--obs-only", action="store_true", help="只从 OBS 安装")
    install_parser.add_argument("--no-obs", action="store_true", help="跳过 OBS 搜索")
    install_parser.add_argument("--allow-obs-fallback", action="store_true", help="允许 OBS 版本 fallback")
    install_parser.add_argument("--keep-copr", action="store_true", help="安装后保留 Copr 仓库")
    install_parser.add_argument("--dry-run", action="store_true", help="只显示将执行的操作")
    install_parser.add_argument("-y", "--assumeyes", action="store_true", help="自动确认")

    # info 命令
    info_parser = subparsers.add_parser("info", help="显示软件包信息")
    info_parser.add_argument("package", help="软件包名或 owner/project")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出软件包")
    list_parser.add_argument("--packages", metavar="OWNER/PROJECT", help="列出指定 Copr 项目的包")

    # copr 子命令
    copr_parser = subparsers.add_parser("copr", help="管理 Copr 仓库")
    copr_subparsers = copr_parser.add_subparsers(dest="copr_command")

    copr_subparsers.add_parser("list", help="列出已启用的 Copr 仓库")

    copr_enable = copr_subparsers.add_parser("enable", help="启用 Copr 仓库")
    copr_enable.add_argument("repo", help="owner/project 格式的仓库名")
    copr_enable.add_argument("chroot", nargs="?", help="chroot（如 fedora-43-x86_64）")

    copr_disable = copr_subparsers.add_parser("disable", help="禁用 Copr 仓库")
    copr_disable.add_argument("repo", help="owner/project 格式的仓库名")

    copr_remove = copr_subparsers.add_parser("remove", help="移除 Copr 仓库")
    copr_remove.add_argument("repo", help="owner/project 格式的仓库名")

    # doctor 命令
    subparsers.add_parser("doctor", help="检查系统环境和依赖")

    # audit 命令
    subparsers.add_parser("audit", help="审计已启用的 Copr 仓库")

    return parser


def cmd_search(args: argparse.Namespace) -> int:
    """search 命令实现"""
    print(f"搜索: {args.keyword}")
    # TODO: 实现搜索逻辑
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """install 命令实现"""
    print(f"安装: {args.package}")
    # TODO: 实现安装逻辑
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """info 命令实现"""
    print(f"信息: {args.package}")
    # TODO: 实现信息查询
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """list 命令实现"""
    if args.packages:
        print(f"列出包: {args.packages}")
    else:
        print("列出所有已安装的包")
    # TODO: 实现列表逻辑
    return 0


def cmd_copr(args: argparse.Namespace) -> int:
    """copr 子命令实现"""
    if args.copr_command == "list":
        print("列出 Copr 仓库")
    elif args.copr_command == "enable":
        print(f"启用 Copr: {args.repo}")
    elif args.copr_command == "disable":
        print(f"禁用 Copr: {args.repo}")
    elif args.copr_command == "remove":
        print(f"移除 Copr: {args.repo}")
    else:
        print("请指定 copr 子命令")
        return 1
    # TODO: 实现 copr 管理逻辑
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """doctor 命令实现"""
    print("检查系统环境...")
    # TODO: 实现环境检查
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """audit 命令实现"""
    print("审计 Copr 仓库...")
    # TODO: 实现审计逻辑
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """主入口"""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "search": cmd_search,
        "install": cmd_install,
        "info": cmd_info,
        "list": cmd_list,
        "copr": cmd_copr,
        "doctor": cmd_doctor,
        "audit": cmd_audit,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
