"""Command line entry point"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from copa import __app_name__, __version__

# ANSI color codes
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BOLD = "\033[1m"
RESET = "\033[0m"


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="DNF5-style Fedora Copr Package Assistant",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    subparsers = parser.add_subparsers(dest="command", help="available commands")

    # search command
    search_parser = subparsers.add_parser(
        "search", help="Search packages"
    )
    search_parser.add_argument(
        "keyword", nargs="+",
        help="Search keywords (AND logic)"
    )
    search_parser.add_argument(
        "--official-only", action="store_true",
        help="Search Fedora official repos only"
    )
    search_parser.add_argument(
        "--rpmfusion-only", action="store_true",
        help="Search RPM Fusion only"
    )
    search_parser.add_argument(
        "--copr-only", action="store_true",
        help="Search Copr only"
    )
    search_parser.add_argument(
        "-x", "--regex", action="store_true",
        help="Search using regex (name only)"
    )
    search_parser.add_argument(
        "--json", action="store_true",
        help="JSON output"
    )

    # install command
    install_parser = subparsers.add_parser(
        "install", help="Install package"
    )
    install_parser.add_argument(
        "package", help="Package name to install"
    )
    install_parser.add_argument(
        "--official-only", action="store_true",
        help="Install from Fedora official repos only"
    )
    install_parser.add_argument(
        "--rpmfusion-only", action="store_true",
        help="Install from RPM Fusion only"
    )
    install_parser.add_argument(
        "--copr-only", action="store_true",
        help="Install from Copr only"
    )
    install_parser.add_argument(
        "--copr", metavar="OWNER/PROJECT",
        help="Use specified Copr repo"
    )
    install_parser.add_argument(
        "--obs-only", action="store_true",
        help="Install from OBS only"
    )
    install_parser.add_argument(
        "--include-local-repo", action="store_true",
        help="Also search Fedora, RPM Fusion, Terra (default: Copr + OBS only)"
    )
    install_parser.add_argument(
        "--no-obs", action="store_true",
        help="Skip OBS search"
    )
    install_parser.add_argument(
        "--allow-obs-fallback", action="store_true",
        help="Allow OBS version fallback"
    )
    install_parser.add_argument(
        "--keep-copr", action="store_true",
        help="Keep Copr repo after install"
    )
    install_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show operations without executing"
    )
    install_parser.add_argument(
        "-y", "--assumeyes", action="store_true",
        help="Auto confirm"
    )

    # info command
    info_parser = subparsers.add_parser(
        "info", help="Show package info"
    )
    info_parser.add_argument(
        "package", help="Package name or owner/project"
    )

    # list command
    list_parser = subparsers.add_parser(
        "list", help="List packages"
    )
    list_parser.add_argument(
        "--packages", metavar="OWNER/PROJECT",
        help="List packages in Copr project"
    )

    # repo subcommand
    repo_parser = subparsers.add_parser(
        "repo", help="Manage third-party repos (Copr/OBS)"
    )
    repo_subparsers = repo_parser.add_subparsers(
        dest="repo_command"
    )

    repo_subparsers.add_parser(
        "list", help="List all third-party repos"
    )

    repo_enable = repo_subparsers.add_parser(
        "enable", help="Enable repo"
    )
    repo_enable.add_argument(
        "repo", help="Repo name: copr:owner/project or obs:project"
    )
    repo_enable.add_argument(
        "chroot", nargs="?",
        help="chroot for Copr (e.g. fedora-43-x86_64)"
    )

    repo_disable = repo_subparsers.add_parser(
        "disable", help="Disable repo"
    )
    repo_disable.add_argument(
        "repo", help="Repo name: copr:owner/project or obs:project"
    )

    repo_remove = repo_subparsers.add_parser("remove", help="Remove repo")
    repo_remove.add_argument(
        "repo", help="Repo name: copr:owner/project or obs:project"
    )

    # repoquery command
    repoquery_parser = subparsers.add_parser(
        "repoquery", help="Query package dependencies"
    )
    repoquery_parser.add_argument(
        "package", help="Package name to query"
    )
    repoquery_parser.add_argument(
        "--requires", action="store_true",
        help="Show package dependencies"
    )
    repoquery_parser.add_argument(
        "--provides", action="store_true",
        help="Show what package provides"
    )
    repoquery_parser.add_argument(
        "--files", action="store_true",
        help="Show package files"
    )

    # provides command
    provides_parser = subparsers.add_parser(
        "provides", help="Find packages providing a file"
    )
    provides_parser.add_argument(
        "file", help="File path or command name"
    )

    # doctor command
    subparsers.add_parser(
        "doctor", help="Check system environment and dependencies"
    )

    # audit command
    subparsers.add_parser(
        "audit", help="Audit enabled Copr repos"
    )

    # remove command
    remove_parser = subparsers.add_parser(
        "remove", help="Remove installed package"
    )
    remove_parser.add_argument(
        "package", help="Package name to remove"
    )
    remove_parser.add_argument(
        "-y", "--assumeyes", action="store_true",
        help="Auto confirm",
    )

    return parser


def cmd_search(args: argparse.Namespace) -> int:
    """search command implementation - supports multi-keyword AND logic and regex search"""
    import json
    import re

    from copa.copr_backend import CoprBackend
    from copa.dnf_backend import DnfBackend
    from copa.search import SearchEngine

    keywords = [k.lower() for k in args.keyword]
    search_query = " ".join(args.keyword)
    use_json = args.json if hasattr(args, 'json') else False
    use_regex = args.regex if hasattr(args, 'regex') else False

    # Regex pattern validation
    regex_patterns = []
    if use_regex:
        for kw in args.keyword:
            try:
                regex_patterns.append(re.compile(kw, re.IGNORECASE))
            except re.error as e:
                if not use_json:
                    print(f"{RED}Invalid regex '{kw}': {e}{RESET}")
                return 1

    # Initialize backends
    dnf = DnfBackend()
    copr = CoprBackend()
    engine = SearchEngine(dnf=dnf, copr=copr)

    # Get enabled repos
    enabled_repos = dnf.get_enabled_repos()

    # Collect all results
    all_results: dict[str, Any] = {
        "query": search_query,
        "regex": use_regex,
        "fedora": [],
        "rpmfusion": [],
        "terra": [],
        "copr": [],
    }

    if not use_json:
        print(f"Searching: {search_query}")
        if use_regex:
            print(f"{YELLOW}(regex mode - matching package names only){RESET}")
        print()

        # Third-party source risk warning
        if not args.official_only:
            print(f"{RED}WARNING: Packages from sources other than Fedora official repos")
            print("  (RPM Fusion, Terra, Copr, OBS) are built by third parties.")
            print(f"  Please verify the risks before installation.{RESET}\n")

    # Search Fedora official repos
    if not args.copr_only:
        if not use_json:
            print("Searching Fedora official repos...")
        fedora_results = dnf.search_in_repos(search_query, enabled_repos["fedora"])
        # Regex mode: match package names only
        if use_regex:
            fedora_results = _filter_by_regex(fedora_results, regex_patterns)
        else:
            fedora_results = _filter_by_keywords(fedora_results, keywords, match_desc=False)
        for pkg in fedora_results[:10]:
            all_results["fedora"].append({
                "name": pkg.name,
                "evr": pkg.evr,
                "arch": pkg.arch,
                "repo": pkg.repo,
                "summary": pkg.summary,
            })
        if not use_json and fedora_results:
            print(f"  Found {len(fedora_results)} results:")
            for pkg in fedora_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # Search RPM Fusion
    if not args.official_only and not args.copr_only and enabled_repos["rpmfusion"]:
        if not use_json:
            print("Searching RPM Fusion...")
        rpmfusion_results = dnf.search_in_repos(search_query, enabled_repos["rpmfusion"])
        if use_regex:
            rpmfusion_results = _filter_by_regex(rpmfusion_results, regex_patterns)
        else:
            rpmfusion_results = _filter_by_keywords(rpmfusion_results, keywords, match_desc=False)
        for pkg in rpmfusion_results[:10]:
            all_results["rpmfusion"].append({
                "name": pkg.name,
                "evr": pkg.evr,
                "arch": pkg.arch,
                "repo": pkg.repo,
                "summary": pkg.summary,
            })
        if not use_json and rpmfusion_results:
            print(f"  Found {len(rpmfusion_results)} results:")
            for pkg in rpmfusion_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # Search Terra
    if not args.official_only and not args.copr_only and enabled_repos["terra"]:
        if not use_json:
            print("Searching Terra...")
        terra_results = dnf.search_in_repos(search_query, enabled_repos["terra"])
        if use_regex:
            terra_results = _filter_by_regex(terra_results, regex_patterns)
        else:
            terra_results = _filter_by_keywords(terra_results, keywords, match_desc=False)
        for pkg in terra_results[:10]:
            all_results["terra"].append({
                "name": pkg.name,
                "evr": pkg.evr,
                "arch": pkg.arch,
                "repo": pkg.repo,
                "summary": pkg.summary,
            })
        if not use_json and terra_results:
            print(f"  Found {len(terra_results)} results:")
            for pkg in terra_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # Search Copr
    if not args.official_only and not args.rpmfusion_only:
        if not use_json:
            print("Searching Copr repos...")
        chroot = dnf.get_chroot()
        fedora_version = dnf.get_fedora_version()
        copr_results = engine.search_copr(
            search_query, chroot, fedora_version,
        )
        if use_regex:
            copr_results = _filter_copr_by_regex(copr_results, regex_patterns)
        else:
            copr_results = _filter_copr_by_keywords(copr_results, keywords)
        for result in copr_results[:10]:
            all_results["copr"].append({
                "owner": result.project.owner,
                "name": result.project.name,
                "description": result.project.description[:100],
                "supports_chroot": result.supports_chroot,
                "version_gap": result.version_gap,
                "risk_level": result.risk_level,
            })
        if not use_json and copr_results:
            print(f"  Found {len(copr_results)} Copr projects:")
            for i, result in enumerate(copr_results[:10], 1):
                if result.supports_chroot:
                    chroot_status = "✓"
                elif result.best_chroot:
                    chroot_status = f"⚠ fallback ({result.best_chroot})"
                else:
                    chroot_status = "✗"
                print(f"    [{i}] {result.project.owner}/{result.project.name}")
                print(f"        {result.project.description[:60]}...")
                print(f"        Chroot: {chroot_status} | Risk: {result.risk_level}")
            print()

    # JSON output
    if use_json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
        return 0

    return 0

    return 0


def _filter_by_keywords(
    packages: list[Any], keywords: list[str], match_desc: bool = True
) -> list[Any]:
    """Filter packages by keywords - AND logic"""
    def matches(pkg: Any) -> bool:
        name_lower = pkg.name.lower()
        desc_lower = pkg.summary.lower() if hasattr(pkg, 'summary') else ""
        for kw in keywords:
            name_match = kw in name_lower
            desc_match = match_desc and kw in desc_lower
            if not name_match and not desc_match:
                return False
        return True
    return [p for p in packages if matches(p)]


def _filter_by_regex(
    packages: list[Any], patterns: list[Any]
) -> list[Any]:
    """Filter packages by regex - match names only, AND logic"""
    def matches(pkg: Any) -> bool:
        name = pkg.name
        for pattern in patterns:
            if not pattern.search(name):
                return False
        return True
    return [p for p in packages if matches(p)]


def _filter_copr_by_keywords(
    results: list[Any], keywords: list[str]
) -> list[Any]:
    """Filter Copr results by keywords - AND logic"""
    def matches(result: Any) -> bool:
        name_lower = result.project.name.lower()
        owner_lower = result.project.owner.lower()
        for kw in keywords:
            if kw not in name_lower and kw not in owner_lower:
                return False
        return True
    return [r for r in results if matches(r)]


def _filter_copr_by_regex(
    results: list[Any], patterns: list[Any]
) -> list[Any]:
    """Filter Copr results by regex - match project names only, AND logic"""
    def matches(result: Any) -> bool:
        name = result.project.name
        for pattern in patterns:
            if not pattern.search(name):
                return False
        return True
    return [r for r in results if matches(r)]


def cmd_install(args: argparse.Namespace) -> int:
    """install command implementation"""
    from copa.copr_backend import CoprBackend
    from copa.dnf_backend import DnfBackend
    from copa.obs_backend import OBSBackend
    from copa.search import SearchEngine
    from copa.state import AppState

    package = args.package
    dnf = DnfBackend()
    copr = CoprBackend()
    obs = OBSBackend()
    engine = SearchEngine(dnf=dnf, copr=copr, obs=obs)
    state = AppState.load()

    # Get enabled repos
    enabled_repos = dnf.get_enabled_repos()
    fedora_version = dnf.get_fedora_version()

    print(f"Installing: {package}\n")

    # Third-party source risk warning
    if not args.official_only:
        print(f"{RED}WARNING: Packages from sources other than Fedora official repos")
        print("  (RPM Fusion, Terra, Copr, OBS) are built by third parties.")
        print(f"  Please verify the risks before installation.{RESET}\n")

    # Dry-run 模式
    if args.dry_run:
        print("[dry-run] Will execute:")
        print(f"  1. Search {package} in Copr/OBS")
        if args.include_local_repo:
            print(f"     Also search: Fedora/RPM Fusion/Terra")
        print(f"  2. If found: sudo dnf5 install {package}")
        print("  3. If from Copr/OBS, ask whether to keep repo")
        return 0

    # Steps 1-3: Search Fedora/RPM Fusion/Terra (only when explicitly requested)
    search_local = args.include_local_repo or args.official_only or args.rpmfusion_only
    if search_local and not args.copr_only and not args.obs_only:
        local_results: list[tuple[str, Any]] = []

        # Search Fedora
        if not args.rpmfusion_only:
            print("Searching Fedora official repos...")
            for pkg in dnf.search_in_repos(package, enabled_repos["fedora"]):
                local_results.append(("Fedora", pkg))

        # Search RPM Fusion
        if not args.official_only and enabled_repos["rpmfusion"]:
            print("Searching RPM Fusion...")
            for pkg in dnf.search_in_repos(package, enabled_repos["rpmfusion"]):
                local_results.append(("RPM Fusion", pkg))

        # Search Terra
        if not args.official_only and enabled_repos["terra"]:
            print("Searching Terra...")
            for pkg in dnf.search_in_repos(package, enabled_repos["terra"]):
                local_results.append(("Terra", pkg))

        if local_results:
            # Deduplicate by name
            seen: set[str] = set()
            unique_local: list[tuple[str, Any]] = []
            for source, pkg in local_results:
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    unique_local.append((source, pkg))

            print(f"\nFound {len(unique_local)} package(s) in local repos:\n")
            for i, (source, pkg) in enumerate(unique_local, 1):
                print(f"  [{i:2d}] {pkg.name}-{pkg.evr} ({source})")
                if pkg.summary:
                    print(f"       {pkg.summary}")

            if args.assumeyes:
                target_name = unique_local[0][1].name
                print(f"\n  Auto-selected: {target_name}")
                print(f"\nExecuting: sudo dnf5 install {target_name}")
                if dnf.install(target_name):
                    print("Installation successful!")
                else:
                    print("Installation failed")
                return 0

            choice = input(
                f"{BOLD}\nSelect [1-{len(unique_local)}], "
                f"'s' to search Copr/OBS, 'q' to cancel: {RESET}"
            ).strip().lower()
            if choice in ("q", "quit"):
                return 0
            if choice == "s":
                pass  # fall through to Copr/OBS search
            else:
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(unique_local):
                        target_name = unique_local[idx - 1][1].name
                        print(f"\nExecuting: sudo dnf5 install {target_name}")
                        if dnf.install(target_name):
                            print("Installation successful!")
                        else:
                            print("Installation failed")
                        return 0
                except ValueError:
                    pass
                print("Invalid input, continuing to Copr/OBS search...")

    # Steps 4-16: Search Copr and OBS (merged results)
    if not args.official_only and not args.rpmfusion_only:
        chroot = dnf.get_chroot()
        all_sources: list[tuple[str, Any]] = []

        # 并行搜索 Copr 和 OBS
        search_copr = not args.obs_only
        search_obs = not args.no_obs and not args.copr_only

        # Check OBS auth before searching
        if search_obs and not obs.has_auth:
            print(f"{YELLOW}OBS: credentials not configured, skipping.{RESET}")
            print("  Configure: osc config (set user/pass for api.opensuse.org)\n")
            search_obs = False

        if search_copr and search_obs:
            print("Searching Copr and OBS repos...")
            with ThreadPoolExecutor(max_workers=2) as pool:
                future_copr = pool.submit(
                    engine.search_copr, package, chroot, fedora_version,
                )
                future_obs = pool.submit(engine.search_obs, package, fedora_version)
                for future in as_completed([future_copr, future_obs]):
                    try:
                        results = future.result(timeout=60)
                    except Exception:
                        results = []
                    if future is future_copr:
                        for r in results[:10]:
                            all_sources.append(("copr", r))
                    else:
                        for r in results[:10]:
                            all_sources.append(("obs", r))
        else:
            if search_copr:
                print("Searching Copr repos...")
                copr_results = engine.search_copr(package, chroot, fedora_version)
                for r in copr_results[:10]:
                    all_sources.append(("copr", r))
            if search_obs:
                print("Searching OBS repos...")
                obs_results_list: list[Any] = engine.search_obs(package, fedora_version)
                for r in obs_results_list[:10]:
                    all_sources.append(("obs", r))

        if all_sources:
            print(f"\nFound {len(all_sources)} packages from third-party repos:\n")

            # Unified display list
            for i, (source, data) in enumerate(all_sources, 1):
                if source == "copr":
                    if data.supports_chroot:
                        chroot_status = "✓"
                    elif data.best_chroot:
                        chroot_status = f"⚠ fallback"
                    else:
                        chroot_status = "✗"
                    print(f"  [{i:2d}] [Copr] {data.project.owner}/{data.project.name}")
                    print(f"       {data.project.description[:50]}...")
                    print(f"       Chroot: {chroot_status} | Risk: {data.risk_level}")
                else:  # obs
                    version_status = "✓" if data.has_current_version else "⚠ fallback"
                    print(f"  [{i:2d}] [OBS]  {data.package.project}/{data.package.name}")
                    print(f"       {data.package.description[:50]}...")
                    print(f"       Version: {version_status} | Risk: {data.risk_level}")

            # User selection
            if args.assumeyes and not args.copr:
                print(f"\n{RED}Error: --copr OWNER/PROJECT required in non-interactive mode{RESET}")
                return 1

            if args.copr:
                # Use specified Copr
                owner, project = args.copr.split("/", 1)
                selected = None
                selected_source = None
                for source, data in all_sources:
                    if (source == "copr"
                            and data.project.owner == owner
                            and data.project.name == project):
                        selected = data
                        selected_source = "copr"
                        break
                if not selected:
                    print(f"\n{RED}Error: Copr project {args.copr} not found{RESET}")
                    return 1
            else:
                # Interactive selection
                choice = input(
                    f"{BOLD}\nSelect package "
                    f"[1-{len(all_sources)}, q to cancel]: {RESET}"
                ).strip().lower()
                if choice in ("q", "quit"):
                    return 0
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_sources):
                        selected_source, selected = all_sources[idx]
                    else:
                        print("Invalid selection")
                        return 1
                except ValueError:
                    print("Invalid input")
                    return 1

            # Execute installation based on source
            if selected_source == "copr":
                return _install_from_copr(args, dnf, state, engine, package, selected, chroot)
            else:
                return _install_from_obs(args, dnf, obs, state, package, selected, fedora_version)

    print(f"\nPackage {package} not found")
    return 1


def _resolve_package_name(
    dnf: Any,
    package: str,
    repo_id: str,
    assumeyes: bool = False,
) -> str | None:
    """Search for actual package name in the repo, list for user selection. Returns None if not found."""
    found = dnf.search(package, repo=repo_id)

    if not found:
        print(f"  No packages matching '{package}' found in repo")
        return None

    # 去重
    seen: set[str] = set()
    unique: list[Any] = []
    for pkg in found:
        if pkg.name not in seen:
            seen.add(pkg.name)
            unique.append(pkg)

    # Always list for user selection
    print(f"  Found {len(unique)} package(s):")
    for i, pkg in enumerate(unique, 1):
        print(f"    [{i}] {pkg.name}-{pkg.evr} ({pkg.repo})")
        if pkg.summary:
            print(f"        {pkg.summary}")

    if assumeyes:
        print(f"  Auto-selected: {unique[0].name}")
        return unique[0].name

    while True:
        choice = input(
            f"{BOLD}\nSelect package [1-{len(unique)}]: {RESET}"
        ).strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(unique):
                return unique[idx - 1].name
        except ValueError:
            pass
        print("Invalid input, try again.")


def _install_from_copr(
    args: argparse.Namespace,
    dnf: Any,
    state: Any,
    engine: Any,
    package: str,
    selected: Any,
    chroot: str,
) -> int:
    """Install from Copr"""
    owner_project = f"{selected.project.owner}/{selected.project.name}"
    repo_id = f"copr:copr.fedorainfracloud.org:{selected.project.owner}:{selected.project.name}"

    # Determine chroot to use
    use_chroot = selected.best_chroot or chroot

    # 版本降级风险提示
    if selected.version_gap > 0:
        fedora_version = dnf.get_fedora_version()
        target_version = fedora_version - selected.version_gap
        print(f"\n{RED}WARNING: Version fallback!{RESET}")
        print(f"Project: {owner_project}")
        print(f"Current system: Fedora {fedora_version} ({chroot})")
        print(f"Fallback to: Fedora {target_version} ({use_chroot})")
        print(f"{RED}This package was built for an older Fedora version.")
        print(f"It may have dependency issues or not work correctly.{RESET}")

        if not args.assumeyes:
            from copa.utils import confirm
            if not confirm(f"{BOLD}Continue anyway?{RESET}", default=False):
                return 0

    print(f"\nEnabling Copr: {owner_project} ({use_chroot})")

    if not args.dry_run:
        if not dnf.copr_enable(owner_project, use_chroot):
            print("Failed to enable Copr")
            return 1

        print("Refreshing cache...")
        dnf.makecache()

        # 在 Copr 仓库内查找实际包名
        print(f"Searching for '{package}' in {owner_project}...")
        install_name = _resolve_package_name(
            dnf, package, repo_id, args.assumeyes,
        )

        if not install_name:
            print(f"{RED}No matching package found in {owner_project}{RESET}")
            print(f"  copa repo disable copr:{owner_project}")
            print(f"  copa repo remove copr:{owner_project}")
            return 1

        # 安装前确认
        if not args.assumeyes:
            from copa.utils import confirm
            if not confirm(f"{BOLD}\nInstall {install_name}?{RESET}", default=True):
                print("Cancelled, Copr repo kept enabled")
                print(f"  copa repo disable copr:{owner_project}")
                print(f"  copa repo remove copr:{owner_project}")
                return 0

        print(f"Installing {install_name}...")
        if dnf.install(install_name):
            print("Installation successful!")

            state.add_copr_repo(
                owner=selected.project.owner,
                project=selected.project.name,
                repo_id=f"copr:{owner_project}",
                chroot=use_chroot,
            )
            state.save()

            if not args.keep_copr:
                print(f"{BOLD}\nCopr repo {owner_project} is kept enabled.{RESET}")
                print(f"{YELLOW}Note: This repo will participate in system updates.")
                print(f"If you don't want this, you can disable or remove it:{RESET}")
                print(f"  copa repo disable copr:{owner_project}")
                print(f"  copa repo remove copr:{owner_project}")

                choice = input(f"{BOLD}\nDisable repo now? [y/N]: {RESET}").strip().lower()
                if choice in ("y", "yes"):
                    print("Disabling repo...")
                    dnf.copr_disable(owner_project)
                else:
                    print("Keeping repo enabled")
        else:
            print("Installation failed")
            print(f"{YELLOW}Copr repo {owner_project} is kept enabled.{RESET}")
            print("You can disable or remove it:")
            print(f"  copa repo disable copr:{owner_project}")
            print(f"  copa repo remove copr:{owner_project}")
            return 1
    else:
        print("[dry-run] Will execute:")
        print(f"  sudo dnf5 copr enable {owner_project} {use_chroot}")
        print("  sudo dnf5 makecache --refresh")
        print(f"  sudo dnf5 install {package}")

    return 0


def _install_from_obs(
    args: argparse.Namespace,
    dnf: Any,
    obs: Any,
    state: Any,
    package: str,
    selected: Any,
    fedora_version: int,
) -> int:
    """Install from OBS"""
    # Version fallback warning
    if not selected.has_current_version and selected.best_repo:
        print(f"\n{RED}WARNING: Version mismatch!{RESET}")
        print(f"Package: {package}")
        print(f"Available for: Fedora {selected.best_repo.fedora_version}")
        print(f"Your system: Fedora {fedora_version}")
        print(f"{RED}This package was built for an older Fedora version.")
        print(f"It may have dependency issues or not work correctly.{RESET}")

        if not args.allow_obs_fallback:
            from copa.utils import confirm
            if not confirm(f"{BOLD}Continue anyway?{RESET}", default=False):
                return 0

    if selected.best_repo:
        print("\nDownloading repo file to /etc/yum.repos.d/...")
        if not args.dry_run:
            if obs.download_repo_file(selected.package.project, selected.best_repo.repository):
                print("✓ Repo file downloaded")

                state.add_obs_repo(
                    project=selected.package.project,
                    repository=selected.best_repo.repository,
                    repo_file_name=obs._get_repo_file_name(selected.package.project),
                    fedora_version=selected.best_repo.fedora_version or "",
                )
                state.save()

                print("Refreshing cache...")
                dnf.makecache()

                # 在 OBS 仓库内查找实际包名
                obs_repo_id = selected.package.project.replace(":", "_").replace("/", "_")
                print(f"Searching for '{package}' in {obs_repo_id}...")
                install_name = _resolve_package_name(
                    dnf, package, obs_repo_id, args.assumeyes,
                )

                if not install_name:
                    print(f"{RED}No matching package found in {selected.package.project}{RESET}")
                    print(f"  copa repo disable obs:{selected.package.project}")
                    print(f"  copa repo remove obs:{selected.package.project}")
                    return 1

                # 安装前确认
                if not args.assumeyes:
                    from copa.utils import confirm
                    if not confirm(f"{BOLD}\nInstall {install_name}?{RESET}", default=True):
                        print("Cancelled, OBS repo kept enabled")
                        print(f"  copa repo disable obs:{selected.package.project}")
                        print(f"  copa repo remove obs:{selected.package.project}")
                        return 0

                print(f"Installing {install_name}...")
                if dnf.install(install_name):
                    print("Installation successful!")

                    print(
                        f"{BOLD}\nOBS repo "
                        f"{selected.package.project} "
                        f"is kept enabled.{RESET}"
                    )
                    print(f"{YELLOW}Note: This repo will participate in system updates.")
                    print(f"If you don't want this, you can disable or remove it:{RESET}")
                    print(f"  copa repo disable obs:{selected.package.project}")
                    print(f"  copa repo remove obs:{selected.package.project}")

                    choice = input(f"{BOLD}\nDisable repo now? [y/N]: {RESET}").strip().lower()
                    if choice in ("y", "yes"):
                        print("Disabling repo...")
                        obs.disable_repo(selected.package.project)
                    else:
                        print("Keeping repo enabled")
                else:
                    print("Installation failed")
                    print(f"{YELLOW}OBS repo {selected.package.project} is kept enabled.{RESET}")
                    print("You can disable or remove it:")
                    print(f"  copa repo disable obs:{selected.package.project}")
                    print(f"  copa repo remove obs:{selected.package.project}")
                    return 1
            else:
                print("✗ Failed to download repo file")
                return 1
        else:
            print("[dry-run] Will execute:")
            repo_url = obs.get_repo_file_url(
                selected.package.project,
                selected.best_repo.repository
            )
            print(f"  Download repo: {repo_url}")
            print("  sudo dnf5 makecache --refresh")
            print(f"  sudo dnf5 install {package}")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """info command implementation"""
    import json

    from copa.copr_backend import CoprBackend
    from copa.dnf_backend import DnfBackend

    package = args.package
    use_json = args.json if hasattr(args, 'json') else False
    dnf = DnfBackend()
    copr = CoprBackend()

    result_data: dict[str, Any] = {
        "package": package,
        "type": "unknown",
        "repos": [],
        "copr_projects": [],
    }

    # Check if it is a owner/project 格式
    if "/" in package:
        # Copr 项目详情
        owner, project = package.split("/", 1)
        result_data["type"] = "copr_project"
        project_info = copr.get_project(owner, project)
        if project_info:
            result_data["copr_projects"].append({
                "owner": project_info.owner,
                "name": project_info.name,
                "description": project_info.description,
                "chroots": project_info.chroots[:5],
            })
            if not use_json:
                print(f"Package: {package}\n")
                print(f"Fetching Copr project info: {owner}/{project}")
                print(f"  Name: {project_info.name}")
                print(f"  Owner: {project_info.owner}")
                print(f"  Description: {project_info.description[:200]}")
                print(f"  Supported chroots: {', '.join(project_info.chroots[:5])}")
                if project_info.instructions:
                    print(f"  Instructions: {project_info.instructions[:200]}")
        else:
            if not use_json:
                print(f"Package: {package}\n")
                print(f"  Project not found: {owner}/{project}")
            return 1
    else:
        # 软件包详情
        result_data["type"] = "package"
        if not use_json:
            print(f"Package: {package}\n")
            print("Searching in enabled repos...")

        enabled_repos = dnf.get_enabled_repos()
        all_repo_ids = (
            enabled_repos["fedora"]
            + enabled_repos["rpmfusion"]
            + enabled_repos["terra"]
        )

        if all_repo_ids:
            results = dnf.search_in_repos(package, all_repo_ids)
            for pkg in results[:10]:
                result_data["repos"].append({
                    "name": pkg.name,
                    "evr": pkg.evr,
                    "arch": pkg.arch,
                    "repo": pkg.repo,
                    "summary": pkg.summary,
                })
            if not use_json and results:
                print(f"\nFound {len(results)} packages:")
                for pkg in results[:10]:
                    print(f"\n  {pkg.name}-{pkg.evr}")
                    print(f"    Arch: {pkg.arch}")
                    print(f"    Repo: {pkg.repo}")
                    print(f"    Summary: {pkg.summary}")
            elif not use_json:
                print(f"\nPackage '{package}' not found in enabled repos")

        # Search Copr
        if not use_json:
            print("\nSearching Copr projects...")
        copr_results = copr.search_projects(package)
        for proj in copr_results[:5]:
            result_data["copr_projects"].append({
                "owner": proj.owner,
                "name": proj.name,
                "description": proj.description[:100],
            })
        if not use_json and copr_results:
            print(f"Found {len(copr_results)} Copr projects:")
            for proj in copr_results[:5]:
                print(f"  - {proj.owner}/{proj.name}: {proj.description[:60]}...")

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """list command implementation"""
    import json

    from copa.copr_backend import CoprBackend
    from copa.state import AppState

    copr = CoprBackend()
    state = AppState.load()
    use_json = args.json if hasattr(args, 'json') else False

    result_data: dict[str, Any] = {
        "packages": [],
        "copr_repos": [],
        "obs_repos": [],
    }

    if args.packages:
        # List specified Copr 项目的包
        owner, project = args.packages.split("/", 1)
        if not use_json:
            print(f"Listing packages in {owner}/{project}:\n")

        packages = copr.list_packages(owner, project)
        for pkg in packages:
            result_data["packages"].append({
                "name": pkg.name,
                "latest_version": pkg.latest_version,
            })
            if not use_json:
                print(f"  {pkg.name}")
                if pkg.latest_version:
                    print(f"    Latest: {pkg.latest_version}")

        if not packages and not use_json:
            print("  No packages found or project does not exist")
            return 1
    else:
        # List enabled Copr 和 OBS 仓库
        if not use_json:
            print("Enabled third-party repos:\n")

        # 从状态文件读取
        for repo in state.copr_repos:
            status = "enabled" if repo.enabled_by_copa else "system"
            result_data["copr_repos"].append({
                "owner": repo.owner,
                "project": repo.project,
                "status": status,
                "installed_packages": repo.installed_packages,
            })
            if not use_json:
                print("Copr repos:")
                print(f"  - {repo.owner}/{repo.project} [{status}]")
                if repo.installed_packages:
                    print(f"    Packages: {', '.join(repo.installed_packages)}")

        for obs_repo in state.obs_repos:
            status = "enabled" if obs_repo.enabled_by_copa else "system"
            result_data["obs_repos"].append({
                "project": obs_repo.project,
                "status": status,
                "fedora_version": obs_repo.fedora_version,
                "installed_packages": obs_repo.installed_packages,
            })
            if not use_json:
                print("\nOBS repos:")
                print(f"  - {obs_repo.project} [{status}]")
                if obs_repo.installed_packages:
                    print(f"    Packages: {', '.join(obs_repo.installed_packages)}")

        if not state.copr_repos and not state.obs_repos and not use_json:
            print("  No third-party repos managed by copa")

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0


def cmd_repo(args: argparse.Namespace) -> int:
    """repo subcommand implementation - manage Copr and OBS repos"""
    from copa.dnf_backend import DnfBackend
    from copa.obs_backend import OBSBackend
    from copa.state import AppState

    dnf = DnfBackend()
    obs = OBSBackend()
    state = AppState.load()

    if not args.repo_command:
        print("Please specify a repo subcommand: list, enable, disable, remove")
        return 1

    if args.repo_command == "list":
        print("Third-party repos:\n")

        # Get enabled and all repos to distinguish status
        enabled_repos = dnf.get_enabled_repos()
        all_repos = dnf.repolist(enabled_only=False)
        enabled_ids = {r.id for r in dnf.repolist(enabled_only=True)}

        # Display Copr repos
        copr_enabled = enabled_repos.get("copr", [])
        copr_all = [r for r in all_repos if r.id.lower().startswith("copr:") or r.id.lower().startswith("coprdep:")]
        if copr_all or state.copr_repos:
            print("Copr repos:")
            # System Copr repos (including disabled)
            for repo in copr_all:
                parts = repo.id.split(":")
                if len(parts) >= 4:
                    owner = parts[2]
                    project = parts[3]
                    status = "enabled" if repo.id in enabled_ids else "disabled"
                    print(f"  copr:{owner}/{project} [{status}] [system]")
                else:
                    status = "enabled" if repo.id in enabled_ids else "disabled"
                    print(f"  copr:{repo.id} [{status}] [system]")

            # Copr repos managed by copa（不在系统列表中的）
            for repo in state.copr_repos:
                if f"copr:copr.fedorainfracloud.org:{repo.owner}:{repo.project}" not in {r.id for r in copr_all}:
                    print(f"  copr:{repo.owner}/{repo.project} [enabled] [copa]")
                    if repo.chroot:
                        print(f"    Chroot: {repo.chroot}")
                    if repo.installed_packages:
                        print(f"    Packages: {', '.join(repo.installed_packages)}")

        # Display OBS repos
        obs_all = [r for r in all_repos if r.id.lower().startswith("home_") or r.id.lower().startswith("home:")]
        if obs_all or state.obs_repos:
            print("\nOBS repos:")
            for repo in obs_all:
                status = "enabled" if repo.id in enabled_ids else "disabled"
                print(f"  obs:{repo.id} [{status}] [system]")

            for obs_repo in state.obs_repos:
                if f"obs:{obs_repo.project}" not in {r.id for r in obs_all}:
                    print(f"  obs:{obs_repo.project} [enabled] [copa]")
                    if obs_repo.fedora_version:
                        print(f"    Fedora: {obs_repo.fedora_version}")
                    if obs_repo.installed_packages:
                        print(f"    Packages: {', '.join(obs_repo.installed_packages)}")

        if not copr_all and not obs_all and not state.copr_repos and not state.obs_repos:
            print("  No third-party repos found")

        return 0

    # Parse repo argument: copr:owner/project or obs:project
    repo_arg = args.repo
    if repo_arg.startswith("copr:"):
        repo_type = "copr"
        repo_name = repo_arg[5:]
    elif repo_arg.startswith("obs:"):
        repo_type = "obs"
        repo_name = repo_arg[4:]
    else:
        print(f"{RED}Error: Invalid repo format. Use copr:owner/project or obs:project{RESET}")
        return 1

    if args.repo_command == "enable":
        if repo_type == "copr":
            chroot = args.chroot or dnf.get_chroot()
            print(f"Enabling Copr repo: {repo_name}")
            if dnf.copr_enable(repo_name, chroot):
                print("✓ Copr repo enabled")
                state.add_copr_repo(
                    owner=repo_name.split("/")[0],
                    project=repo_name.split("/")[1],
                    repo_id=f"copr:{repo_name}",
                    chroot=chroot,
                    enabled_by_copa=True,
                )
                state.save()
            else:
                print("✗ Failed to enable Copr repo")
                return 1
        else:  # obs
            print(f"Enabling OBS repo: {repo_name}")
            # OBS needs to download repo file
            fedora_version = dnf.get_fedora_version()
            repos = obs.find_fedora_repos(repo_name, fedora_version)
            if repos:
                best_repo = repos[0]
                if obs.download_repo_file(repo_name, best_repo.repository):
                    print("✓ OBS repo enabled (repo file downloaded)")
                    state.add_obs_repo(
                        project=repo_name,
                        repository=best_repo.repository,
                        repo_file_name=obs._get_repo_file_name(repo_name),
                        fedora_version=best_repo.fedora_version or "",
                        enabled_by_copa=True,
                    )
                    state.save()
                else:
                    print("✗ Failed to download OBS repo file")
                    return 1
            else:
                print(f"✗ No Fedora repos found for OBS project: {repo_name}")
                return 1

    elif args.repo_command == "disable":
        if repo_type == "copr":
            print(f"Disabling Copr repo: {repo_name}")
            if dnf.copr_disable(repo_name):
                print("✓ Copr repo disabled")
            else:
                print("✗ Failed to disable Copr repo")
                return 1
        else:  # obs
            print(f"Disabling OBS repo: {repo_name}")
            if obs.disable_repo(repo_name):
                print("✓ OBS repo disabled")
            else:
                print("✗ Failed to disable OBS repo")
                return 1

    elif args.repo_command == "remove":
        if repo_type == "copr":
            print(f"Removing Copr repo: {repo_name}")
            if dnf.copr_remove(repo_name):
                print("✓ Copr repo removed")
                owner, project = repo_name.split("/", 1)
                state.remove_copr_repo(owner, project)
                state.save()
            else:
                print("✗ Failed to remove Copr repo")
                return 1
        else:  # obs
            print(f"Removing OBS repo: {repo_name}")
            if obs.remove_repo_file(repo_name):
                dnf.makecache()
                print("✓ OBS repo removed")
                state.remove_obs_repo(repo_name)
                state.save()
            else:
                print("✗ Failed to remove OBS repo")
                return 1

    else:
        print("Please specify a repo subcommand: list, enable, disable, remove")
        return 1

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """doctor command implementation"""
    import subprocess
    from pathlib import Path

    from copa.utils import check_command_exists

    print("copa doctor - Check system environment\n")

    checks = []

    # Check dnf5
    dnf5_exists = check_command_exists("dnf5")
    dnf5_version = ""
    if dnf5_exists:
        try:
            result = subprocess.run(["dnf5", "--version"], capture_output=True, text=True)
            dnf5_version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else ""
        except Exception:
            pass
    checks.append(("dnf5", dnf5_exists, dnf5_version))

    # Check dnf（fallback）
    dnf_exists = check_command_exists("dnf")
    checks.append(("dnf", dnf_exists, "fallback"))

    # Check copr-cli
    copr_cli_exists = check_command_exists("copr-cli")
    copr_cli_version = ""
    if copr_cli_exists:
        try:
            result = subprocess.run(["copr-cli", "--version"], capture_output=True, text=True)
            copr_cli_version = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            pass
    checks.append(("copr-cli", copr_cli_exists, copr_cli_version))

    # Check python-copr
    copr_available = False
    try:
        import importlib.util
        copr_available = importlib.util.find_spec("copr.v3") is not None
    except Exception:
        pass
    checks.append(("python-copr", copr_available, ""))

    # Check Copr network connection
    copr_network_ok = False
    try:
        import httpx
        client = httpx.Client(timeout=10.0)
        response = client.head("https://copr.fedorainfracloud.org")
        copr_network_ok = response.status_code < 500
        client.close()
    except Exception:
        pass
    checks.append(("Copr API", copr_network_ok, "copr.fedorainfracloud.org"))

    # Check OBS auth and network connection
    obs_auth_exists = (Path.home() / ".config" / "osc" / "oscrc").exists()
    obs_network_ok = False
    if obs_auth_exists:
        try:
            import httpx
            client = httpx.Client(timeout=10.0)
            response = client.head("https://api.opensuse.org")
            obs_network_ok = response.status_code < 500
            client.close()
        except Exception:
            pass
    checks.append(("OBS auth", obs_auth_exists, "~/.config/osc/oscrc"))
    checks.append(("OBS API", obs_network_ok, "api.opensuse.org"))

    # Check if it is a rpm-ostree system
    is_ostree = False
    try:
        result = subprocess.run(
            ["rpm-ostree", "status"],
            capture_output=True,
            text=True
        )
        is_ostree = result.returncode == 0
    except Exception:
        pass
    if is_ostree:
        checks.append(("rpm-ostree", True, "Atomic system detected, not supported yet"))

    # Output results
    all_ok = True
    for name, ok, detail in checks:
        status = "✓" if ok else "✗"
        detail_str = f" ({detail})" if detail else ""
        print(f"  {status} {name}{detail_str}")
        if not ok and name not in ["dnf"]:
            all_ok = False

    print()
    if not dnf5_exists and not dnf_exists:
        print("Error: dnf5 or dnf not found, cannot continue")
        return 1

    if not copr_cli_exists:
        print("Warning: copr-cli not installed, Copr search will be unavailable")
        print("  Install: sudo dnf install copr-cli")

    if is_ostree:
        print("Warning: rpm-ostree system detected, copa does not support Atomic desktops yet")
        print("  Please use on traditional Fedora Workstation")

    if all_ok:
        print("All checks passed, system ready")
    else:
        print("Some checks failed, some features may be unavailable")

    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """audit command implementation"""
    from datetime import datetime

    from copa.copr_backend import CoprBackend
    from copa.dnf_backend import DnfBackend
    from copa.state import AppState

    dnf = DnfBackend()
    copr = CoprBackend()
    state = AppState.load()
    fedora_version = dnf.get_fedora_version()
    chroot = dnf.get_chroot()

    print("Auditing third-party repos...\n")

    issues = []

    # 审计 Copr 仓库
    if state.copr_repos:
        print("Copr repos:")
        for repo in state.copr_repos:
            print(f"  Checking {repo.owner}/{repo.project}...")

            # Check if project exists
            project_info = copr.get_project(repo.owner, repo.project)
            if not project_info:
                issues.append(f"Copr {repo.owner}/{repo.project}: Project not found or deleted")
                print("    WARNING: Project not found")
                continue

            # Check if current chroot is supported
            if chroot not in project_info.chroots:
                issues.append(f"Copr {repo.owner}/{repo.project}: Does not support {chroot}")
                print(f"    WARNING: Does not support current chroot ({chroot})")

            # Check latest build status
            builds = copr.get_builds(
                repo.owner, repo.project, limit=1
            )
            if builds:
                latest_build = builds[0]
                if latest_build.state != "succeeded":
                    issues.append(
                        f"Copr {repo.owner}/{repo.project}: "
                        f"Latest build {latest_build.state}"
                    )
                    print(
                        f"    WARNING: Latest build "
                        f"{latest_build.state}"
                    )

                # Check build time
                if latest_build.ended_on:
                    build_date = datetime.fromtimestamp(
                        latest_build.ended_on
                    )
                    days_ago = (
                        datetime.now() - build_date
                    ).days
                    if days_ago > 180:
                        issues.append(
                            f"Copr {repo.owner}/{repo.project}: "
                            f"Last build {days_ago} days ago"
                        )
                        print(
                            f"    WARNING: Last build was "
                            f"{days_ago} days ago"
                        )
            else:
                print("    No builds found")

            # Check risk words
            desc_lower = (project_info.description or "").lower()
            risk_words = ["testing", "experimental", "do not use", "mock only"]
            for word in risk_words:
                if word in desc_lower:
                    issues.append(f"Copr {repo.owner}/{repo.project}: Contains risk word '{word}'")
                    print(f"    WARNING: Contains risk word '{word}'")
                    break

        print()

    # Audit OBS repos
    if state.obs_repos:
        print("OBS repos:")
        for obs_repo in state.obs_repos:
            print(f"  Checking {obs_repo.project}...")

            # Check version match
            if (obs_repo.fedora_version
                    and obs_repo.fedora_version != str(fedora_version)):
                issues.append(
                    f"OBS {obs_repo.project}: "
                    f"Built for Fedora {obs_repo.fedora_version}, "
                    f"current is {fedora_version}"
                )
                print(
                    f"    WARNING: Version mismatch "
                    f"(Fedora {obs_repo.fedora_version} "
                    f"vs {fedora_version})"
                )

        print()

    # Output summary
    if issues:
        print(f"Found {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("No issues found. All repos look healthy.")

    return 0 if not issues else 1


def cmd_remove(args: argparse.Namespace) -> int:
    """remove command - uninstall a locally installed package"""
    from copa.dnf_backend import DnfBackend

    package = args.package
    dnf = DnfBackend()

    # Search installed packages matching input
    found = dnf.search_installed(package)
    if not found:
        print(f"Package '{package}' is not installed")
        return 1

    # Deduplicate by name
    seen: set[str] = set()
    unique: list[Any] = []
    for pkg in found:
        if pkg.name not in seen:
            seen.add(pkg.name)
            unique.append(pkg)

    if len(unique) == 1:
        pkg = unique[0]
        print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")
        if not args.assumeyes:
            from copa.utils import confirm
            if not confirm(f"{BOLD}\nRemove {pkg.name}?{RESET}", default=False):
                print("Cancelled")
                return 0
        print(f"Removing {pkg.name}...")
        if dnf.remove(pkg.name):
            print("Removed successfully")
        else:
            print("Remove failed")
            return 1
    else:
        print(f"Found {len(unique)} packages:")
        for i, pkg in enumerate(unique, 1):
            print(f"  [{i}] {pkg.name}-{pkg.evr} ({pkg.repo})")
            if pkg.summary:
                print(f"      {pkg.summary}")

        if args.assumeyes:
            target = unique[0]
            print(f"  Auto-selected: {target.name}")
        else:
            while True:
                choice = input(
                    f"{BOLD}\nSelect package to remove [1-{len(unique)}, q to cancel]: {RESET}"
                ).strip().lower()
                if choice in ("q", "quit"):
                    return 0
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(unique):
                        target = unique[idx - 1]
                        break
                except ValueError:
                    pass
                print("Invalid input, try again.")

            from copa.utils import confirm
            if not confirm(f"{BOLD}\nRemove {target.name}?{RESET}", default=False):
                print("Cancelled")
                return 0

        print(f"Removing {target.name}...")
        if dnf.remove(target.name):
            print("Removed successfully")
        else:
            print("Remove failed")
            return 1

    return 0


def cmd_repoquery(args: argparse.Namespace) -> int:
    """repoquery command implementation - query package dependencies"""
    import json

    from copa.dnf_backend import DnfBackend

    package = args.package
    dnf = DnfBackend()
    use_json = args.json if hasattr(args, 'json') else False

    result_data = {
        "package": package,
        "type": "unknown",
        "items": [],
    }

    if args.requires:
        # Query package dependencies
        result_data["type"] = "requires"
        result = dnf._run(["repoquery", "--requires", package])
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    result_data["items"].append(line.strip())
        if not use_json:
            print(f"Querying package: {package}\n")
            print("Dependencies:")
            for item in result_data["items"]:
                print(f"  {item}")
        if not result_data["items"]:
            if not use_json:
                print(f"  Package {package} not found or error querying")
            return 1
    elif args.provides:
        # Query what package provides
        result_data["type"] = "provides"
        result = dnf._run(["repoquery", "--provides", package])
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    result_data["items"].append(line.strip())
        if not use_json:
            print(f"Querying package: {package}\n")
            print("Provides:")
            for item in result_data["items"]:
                print(f"  {item}")
        if not result_data["items"]:
            if not use_json:
                print(f"  Package {package} not found or error querying")
            return 1
    elif args.files:
        # Query package files
        result_data["type"] = "files"
        result = dnf._run(["repoquery", "--list", package])
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    result_data["items"].append(line.strip())
        if not use_json:
            print(f"Querying package: {package}\n")
            print("Files:")
            for item in result_data["items"]:
                print(f"  {item}")
        if not result_data["items"]:
            if not use_json:
                print(f"  Package {package} not found or error querying")
            return 1
    else:
        # Display package info by default
        result_data["type"] = "info"
        result = dnf._run(["repoquery", "--info", package])
        if result.returncode == 0:
            result_data["info"] = result.stdout.strip()
            if not use_json:
                print(f"Querying package: {package}\n")
                print("Package info:")
                print(result.stdout)
        else:
            if not use_json:
                print(f"Querying package: {package}\n")
                print(f"  Package {package} not found")
            return 1

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0


def cmd_provides(args: argparse.Namespace) -> int:
    """provides command implementation - find packages providing a file"""
    import json

    from copa.dnf_backend import DnfBackend

    file_path = args.file
    dnf = DnfBackend()
    use_json = args.json if hasattr(args, 'json') else False

    result_data = {
        "file": file_path,
        "providers": [],
    }

    # Use dnf5 provides command
    result = dnf._run(["provides", file_path])

    if result.returncode == 0 and result.stdout.strip():
        # 解析输出
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                result_data["providers"].append(line.strip())
        if not use_json:
            print(f"Finding packages providing: {file_path}\n")
            print("Found in repositories:")
            print(result.stdout)
    else:
        if not use_json:
            print(f"Finding packages providing: {file_path}\n")
            print(f"No packages found providing {file_path}")
        return 1

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0


def main(argv: list[str] | None = None) -> int:
    """主入口"""
    import signal

    from copa.config import Config

    # Ctrl+C 中断处理
    def signal_handler(sig, frame):
        print(f"\n{YELLOW}Interrupted by user{RESET}")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)

    # 加载配置文件
    config = Config.load()

    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # 将配置传递给命令
    args.config = config

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
