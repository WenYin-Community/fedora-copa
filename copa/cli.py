"""Command line entry point."""

import argparse
import sys

from copa import __app_name__, __version__
from copa.cli_helpers import (
    _make_dnf,
    _obs_project_exists_in_system,
    _parse_owner_project,
    _search_local_repos,
)
from copa.commands import (
    _filter_by_keywords,
    _filter_by_regex,
    _filter_copr_by_keywords,
    _filter_copr_by_regex,
    _install_from_copr,
    _install_from_obs,
    _resolve_package_name,
    cmd_audit,
    cmd_doctor,
    cmd_info,
    cmd_install,
    cmd_list,
    cmd_provides,
    cmd_remove,
    cmd_repo,
    cmd_repoquery,
    cmd_search,
)
from copa.i18n import tr
from copa.ui import BOLD, GREEN, RED, RESET, YELLOW

__all__ = [
    "BOLD",
    "GREEN",
    "RED",
    "RESET",
    "YELLOW",
    "cmd_audit",
    "cmd_doctor",
    "cmd_info",
    "cmd_install",
    "cmd_list",
    "cmd_provides",
    "cmd_remove",
    "cmd_repo",
    "cmd_repoquery",
    "cmd_search",
    "create_parser",
    "main",
    "_filter_by_keywords",
    "_filter_by_regex",
    "_filter_copr_by_keywords",
    "_filter_copr_by_regex",
    "_install_from_copr",
    "_install_from_obs",
    "_make_dnf",
    "_obs_project_exists_in_system",
    "_parse_owner_project",
    "_resolve_package_name",
    "_search_local_repos",
]


_json_parser = argparse.ArgumentParser(add_help=False)
_json_parser.add_argument(
    "--json", action="store_true", default=argparse.SUPPRESS, help=tr("JSON output")
)


