"""命令行入口"""

import argparse
import sys
from typing import Optional

from copa import __app_name__, __version__

# ANSI 颜色码
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BOLD = "\033[1m"
RESET = "\033[0m"


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="DNF5-style Fedora Copr Package Assistant",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="available commands")

    # search 命令
    search_parser = subparsers.add_parser("search", help="Search packages")
    search_parser.add_argument("keyword", nargs="+", help="Search keywords (AND logic)")
    search_parser.add_argument("--official-only", action="store_true", help="Search Fedora official repos only")
    search_parser.add_argument("--rpmfusion-only", action="store_true", help="Search RPM Fusion only")
    search_parser.add_argument("--copr-only", action="store_true", help="Search Copr only")
    search_parser.add_argument("--json", action="store_true", help="JSON output")

    # install 命令
    install_parser = subparsers.add_parser("install", help="Install package")
    install_parser.add_argument("package", help="Package name to install")
    install_parser.add_argument("--official-only", action="store_true", help="Install from Fedora official repos only")
    install_parser.add_argument("--rpmfusion-only", action="store_true", help="Install from RPM Fusion only")
    install_parser.add_argument("--copr-only", action="store_true", help="Install from Copr only")
    install_parser.add_argument("--copr", metavar="OWNER/PROJECT", help="Use specified Copr repo")
    install_parser.add_argument("--obs-only", action="store_true", help="Install from OBS only")
    install_parser.add_argument("--no-obs", action="store_true", help="Skip OBS search")
    install_parser.add_argument("--allow-obs-fallback", action="store_true", help="Allow OBS version fallback")
    install_parser.add_argument("--keep-copr", action="store_true", help="Keep Copr repo after install")
    install_parser.add_argument("--dry-run", action="store_true", help="Show operations without executing")
    install_parser.add_argument("-y", "--assumeyes", action="store_true", help="Auto confirm")

    # info 命令
    info_parser = subparsers.add_parser("info", help="Show package info")
    info_parser.add_argument("package", help="Package name or owner/project")

    # list 命令
    list_parser = subparsers.add_parser("list", help="List packages")
    list_parser.add_argument("--packages", metavar="OWNER/PROJECT", help="List packages in Copr project")

    # repo 子命令（统一管理 Copr 和 OBS 仓库）
    repo_parser = subparsers.add_parser("repo", help="Manage third-party repos (Copr/OBS)")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command")

    repo_subparsers.add_parser("list", help="List all third-party repos")

    repo_enable = repo_subparsers.add_parser("enable", help="Enable repo")
    repo_enable.add_argument("repo", help="Repo name: copr:owner/project or obs:project")
    repo_enable.add_argument("chroot", nargs="?", help="chroot for Copr (e.g. fedora-43-x86_64)")

    repo_disable = repo_subparsers.add_parser("disable", help="Disable repo")
    repo_disable.add_argument("repo", help="Repo name: copr:owner/project or obs:project")

    repo_remove = repo_subparsers.add_parser("remove", help="Remove repo")
    repo_remove.add_argument("repo", help="Repo name: copr:owner/project or obs:project")

    # doctor 命令
    subparsers.add_parser("doctor", help="Check system environment and dependencies")

    # audit 命令
    subparsers.add_parser("audit", help="Audit enabled Copr repos")

    return parser


