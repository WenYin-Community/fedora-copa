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
    search_parser.add_argument("keyword", help="Search keyword")
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

    # copr 子命令
    copr_parser = subparsers.add_parser("copr", help="Manage Copr repos")
    copr_subparsers = copr_parser.add_subparsers(dest="copr_command")

    copr_subparsers.add_parser("list", help="List enabled Copr repos")

    copr_enable = copr_subparsers.add_parser("enable", help="Enable Copr repo")
    copr_enable.add_argument("repo", help="owner/project format repo name")
    copr_enable.add_argument("chroot", nargs="?", help="chroot (e.g. fedora-43-x86_64)")

    copr_disable = copr_subparsers.add_parser("disable", help="Disable Copr repo")
    copr_disable.add_argument("repo", help="owner/project format repo name")

    copr_remove = copr_subparsers.add_parser("remove", help="Remove Copr repo")
    copr_remove.add_argument("repo", help="owner/project format repo name")

    # doctor 命令
    subparsers.add_parser("doctor", help="Check system environment and dependencies")

    # audit 命令
    subparsers.add_parser("audit", help="Audit enabled Copr repos")

    return parser


def cmd_search(args: argparse.Namespace) -> int:
    """search 命令实现"""
    from copa.dnf_backend import DnfBackend
    from copa.copr_backend import CoprBackend
    from copa.search import SearchEngine

    keyword = args.keyword

    # 初始化后端
    dnf = DnfBackend()
    copr = CoprBackend()
    engine = SearchEngine(dnf=dnf, copr=copr)

    # 获取已启用仓库
    enabled_repos = dnf.get_enabled_repos()

    print(f"Searching: {keyword}\n")

    # 第三方源风险提示
    if not args.official_only:
        print(f"{RED}WARNING: Packages from sources other than Fedora official repos")
        print(f"  (RPM Fusion, Terra, Copr, OBS) are built by third parties.")
        print(f"  Please verify the risks before installation.{RESET}\n")

    # 搜索 Fedora 官方源
    if not args.copr_only:
        print("Searching Fedora official repos...")
        fedora_results = dnf.search_in_repos(keyword, enabled_repos["fedora"])
        if fedora_results:
            print(f"  Found {len(fedora_results)} results:")
            for pkg in fedora_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 RPM Fusion
    if not args.official_only and not args.copr_only and enabled_repos["rpmfusion"]:
        print("Searching RPM Fusion...")
        rpmfusion_results = dnf.search_in_repos(keyword, enabled_repos["rpmfusion"])
        if rpmfusion_results:
            print(f"  Found {len(rpmfusion_results)} results:")
            for pkg in rpmfusion_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 Terra
    if not args.official_only and not args.copr_only and enabled_repos["terra"]:
        print("Searching Terra...")
        terra_results = dnf.search_in_repos(keyword, enabled_repos["terra"])
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
        copr_results = engine.search_copr(keyword, chroot)
        if copr_results:
            print(f"  Found {len(copr_results)} Copr projects:")
            for i, result in enumerate(copr_results[:10], 1):
                chroot_status = "✓" if result.supports_chroot else "✗"
                print(f"    [{i}] {result.project.owner}/{result.project.name}")
                print(f"        {result.project.description[:60]}...")
                print(f"        Chroot: {chroot_status} | Risk: {result.risk_level}")
            print()

    return 0


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

    # 步骤 4-12: 搜索 Copr
    if not args.official_only and not args.rpmfusion_only and not args.obs_only:
        print("Searching Copr repos...")
        chroot = dnf.get_chroot()
        copr_results = engine.search_copr(package, chroot)

        if copr_results:
            print(f"\nFound {len(copr_results)} Copr projects:")
            for i, result in enumerate(copr_results[:10], 1):
                chroot_status = "✓" if result.supports_chroot else "✗"
                print(f"  [{i}] {result.project.owner}/{result.project.name}")
                print(f"      {result.project.description[:50]}...")
                print(f"      Chroot: {chroot_status} | Risk: {result.risk_level}")

            # 用户选择
            if args.assumeyes and not args.copr:
                print("\nError: --copr OWNER/PROJECT required in non-interactive mode")
                return 1

            if args.copr:
                # 使用指定的 Copr
                owner, project = args.copr.split("/", 1)
                selected = None
                for r in copr_results:
                    if r.project.owner == owner and r.project.name == project:
                        selected = r
                        break
                if not selected:
                    print(f"\nError: Copr project {args.copr} not found")
                    return 1
            else:
                # 交互选择
                choice = input(f"{BOLD}\nSelect Copr project [1-N, q to cancel]: {RESET}").strip().lower()
                if choice in ("q", "quit"):
                    return 0
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(copr_results):
                        selected = copr_results[idx]
                    else:
                        print("Invalid selection")
                        return 1
                except ValueError:
                    print("Invalid input")
                    return 1

            # 启用 Copr
            owner_project = f"{selected.project.owner}/{selected.project.name}"
            print(f"\nEnabling Copr: {owner_project}")

            if not args.dry_run:
                if not dnf.copr_enable(owner_project, chroot):
                    print("Failed to enable Copr")
                    return 1

                # 刷新缓存
                print("Refreshing cache...")
                dnf.makecache()

                # 安装
                print(f"Installing {package}...")
                if dnf.install(package):
                    print("Installation successful!")

                    # 记录状态
                    state.add_copr_repo(
                        owner=selected.project.owner,
                        project=selected.project.name,
                        repo_id=f"copr:{owner_project}",
                        chroot=chroot,
                    )
                    state.save()

                    # 询问是否保留
                    if not args.keep_copr:
                        print(f"{BOLD}\nKeep Copr repo {owner_project}?{RESET}")
                        print("  [1] Keep enabled")
                        print("  [2] Disable repo [default]")
                        print("  [3] Remove repo file")
                        choice = input(f"{BOLD}Select [1/2/3]: {RESET}").strip()
                else:
                    print("Installation failed")
                    # 回滚: 禁用新启用的 Copr
                    print("Rollback: Disabling Copr repo...")
                    dnf.copr_disable(owner_project)
                    return 1
            else:
                print("[dry-run] Will execute:")
                print(f"  sudo dnf5 copr enable {owner_project} {chroot}")
                print(f"  sudo dnf5 makecache --refresh")
                print(f"  sudo dnf5 install {package}")

            return 0

    # 步骤 13-16: 搜索 OBS
    if not args.no_obs and not args.official_only and not args.rpmfusion_only and not args.copr_only:
        print("Searching OBS repos...")
        obs_results = engine.search_obs(package, fedora_version)

        if obs_results:
            print(f"\nFound {len(obs_results)} OBS projects:")
            for i, result in enumerate(obs_results[:5], 1):
                version_status = "✓" if result.has_current_version else "⚠ fallback"
                print(f"  [{i}] {result.package.project}/{result.package.name}")
                print(f"      {result.package.description[:50]}...")
                print(f"      Version: {version_status} | Risk: {result.risk_level}")

            # 用户选择
            choice = input(f"{BOLD}\nSelect OBS project [1-N, q to cancel]: {RESET}").strip().lower()
            if choice in ("q", "quit"):
                return 0

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(obs_results):
                    selected = obs_results[idx]
                else:
                    print("Invalid selection")
                    return 1
            except ValueError:
                print("Invalid input")
                return 1

            # 版本 fallback 警告
            if not selected.has_current_version and selected.best_repo:
                print(f"\n{RED}WARNING: Version mismatch!{RESET}")
                print(f"Package: {package}")
                print(f"Available for: Fedora {selected.best_repo.fedora_version}")
                print(f"Your system: Fedora {fedora_version}")
                print(f"{RED}This package was built for an older Fedora version.")
                print(f"It may have dependency issues or not work correctly.{RESET}")

                if not args.allow_obs_fallback:
                    if not confirm(f"{BOLD}Continue anyway?{RESET}", default=False):
                        return 0

            # 下载 repo 文件
            if selected.best_repo:
                print(f"\nDownloading repo file to /etc/yum.repos.d/...")
                if not args.dry_run:
                    if obs.download_repo_file(selected.package.project, selected.best_repo.repository):
                        print("✓ Repo file downloaded")

                        # 记录状态
                        state.add_obs_repo(
                            project=selected.package.project,
                            repository=selected.best_repo.repository,
                            repo_file_name=obs._get_repo_file_name(selected.package.project),
                            fedora_version=selected.best_repo.fedora_version or "",
                        )
                        state.save()

                        # 询问是否安装
                        print(f"\nWill execute:")
                        print(f"  sudo dnf5 makecache --refresh")
                        print(f"  sudo dnf5 install {package}")

                        if args.assumeyes or confirm(f"{BOLD}\nPress Enter to install{RESET}", default=True):
                            print("Refreshing cache...")
                            dnf.makecache()

                            print(f"Installing {package}...")
                            if dnf.install(package):
                                print("Installation successful!")

                                # 询问是否保留
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

    print(f"\nPackage {package} not found")
    return 1


def cmd_info(args: argparse.Namespace) -> int:
    """info 命令实现"""
    print(f"Info: {args.package}")
    # TODO: 实现信息查询
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """list 命令实现"""
    if args.packages:
        print(f"Listing packages: {args.packages}")
    else:
        print("Listing all installed packages")
    # TODO: 实现列表逻辑
    return 0


def cmd_copr(args: argparse.Namespace) -> int:
    """copr 子命令实现"""
    if args.copr_command == "list":
        print("Listing Copr repos")
    elif args.copr_command == "enable":
        print(f"Enabling Copr: {args.repo}")
    elif args.copr_command == "disable":
        print(f"Disabling Copr: {args.repo}")
    elif args.copr_command == "remove":
        print(f"Removing Copr: {args.repo}")
    else:
        print("Please specify a copr subcommand")
        return 1
    # TODO: 实现 copr 管理逻辑
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
    print("Auditing Copr repos...")
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