def _add_source_flags(parser: argparse.ArgumentParser) -> None:
    """Add mutually exclusive source selection flags."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--official-only", action="store_true",
        help=tr("Search Fedora official repos only")
    )
    group.add_argument(
        "--rpmfusion-only", action="store_true",
        help=tr("Search RPM Fusion only")
    )
    group.add_argument(
        "--copr-only", action="store_true",
        help=tr("Search Copr only")
    )
    group.add_argument(
        "--obs-only", action="store_true",
        help=tr("Search OBS only")
    )


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description=tr("DNF5-style Fedora Copr Package Assistant"),
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=tr("Output in JSON format"),
    )

    subparsers = parser.add_subparsers(dest="command", help=tr("available commands"))

    # search command
    search_parser = subparsers.add_parser(
        "search", help=tr("Search packages")
    )
    search_parser.add_argument(
        "keyword", nargs="+",
        help=tr("Search keywords (AND logic)")
    )
    _add_source_flags(search_parser)
    search_parser.add_argument(
        "--no-obs", action="store_true",
        help=tr("Skip OBS search")
    )
    search_parser.add_argument(
        "--include-local-repo", action="store_true",
        help=tr("Also search Fedora, RPM Fusion, Terra (default: Copr + OBS)")
    )
    search_parser.add_argument(
        "-x", "--regex", action="store_true",
        help=tr("Search using regex (name only)")
    )
    search_parser.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS,
        help=tr("JSON output")
    )

    # install command
    install_parser = subparsers.add_parser(
        "install", help=tr("Install package")
    )
    install_parser.add_argument(
        "package", help=tr("Package name to install")
    )
    _add_source_flags(install_parser)
    install_parser.add_argument(
        "--copr", metavar="OWNER/PROJECT",
        help=tr("Use specified Copr repo")
    )
    install_parser.add_argument(
        "--include-local-repo", action="store_true",
        help=tr("Also search Fedora, RPM Fusion, Terra (default: Copr + OBS only)")
    )
    install_parser.add_argument(
        "--no-obs", action="store_true",
        help=tr("Skip OBS search")
    )
    install_parser.add_argument(
        "--allow-obs-fallback", action="store_true",
        help=tr("Allow OBS version fallback")
    )
    install_parser.add_argument(
        "--keep-copr", action="store_true",
        help=tr("Keep Copr repo after install")
    )
    install_parser.add_argument(
        "--dry-run", action="store_true",
        help=tr("Show operations without executing")
    )
    install_parser.add_argument(
        "-y", "--assumeyes", action="store_true",
        help=tr("Auto confirm")
    )

    # info command
    info_parser = subparsers.add_parser(
        "info", help=tr("Show package info"), parents=[_json_parser]
    )
    info_parser.add_argument(
        "package", help=tr("Package name or owner/project")
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help=tr("List packages"), parents=[_json_parser]
    )
    list_parser.add_argument(
        "--packages", metavar="OWNER/PROJECT",
        help=tr("List packages in Copr project")
    )

    # repo subcommand
    repo_parser = subparsers.add_parser(
        "repo", help=tr("Manage third-party repos (Copr/OBS)"),
        parents=[_json_parser],
    )
    repo_subparsers = repo_parser.add_subparsers(
        dest="repo_command"
    )

    repo_subparsers.add_parser(
        "list", help=tr("List all third-party repos"), parents=[_json_parser]
    )

    repo_enable = repo_subparsers.add_parser(
        "enable", help=tr("Enable repo")
    )
    repo_enable.add_argument(
        "repo", help=tr("Repo name: copr:owner/project or obs:project")
    )
    repo_enable.add_argument(
        "chroot", nargs="?",
        help=tr("chroot for Copr (e.g. fedora-43-x86_64)")
    )

    repo_disable = repo_subparsers.add_parser(
        "disable", help=tr("Disable repo")
    )
    repo_disable.add_argument(
        "repo", help=tr("Repo name: copr:owner/project or obs:project")
    )

    repo_remove = repo_subparsers.add_parser("remove", help=tr("Remove repo"))
    repo_remove.add_argument(
        "repo", help=tr("Repo name: copr:owner/project or obs:project")
    )

    # repoquery command
    repoquery_parser = subparsers.add_parser(
        "repoquery", help=tr("Query package dependencies"), parents=[_json_parser]
    )
    repoquery_parser.add_argument(
        "package", help=tr("Package name to query")
    )
    query_group = repoquery_parser.add_mutually_exclusive_group()
    query_group.add_argument(
        "--requires", action="store_true",
        help=tr("Show package dependencies")
    )
    query_group.add_argument(
        "--provides", action="store_true",
        help=tr("Show what package provides")
    )
    query_group.add_argument(
        "--files", action="store_true",
        help=tr("Show package files")
    )

    # provides command
    provides_parser = subparsers.add_parser(
        "provides", help=tr("Find packages providing a file"), parents=[_json_parser]
    )
    provides_parser.add_argument(
        "file", help=tr("File path or command name")
    )

    # doctor command
    subparsers.add_parser(
        "doctor", help=tr("Check system environment and dependencies"),
        parents=[_json_parser],
    )

    # audit command
    subparsers.add_parser(
        "audit", help=tr("Audit enabled Copr repos"), parents=[_json_parser]
    )

    # remove command
    remove_parser = subparsers.add_parser(
        "remove", help=tr("Remove installed package")
    )
    remove_parser.add_argument(
        "package", help=tr("Package name to remove")
    )
    remove_parser.add_argument(
        "-y", "--assumeyes", action="store_true",
        help=tr("Auto confirm"),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point"""
    import signal

    from copa.config import Config

    # Ctrl+C interrupt handler
    def signal_handler(sig, frame):
        print(f"\n{YELLOW}{tr('Interrupted by user')}{RESET}")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)

    # Load config file
    config = Config.load()

    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Pass config to command
    args.config = config
    if config.ui.json and not args.json:
        args.json = True

    commands = {
        "search": cmd_search,
        "install": cmd_install,
        "remove": cmd_remove,
        "info": cmd_info,
        "list": cmd_list,
        "repo": cmd_repo,
        "repoquery": cmd_repoquery,
        "provides": cmd_provides,
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