def cmd_search(args: argparse.Namespace) -> int:
    """search 命令实现 - 支持多关键词 AND 逻辑"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.search import SearchEngine

    keywords = [k.lower() for k in args.keyword]
    search_query = " ".join(args.keyword)

    # 初始化后端
    dnf = DnfBackend()
    copr = CoprBackend()
    engine = SearchEngine(dnf=dnf, copr=copr)

    # 获取已启用仓库
    enabled_repos = dnf.get_enabled_repos()

    print(f"Searching: {search_query}\n")

    # 第三方源风险提示
    if not args.official_only:
        print(f"{RED}WARNING: Packages from sources other than Fedora official repos")
        print(f"  (RPM Fusion, Terra, Copr, OBS) are built by third parties.")
        print(f"  Please verify the risks before installation.{RESET}\n")

    # 搜索 Fedora 官方源
    if not args.copr_only:
        print("Searching Fedora official repos...")
        fedora_results = dnf.search_in_repos(search_query, enabled_repos["fedora"])
        # 客户端过滤：AND 逻辑
        fedora_results = _filter_by_keywords(fedora_results, keywords, match_desc=True)
        if fedora_results:
            print(f"  Found {len(fedora_results)} results:")
            for pkg in fedora_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 RPM Fusion
    if not args.official_only and not args.copr_only and enabled_repos["rpmfusion"]:
        print("Searching RPM Fusion...")
        rpmfusion_results = dnf.search_in_repos(search_query, enabled_repos["rpmfusion"])
        rpmfusion_results = _filter_by_keywords(rpmfusion_results, keywords, match_desc=True)
        if rpmfusion_results:
            print(f"  Found {len(rpmfusion_results)} results:")
            for pkg in rpmfusion_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 Terra
    if not args.official_only and not args.copr_only and enabled_repos["terra"]:
        print("Searching Terra...")
        terra_results = dnf.search_in_repos(search_query, enabled_repos["terra"])
        terra_results = _filter_by_keywords(terra_results, keywords, match_desc=True)
        if terra_results:
            print(f"  Found {len(terra_results)} results:")
            for pkg in terra_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 Copr
    if not args.official_only and not args.rpmfusion_only:
        print("Searching Copr repos...")
        chroot = dnf.get_chroot()
        copr_results = engine.search_copr(search_query, chroot)
        # 客户端过滤：AND 逻辑
        copr_results = _filter_copr_by_keywords(copr_results, keywords)
        if copr_results:
            print(f"  Found {len(copr_results)} Copr projects:")
            for i, result in enumerate(copr_results[:10], 1):
                chroot_status = "✓" if result.supports_chroot else "✗"
                print(f"    [{i}] {result.project.owner}/{result.project.name}")
                print(f"        {result.project.description[:60]}...")
                print(f"        Chroot: {chroot_status} | Risk: {result.risk_level}")
            print()

    return 0


def _filter_by_keywords(packages, keywords: list[str], match_desc: bool = True):
    """按关键词过滤包 - AND 逻辑"""
    def matches(pkg):
        name_lower = pkg.name.lower()
        desc_lower = pkg.summary.lower() if hasattr(pkg, 'summary') else ""
        for kw in keywords:
            name_match = kw in name_lower
            desc_match = match_desc and kw in desc_lower
            if not name_match and not desc_match:
                return False
        return True
    return [p for p in packages if matches(p)]


def _filter_copr_by_keywords(results, keywords: list[str]):
    """按关键词过滤 Copr 结果 - AND 逻辑"""
    def matches(result):
        name_lower = result.project.name.lower()
        owner_lower = result.project.owner.lower()
        desc_lower = result.project.description.lower()
        for kw in keywords:
            name_match = kw in name_lower
            owner_match = kw in owner_lower
            desc_match = kw in desc_lower
            if not name_match and not owner_match and not desc_match:
                return False
        return True
    return [r for r in results if matches(r)]


def cmd_install(args: argparse.Namespace) -> int:
    """install 命令实现"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.obs_backend import OBSBackend
    from copa.search import SearchEngine
    from copa.state import AppState
    from copa.utils import confirm

    package = args.package
    dnf = DnfBackend()
    copr = CoprBackend()
    obs = OBSBackend()
    engine = SearchEngine(dnf=dnf, copr=copr, obs=obs)
    state = AppState.load()

    # 获取已启用仓库
    enabled_repos = dnf.get_enabled_repos()
    fedora_version = dnf.get_fedora_version()

    print(f"Installing: {package}\n")

    # 第三方源风险提示
    if not args.official_only:
        print(f"{RED}WARNING: Packages from sources other than Fedora official repos")
        print(f"  (RPM Fusion, Terra, Copr, OBS) are built by third parties.")
        print(f"  Please verify the risks before installation.{RESET}\n")

    # Dry-run 模式
    if args.dry_run:
        print("[dry-run] Will execute:")
        print(f"  1. Search {package} in Fedora/RPM Fusion/Terra/Copr/OBS")
        print(f"  2. If found: sudo dnf5 install {package}")
        print(f"  3. If from Copr/OBS, ask whether to keep repo")
        return 0

    # 步骤 1-3: 搜索 Fedora/RPM Fusion/Terra
    if not args.copr_only and not args.obs_only:
        # 搜索 Fedora
        if not args.rpmfusion_only:
            print("Searching Fedora official repos...")
            fedora_results = dnf.search_in_repos(package, enabled_repos["fedora"])
            if fedora_results:
                print(f"\nFound {package} in Fedora repos:")
                for pkg in fedora_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input(f"{BOLD}\nPress Enter to install from Fedora, or 's' to continue searching [Install/search]: {RESET}").strip().lower()
                    if response != "s":
                        print(f"\nExecuting: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("Installation successful!")
                        else:
                            print("Installation failed")
                        return 0
                else:
                    print(f"\nExecuting: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("Installation successful!")
                    else:
                        print("Installation failed")
                    return 0

        # 搜索 RPM Fusion
        if not args.official_only and enabled_repos["rpmfusion"]:
            print("Searching RPM Fusion...")
            rpmfusion_results = dnf.search_in_repos(package, enabled_repos["rpmfusion"])
            if rpmfusion_results:
                print(f"\nFound {package} in RPM Fusion:")
                for pkg in rpmfusion_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input(f"{BOLD}\nPress Enter to install from RPM Fusion, or 's' to continue searching [Install/search]: {RESET}").strip().lower()
                    if response != "s":
                        print(f"\nExecuting: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("Installation successful!")
                        else:
                            print("Installation failed")
                        return 0
                else:
                    print(f"\nExecuting: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("Installation successful!")
                    else:
                        print("Installation failed")
                    return 0

        # 搜索 Terra
        if not args.official_only and enabled_repos["terra"]:
            print("Searching Terra...")
            terra_results = dnf.search_in_repos(package, enabled_repos["terra"])
            if terra_results:
                print(f"\nFound {package} in Terra:")
                for pkg in terra_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input(f"{BOLD}\nPress Enter to install from Terra, or 's' to continue searching [Install/search]: {RESET}").strip().lower()
                    if response != "s":
                        print(f"\nExecuting: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("Installation successful!")
                        else:
                            print("Installation failed")
                        return 0
                else:
                    print(f"\nExecuting: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("Installation successful!")
                    else:
                        print("Installation failed")
                    return 0

    # 步骤 4-16: 搜索 Copr 和 OBS（合并结果）
    if not args.official_only and not args.rpmfusion_only:
        chroot = dnf.get_chroot()
        all_sources = []  # 合并所有来源 [(source, data), ...]

        # 搜索 Copr
        if not args.obs_only:
            print("Searching Copr repos...")
            copr_results = engine.search_copr(package, chroot)
            for r in copr_results[:10]:
                all_sources.append(("copr", r))

        # 搜索 OBS
        if not args.no_obs and not args.copr_only:
            print("Searching OBS repos...")
            obs_results = engine.search_obs(package, fedora_version)
            for r in obs_results[:10]:
                all_sources.append(("obs", r))

        if all_sources:
            print(f"\nFound {len(all_sources)} packages from third-party repos:\n")

            # 统一展示列表
            for i, (source, data) in enumerate(all_sources, 1):
                if source == "copr":
                    chroot_status = "✓" if data.supports_chroot else "✗"
                    print(f"  [{i:2d}] [Copr] {data.project.owner}/{data.project.name}")
                    print(f"       {data.project.description[:50]}...")
                    print(f"       Chroot: {chroot_status} | Risk: {data.risk_level}")
                else:  # obs
                    version_status = "✓" if data.has_current_version else "⚠ fallback"
                    print(f"  [{i:2d}] [OBS]  {data.package.project}/{data.package.name}")
                    print(f"       {data.package.description[:50]}...")
                    print(f"       Version: {version_status} | Risk: {data.risk_level}")

            # 用户选择
            if args.assumeyes and not args.copr:
                print(f"\n{RED}Error: --copr OWNER/PROJECT required in non-interactive mode{RESET}")
                return 1

            if args.copr:
                # 使用指定的 Copr
                owner, project = args.copr.split("/", 1)
                selected = None
                selected_source = None
                for source, data in all_sources:
                    if source == "copr" and data.project.owner == owner and data.project.name == project:
                        selected = data
                        selected_source = "copr"
                        break
                if not selected:
                    print(f"\n{RED}Error: Copr project {args.copr} not found{RESET}")
                    return 1
            else:
                # 交互选择
                choice = input(f"{BOLD}\nSelect package [1-{len(all_sources)}, q to cancel]: {RESET}").strip().lower()
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

            # 根据来源执行安装
            if selected_source == "copr":
                return _install_from_copr(args, dnf, state, engine, package, selected, chroot)
            else:
                return _install_from_obs(args, dnf, obs, state, package, selected, fedora_version)

    print(f"\nPackage {package} not found")
    return 1


def _install_from_copr(args, dnf, state, engine, package, selected, chroot) -> int:
    """从 Copr 安装"""
    owner_project = f"{selected.project.owner}/{selected.project.name}"
    print(f"\nEnabling Copr: {owner_project}")

    if not args.dry_run:
        if not dnf.copr_enable(owner_project, chroot):
            print("Failed to enable Copr")
            return 1

        print("Refreshing cache...")
        dnf.makecache()

        print(f"Installing {package}...")
        if dnf.install(package):
            print("Installation successful!")

            state.add_copr_repo(
                owner=selected.project.owner,
                project=selected.project.name,
                repo_id=f"copr:{owner_project}",
                chroot=chroot,
            )
            state.save()

            if not args.keep_copr:
                print(f"{BOLD}\nKeep Copr repo {owner_project}?{RESET}")
                print("  [1] Keep enabled")
                print("  [2] Disable repo [default]")
                print("  [3] Remove repo file")
                choice = input(f"{BOLD}Select [1/2/3]: {RESET}").strip()

                if choice == "1":
                    print("Keeping enabled")
                elif choice == "3":
                    print("Removing repo file...")
                    dnf.copr_remove(owner_project)
                    state.remove_copr_repo(selected.project.owner, selected.project.name)
                    state.save()
                else:
                    print("Disabling repo...")
                    dnf.copr_disable(owner_project)
        else:
            print("Installation failed")
            print("Rollback: Disabling Copr repo...")
            dnf.copr_disable(owner_project)
            return 1
    else:
        print("[dry-run] Will execute:")
        print(f"  sudo dnf5 copr enable {owner_project} {chroot}")
        print(f"  sudo dnf5 makecache --refresh")
        print(f"  sudo dnf5 install {package}")

    return 0


def _install_from_obs(args, dnf, obs, state, package, selected, fedora_version) -> int:
    """从 OBS 安装"""
    # 版本 fallback 警告
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
        print(f"\nDownloading repo file to /etc/yum.repos.d/...")
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

                print(f"\nWill execute:")
                print(f"  sudo dnf5 makecache --refresh")
                print(f"  sudo dnf5 install {package}")

                from copa.utils import confirm
                if args.assumeyes or confirm(f"{BOLD}\nPress Enter to install{RESET}", default=True):
                    print("Refreshing cache...")
                    dnf.makecache()

                    print(f"Installing {package}...")
                    if dnf.install(package):
                        print("Installation successful!")

                        print(f"{BOLD}\nKeep OBS repo {selected.package.project}?{RESET}")
                        print("  [1] Keep enabled")
                        print("  [2] Disable repo [default]")
                        print("  [3] Remove repo file")
                        choice = input(f"{BOLD}Select [1/2/3]: {RESET}").strip()

                        if choice == "1":
                            print("Keeping enabled")
                        elif choice == "3":
                            print("Removing repo file...")
                            obs.remove_repo_file(selected.package.project)
                            state.remove_obs_repo(selected.package.project)
                            state.save()
                        else:
                            print("Disabling repo...")
                            obs.disable_repo(selected.package.project)
                    else:
                        print("Installation failed")
            else:
                print("✗ Failed to download repo file")
                return 1
        else:
            print("[dry-run] Will execute:")
            print(f"  Download repo: {obs.get_repo_file_url(selected.package.project, selected.best_repo.repository)}")
            print(f"  sudo dnf5 makecache --refresh")
            print(f"  sudo dnf5 install {package}")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """info 命令实现"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend

    package = args.package
    dnf = DnfBackend()
    copr = CoprBackend()

    print(f"Package: {package}\n")

    # 检查是否为 owner/project 格式
    if "/" in package:
        # Copr 项目详情
        owner, project = package.split("/", 1)
        print(f"Fetching Copr project info: {owner}/{project}")
        project_info = copr.get_project(owner, project)
        if project_info:
            print(f"  Name: {project_info.name}")
            print(f"  Owner: {project_info.owner}")
            print(f"  Description: {project_info.description[:200]}")
            print(f"  Supported chroots: {', '.join(project_info.chroots[:5])}")
            if project_info.instructions:
                print(f"  Instructions: {project_info.instructions[:200]}")
        else:
            print(f"  Project not found: {owner}/{project}")
            return 1
    else:
        # 软件包详情
        print("Searching in enabled repos...")
        enabled_repos = dnf.get_enabled_repos()
        all_repo_ids = (
            enabled_repos["fedora"]
            + enabled_repos["rpmfusion"]
            + enabled_repos["terra"]
        )

        if all_repo_ids:
            results = dnf.search_in_repos(package, all_repo_ids)
            if results:
                print(f"\nFound {len(results)} packages:")
                for pkg in results[:10]:
                    print(f"\n  {pkg.name}-{pkg.evr}")
                    print(f"    Arch: {pkg.arch}")
                    print(f"    Repo: {pkg.repo}")
                    print(f"    Summary: {pkg.summary}")
            else:
                print(f"\nPackage '{package}' not found in enabled repos")

        # 搜索 Copr
        print("\nSearching Copr projects...")
        chroot = dnf.get_chroot()
        copr_results = copr.search_projects(package)
        if copr_results:
            print(f"Found {len(copr_results)} Copr projects:")
            for proj in copr_results[:5]:
                print(f"  - {proj.owner}/{proj.name}: {proj.description[:60]}...")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """list 命令实现"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.state import AppState

    dnf = DnfBackend()
    copr = CoprBackend()
    state = AppState.load()

    if args.packages:
        # 列出指定 Copr 项目的包
        owner, project = args.packages.split("/", 1)
        print(f"Listing packages in {owner}/{project}:\n")

        packages = copr.list_packages(owner, project)
        if packages:
            for pkg in packages:
                print(f"  {pkg.name}")
                if pkg.latest_version:
                    print(f"    Latest: {pkg.latest_version}")
        else:
            print("  No packages found or project does not exist")
            return 1
    else:
        # 列出已启用的 Copr 和 OBS 仓库
        print("Enabled third-party repos:\n")

        # 从状态文件读取
        if state.copr_repos:
            print("Copr repos:")
            for repo in state.copr_repos:
                status = "enabled" if repo.enabled_by_copa else "system"
                print(f"  - {repo.owner}/{repo.project} [{status}]")
                if repo.installed_packages:
                    print(f"    Packages: {', '.join(repo.installed_packages)}")

        if state.obs_repos:
            print("\nOBS repos:")
            for repo in state.obs_repos:
                status = "enabled" if repo.enabled_by_copa else "system"
                print(f"  - {repo.project} [{status}]")
                if repo.installed_packages:
                    print(f"    Packages: {', '.join(repo.installed_packages)}")

        if not state.copr_repos and not state.obs_repos:
            print("  No third-party repos managed by copa")

    return 0


def cmd_repo(args: argparse.Namespace) -> int:
    """repo 子命令实现 - 管理 Copr 和 OBS 仓库"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.obs_backend import OBSBackend
    from copa.state import AppState

    dnf = DnfBackend()
    copr = CoprBackend()
    obs = OBSBackend()
    state = AppState.load()

    if not args.repo_command:
        print("Please specify a repo subcommand: list, enable, disable, remove")
        return 1

    if args.repo_command == "list":
        print("Third-party repos:\n")

        # 从系统检测已启用的仓库
        enabled_repos = dnf.get_enabled_repos()

        # 显示 Copr 仓库
        copr_repos = enabled_repos.get("copr", [])
        if copr_repos or state.copr_repos:
            print("Copr repos:")
            # 系统中的 Copr 仓库
            for repo_id in copr_repos:
                # 解析 repo_id: copr:copr.fedorainfracloud.org:owner:project
                parts = repo_id.split(":")
                if len(parts) >= 3:
                    owner = parts[2] if len(parts) > 2 else ""
                    project = parts[3] if len(parts) > 3 else ""
                    if owner and project:
                        print(f"  {owner}/{project} [system]")
                        continue
                print(f"  {repo_id} [system]")

            # copa 管理的 Copr 仓库
            for repo in state.copr_repos:
                if f"copr:{repo.owner}/{repo.project}" not in copr_repos:
                    status = "enabled" if repo.enabled_by_copa else "system"
                    print(f"  {repo.owner}/{repo.project} [{status}]")
                    if repo.chroot:
                        print(f"    Chroot: {repo.chroot}")
                    if repo.installed_packages:
                        print(f"    Packages: {', '.join(repo.installed_packages)}")

        # 显示 OBS 仓库
        obs_repos = enabled_repos.get("obs", [])
        if obs_repos or state.obs_repos:
            print("\nOBS repos:")
            # 系统中的 OBS 仓库
            for repo_id in obs_repos:
                print(f"  {repo_id} [system]")

            # copa 管理的 OBS 仓库
            for repo in state.obs_repos:
                if f"obs:{repo.project}" not in obs_repos:
                    status = "enabled" if repo.enabled_by_copa else "system"
                    print(f"  {repo.project} [{status}]")
                    if repo.fedora_version:
                        print(f"    Fedora: {repo.fedora_version}")
                    if repo.installed_packages:
                        print(f"    Packages: {', '.join(repo.installed_packages)}")

        if not copr_repos and not obs_repos and not state.copr_repos and not state.obs_repos:
            print("  No third-party repos found")

        return 0

    # 解析 repo 参数：copr:owner/project 或 obs:project
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
            # OBS 需要下载 repo 文件
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
    """doctor 命令实现"""
    from copa.utils import check_command_exists
    import subprocess

    print("copa doctor - Check system environment\n")

    checks = []

    # 检查 dnf5
    dnf5_exists = check_command_exists("dnf5")
    dnf5_version = ""
    if dnf5_exists:
        try:
            result = subprocess.run(["dnf5", "--version"], capture_output=True, text=True)
            dnf5_version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else ""
        except Exception:
            pass
    checks.append(("dnf5", dnf5_exists, dnf5_version))

    # 检查 dnf（fallback）
    dnf_exists = check_command_exists("dnf")
    checks.append(("dnf", dnf_exists, "fallback"))

    # 检查 copr-cli
    copr_cli_exists = check_command_exists("copr-cli")
    copr_cli_version = ""
    if copr_cli_exists:
        try:
            result = subprocess.run(["copr-cli", "--version"], capture_output=True, text=True)
            copr_cli_version = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            pass
    checks.append(("copr-cli", copr_cli_exists, copr_cli_version))

    # 检查 python3-libdnf5
    libdnf5_available = False
    try:
        import libdnf5
        libdnf5_available = True
    except ImportError:
        pass
    checks.append(("python3-libdnf5", libdnf5_available, ""))

    # 检查 python-copr
    copr_available = False
    try:
        from copr.v3 import Client
        copr_available = True
    except ImportError:
        pass
    checks.append(("python-copr", copr_available, ""))

    # 检查网络连接
    network_ok = False
    try:
        import httpx
        client = httpx.Client(timeout=5.0)
        response = client.head("https://copr.fedorainfracloud.org")
        network_ok = response.status_code < 500
    except Exception:
        pass
    checks.append(("Network", network_ok, "copr.fedorainfracloud.org"))

    # 检查是否为 rpm-ostree 系统
    is_ostree = False
    try:
        result = subprocess.run(["rpm-ostree", "status"], capture_output=True)
        is_ostree = result.returncode == 0
    except Exception:
        pass
    if is_ostree:
        checks.append(("rpm-ostree", True, "Atomic system detected, not supported yet"))

    # 输出结果
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
    """audit 命令实现"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.state import AppState
    from datetime import datetime

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

            # 检查项目是否存在
            project_info = copr.get_project(repo.owner, repo.project)
            if not project_info:
                issues.append(f"Copr {repo.owner}/{repo.project}: Project not found or deleted")
                print(f"    WARNING: Project not found")
                continue

            # 检查是否支持当前 chroot
            if chroot not in project_info.chroots:
                issues.append(f"Copr {repo.owner}/{repo.project}: Does not support {chroot}")
                print(f"    WARNING: Does not support current chroot ({chroot})")

            # 检查最近构建状态
            builds = copr.get_builds(repo.owner, repo.project, limit=1)
            if builds:
                latest_build = builds[0]
                if latest_build.state != "succeeded":
                    issues.append(f"Copr {repo.owner}/{repo.project}: Latest build {latest_build.state}")
                    print(f"    WARNING: Latest build {latest_build.state}")

                # 检查构建时间
                if latest_build.ended_on:
                    build_date = datetime.fromtimestamp(latest_build.ended_on)
                    days_ago = (datetime.now() - build_date).days
                    if days_ago > 180:
                        issues.append(f"Copr {repo.owner}/{repo.project}: Last build {days_ago} days ago")
                        print(f"    WARNING: Last build was {days_ago} days ago")
            else:
                print(f"    No builds found")

            # 检查风险词
            desc_lower = (project_info.description or "").lower()
            risk_words = ["testing", "experimental", "do not use", "mock only"]
            for word in risk_words:
                if word in desc_lower:
                    issues.append(f"Copr {repo.owner}/{repo.project}: Contains risk word '{word}'")
                    print(f"    WARNING: Contains risk word '{word}'")
                    break

        print()

    # 审计 OBS 仓库
    if state.obs_repos:
        print("OBS repos:")
        for repo in state.obs_repos:
            print(f"  Checking {repo.project}...")

            # 检查版本匹配
            if repo.fedora_version and repo.fedora_version != str(fedora_version):
                issues.append(f"OBS {repo.project}: Built for Fedora {repo.fedora_version}, current is {fedora_version}")
                print(f"    WARNING: Version mismatch (Fedora {repo.fedora_version} vs {fedora_version})")

        print()

    # 输出总结
    if issues:
        print(f"Found {len(issues)} issues:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("No issues found. All repos look healthy.")

    return 0 if not issues else 1


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
        "repo": cmd_repo,
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
