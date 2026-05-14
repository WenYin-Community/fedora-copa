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

    print(f"搜索: {keyword}\n")

    # 搜索 Fedora 官方源
    if not args.copr_only:
        print("搜索 Fedora 官方仓库...")
        fedora_results = dnf.search_in_repos(keyword, enabled_repos["fedora"])
        if fedora_results:
            print(f"  找到 {len(fedora_results)} 个结果:")
            for pkg in fedora_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 RPM Fusion
    if not args.official_only and not args.copr_only and enabled_repos["rpmfusion"]:
        print("搜索 RPM Fusion...")
        rpmfusion_results = dnf.search_in_repos(keyword, enabled_repos["rpmfusion"])
        if rpmfusion_results:
            print(f"  找到 {len(rpmfusion_results)} 个结果:")
            for pkg in rpmfusion_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 Terra
    if not args.official_only and not args.copr_only and enabled_repos["terra"]:
        print("搜索 Terra...")
        terra_results = dnf.search_in_repos(keyword, enabled_repos["terra"])
        if terra_results:
            print(f"  找到 {len(terra_results)} 个结果:")
            for pkg in terra_results[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()

    # 搜索 Copr
    if not args.official_only and not args.rpmfusion_only:
        print("搜索 Copr 仓库...")
        chroot = dnf.get_chroot()
        copr_results = engine.search_copr(keyword, chroot)
        if copr_results:
            print(f"  找到 {len(copr_results)} 个 Copr 项目:")
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
    from copa.utils import confirm, select_from_list

    package = args.package
    dnf = DnfBackend()
    copr = CoprBackend()
    obs = OBSBackend()
    engine = SearchEngine(dnf=dnf, copr=copr, obs=obs)
    state = AppState.load()

    # 获取已启用仓库
    enabled_repos = dnf.get_enabled_repos()
    fedora_version = dnf.get_fedora_version()

    print(f"安装: {package}\n")

    # Dry-run 模式
    if args.dry_run:
        print("[dry-run] 将执行以下操作:")
        print(f"  1. 搜索 Fedora/RPM Fusion/Terra/Copr/OBS 中的 {package}")
        print(f"  2. 找到后执行: sudo dnf5 install {package}")
        print(f"  3. 如果来自 Copr/OBS，询问是否保留仓库")
        return 0

    # 步骤 1-3: 搜索 Fedora/RPM Fusion/Terra
    if not args.copr_only and not args.obs_only:
        # 搜索 Fedora
        if not args.rpmfusion_only:
            print("搜索 Fedora 官方仓库...")
            fedora_results = dnf.search_in_repos(package, enabled_repos["fedora"])
            if fedora_results:
                print(f"\n在 Fedora 仓库中找到 {package}:")
                for pkg in fedora_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input("\n按回车从 Fedora 安装，输入 's' 继续搜索 [Install/search]: ").strip().lower()
                    if response != "s":
                        print(f"\n执行: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("安装成功!")
                        else:
                            print("安装失败")
                        return 0
                else:
                    print(f"\n执行: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("安装成功!")
                    else:
                        print("安装失败")
                    return 0

        # 搜索 RPM Fusion
        if not args.official_only and enabled_repos["rpmfusion"]:
            print("搜索 RPM Fusion...")
            rpmfusion_results = dnf.search_in_repos(package, enabled_repos["rpmfusion"])
            if rpmfusion_results:
                print(f"\n在 RPM Fusion 中找到 {package}:")
                for pkg in rpmfusion_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input("\n按回车从 RPM Fusion 安装，输入 's' 继续搜索 [Install/search]: ").strip().lower()
                    if response != "s":
                        print(f"\n执行: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("安装成功!")
                        else:
                            print("安装失败")
                        return 0
                else:
                    print(f"\n执行: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("安装成功!")
                    else:
                        print("安装失败")
                    return 0

        # 搜索 Terra
        if not args.official_only and enabled_repos["terra"]:
            print("搜索 Terra...")
            terra_results = dnf.search_in_repos(package, enabled_repos["terra"])
            if terra_results:
                print(f"\n在 Terra 中找到 {package}:")
                for pkg in terra_results[:3]:
                    print(f"  {pkg.name}-{pkg.evr} ({pkg.repo})")

                if not args.assumeyes:
                    response = input("\n按回车从 Terra 安装，输入 's' 继续搜索 [Install/search]: ").strip().lower()
                    if response != "s":
                        print(f"\n执行: sudo dnf5 install {package}")
                        if dnf.install(package):
                            print("安装成功!")
                        else:
                            print("安装失败")
                        return 0
                else:
                    print(f"\n执行: sudo dnf5 install {package}")
                    if dnf.install(package):
                        print("安装成功!")
                    else:
                        print("安装失败")
                    return 0

    # 步骤 4-12: 搜索 Copr
    if not args.official_only and not args.rpmfusion_only and not args.obs_only:
        print("搜索 Copr 仓库...")
        chroot = dnf.get_chroot()
        copr_results = engine.search_copr(package, chroot)

        if copr_results:
            print(f"\n找到 {len(copr_results)} 个 Copr 项目:")
            for i, result in enumerate(copr_results[:10], 1):
                chroot_status = "✓" if result.supports_chroot else "✗"
                print(f"  [{i}] {result.project.owner}/{result.project.name}")
                print(f"      {result.project.description[:50]}...")
                print(f"      Chroot: {chroot_status} | Risk: {result.risk_level}")

            # 用户选择
            if args.assumeyes and not args.copr:
                print("\n错误: 非交互模式下需要指定 --copr OWNER/PROJECT")
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
                    print(f"\n错误: 未找到 Copr 项目 {args.copr}")
                    return 1
            else:
                # 交互选择
                choice = input("\n选择 Copr 项目 [1-N, q 取消]: ").strip().lower()
                if choice in ("q", "quit"):
                    return 0
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(copr_results):
                        selected = copr_results[idx]
                    else:
                        print("无效选择")
                        return 1
                except ValueError:
                    print("无效输入")
                    return 1

            # 启用 Copr
            owner_project = f"{selected.project.owner}/{selected.project.name}"
            print(f"\n启用 Copr: {owner_project}")

            if not args.dry_run:
                if not dnf.copr_enable(owner_project, chroot):
                    print("启用 Copr 失败")
                    return 1

                # 刷新缓存
                print("刷新缓存...")
                dnf.makecache()

                # 安装
                print(f"安装 {package}...")
                if dnf.install(package):
                    print("安装成功!")

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
                        print(f"\n保留 Copr 仓库 {owner_project}?")
                        print("  [1] 保持启用")
                        print("  [2] 禁用仓库 [默认]")
                        print("  [3] 删除 repo 文件")
                        choice = input("选择 [1/2/3]: ").strip()

                        if choice == "1":
                            print("保持启用")
                        elif choice == "3":
                            print("删除 repo 文件...")
                            dnf.copr_remove(owner_project)
                            state.remove_copr_repo(selected.project.owner, selected.project.name)
                            state.save()
                        else:
                            print("禁用仓库...")
                            dnf.copr_disable(owner_project)
                else:
                    print("安装失败")
                    # 回滚: 禁用新启用的 Copr
                    print("回滚: 禁用 Copr 仓库...")
                    dnf.copr_disable(owner_project)
                    return 1
            else:
                print("[dry-run] 将执行:")
                print(f"  sudo dnf5 copr enable {owner_project} {chroot}")
                print(f"  sudo dnf5 makecache --refresh")
                print(f"  sudo dnf5 install {package}")

            return 0

    # 步骤 13-16: 搜索 OBS
    if not args.no_obs and not args.official_only and not args.rpmfusion_only and not args.copr_only:
        print("搜索 OBS 仓库...")
        obs_results = engine.search_obs(package, fedora_version)

        if obs_results:
            print(f"\n找到 {len(obs_results)} 个 OBS 项目:")
            for i, result in enumerate(obs_results[:5], 1):
                version_status = "✓" if result.has_current_version else "⚠ fallback"
                print(f"  [{i}] {result.package.project}/{result.package.name}")
                print(f"      {result.package.description[:50]}...")
                print(f"      Version: {version_status} | Risk: {result.risk_level}")

            # 用户选择
            choice = input("\n选择 OBS 项目 [1-N, q 取消]: ").strip().lower()
            if choice in ("q", "quit"):
                return 0

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(obs_results):
                    selected = obs_results[idx]
                else:
                    print("无效选择")
                    return 1
            except ValueError:
                print("无效输入")
                return 1

            # 版本 fallback 警告
            if not selected.has_current_version and selected.best_repo:
                print(f"\n⚠️  警告: 版本不匹配!")
                print(f"包: {package}")
                print(f"可用版本: Fedora {selected.best_repo.fedora_version}")
                print(f"你的系统: Fedora {fedora_version}")
                print("\n此包是为旧版 Fedora 构建的，可能存在依赖问题。")

                if not args.allow_obs_fallback:
                    if not confirm("继续安装?", default=False):
                        return 0

            # 下载 repo 文件
            if selected.best_repo:
                print(f"\n下载 repo 文件到 /etc/yum.repos.d/...")
                if not args.dry_run:
                    if obs.download_repo_file(selected.package.project, selected.best_repo.repository):
                        print("✓ Repo 文件已下载")

                        # 记录状态
                        state.add_obs_repo(
                            project=selected.package.project,
                            repository=selected.best_repo.repository,
                            repo_file_name=obs._get_repo_file_name(selected.package.project),
                            fedora_version=selected.best_repo.fedora_version or "",
                        )
                        state.save()

                        # 询问是否安装
                        print(f"\n将执行:")
                        print(f"  sudo dnf5 makecache --refresh")
                        print(f"  sudo dnf5 install {package}")

                        if args.assumeyes or confirm("\n按回车开始安装", default=True):
                            print("刷新缓存...")
                            dnf.makecache()

                            print(f"安装 {package}...")
                            if dnf.install(package):
                                print("安装成功!")

                                # 询问是否保留
                                print(f"\n保留 OBS 仓库 {selected.package.project}?")
                                print("  [1] 保持启用")
                                print("  [2] 禁用仓库 [默认]")
                                print("  [3] 删除 repo 文件")
                                choice = input("选择 [1/2/3]: ").strip()

                                if choice == "1":
                                    print("保持启用")
                                elif choice == "3":
                                    print("删除 repo 文件...")
                                    obs.remove_repo_file(selected.package.project)
                                    state.remove_obs_repo(selected.package.project)
                                    state.save()
                                else:
                                    print("禁用仓库...")
                                    obs.disable_repo(selected.package.project)
                            else:
                                print("安装失败")
                    else:
                        print("✗ 下载 repo 文件失败")
                        return 1
                else:
                    print("[dry-run] 将执行:")
                    print(f"  下载 repo 文件: {obs.get_repo_file_url(selected.package.project, selected.best_repo.repository)}")
                    print(f"  sudo dnf5 makecache --refresh")
                    print(f"  sudo dnf5 install {package}")

            return 0

    print(f"\n未找到 {package}")
    return 1


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
    from copa.utils import check_command_exists
    import subprocess

    print("copa doctor - 检查系统环境\n")

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
    checks.append(("网络连接", network_ok, "copr.fedorainfracloud.org"))

    # 检查是否为 rpm-ostree 系统
    is_ostree = False
    try:
        result = subprocess.run(["rpm-ostree", "status"], capture_output=True)
        is_ostree = result.returncode == 0
    except Exception:
        pass
    if is_ostree:
        checks.append(("rpm-ostree", True, "检测到 Atomic 系统，copa 暂不支持"))

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
        print("错误: 未找到 dnf5 或 dnf，无法继续")
        return 1

    if not copr_cli_exists:
        print("警告: copr-cli 未安装，Copr 搜索功能将不可用")
        print("  安装: sudo dnf install copr-cli")

    if is_ostree:
        print("警告: 检测到 rpm-ostree 系统，copa 当前不支持 Atomic 桌面")
        print("  请在传统 Fedora Workstation 上使用")

    if all_ok:
        print("所有检查通过，系统环境就绪")
    else:
        print("部分检查未通过，某些功能可能不可用")

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
