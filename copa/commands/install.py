"""Install command and repository enablement flow."""

from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any

from copa import utils
from copa.cli_helpers import (
    _is_fedora,
    _make_dnf,
    _parse_owner_project,
    _search_local_repos,
)
from copa.i18n import tr
from copa.search import CoprSearchResult
from copa.ui import BOLD, RED, RESET, YELLOW


def _copr_repo_id(dnf: Any, owner: str, project: str) -> str:
    """Resolve the enabled Copr repo id, tolerating older/mock backends."""
    default = f"copr:copr.fedorainfracloud.org:{owner}:{project}"
    get_enabled = getattr(dnf, "get_enabled_repos", None)
    if not callable(get_enabled):
        return default
    try:
        enabled = get_enabled()
        repo_ids: list[str] = list(enabled.get("copr", []))
    except Exception:
        return default
    for repo_id in repo_ids:
        if repo_id.endswith(f":{owner}:{project}") or repo_id == f"copr:{owner}/{project}":
            return str(repo_id)
    return default


def _record_installed(state: Any, kind: str, owner: str, project: str, package: str) -> None:
    """Record a successfully installed package on the matching repo state."""
    if kind == "copr":
        getter = getattr(state, "get_copr_repo", None)
        repo_state = getter(owner, project) if callable(getter) else None
    else:
        getter = getattr(state, "get_obs_repo", None)
        repo_state = getter(project) if callable(getter) else None
    if repo_state is not None and package not in repo_state.installed_packages:
        repo_state.installed_packages.append(package)


def _set_enabled(state: Any, kind: str, owner: str, project: str, enabled: bool) -> None:
    """Update the enabled flag and persist the state if supported."""
    setter_name = "set_copr_enabled" if kind == "copr" else "set_obs_enabled"
    setter = getattr(state, setter_name, None)
    if callable(setter):
        if kind == "copr":
            changed = setter(owner, project, enabled)
        else:
            changed = setter(project, enabled)
        if changed:
            state.save()


def cmd_install(args: Any) -> int:
    """install command implementation"""
    from copa.copr_backend import CoprBackend
    from copa.obs_backend import OBSBackend
    from copa.search import SearchEngine
    from copa.state import AppState

    package = args.package
    if getattr(args, "obs_only", False) and getattr(args, "no_obs", False):
        print(f"{RED}{tr('Error: --obs-only cannot be used with --no-obs')}{RESET}")
        return 1
    if args.copr and (args.official_only or args.rpmfusion_only or args.obs_only):
        message = tr(
            "Error: --copr cannot be combined with "
            "--official-only/--rpmfusion-only/--obs-only"
        )
        print(f"{RED}{message}{RESET}")
        return 1

    dnf = _make_dnf(args)
    copr = CoprBackend()
    with OBSBackend(dnf_binary=dnf.binary) as obs:
        engine = SearchEngine(dnf=dnf, copr=copr, obs=obs, risk=args.config.risk)
        state = AppState.load()

        # Get enabled repos
        enabled_repos = dnf.get_enabled_repos(
            terra_patterns=args.config.search.terra_repo_patterns
        )
        fedora_version = dnf.get_fedora_version()

        print(tr("Installing: {package}").format(package=package))
        print()

        # Third-party source risk warning
        if not args.official_only:
            print(f"{RED}{tr('WARNING: Packages from sources other than Fedora official repos')}")
            print(tr("  (RPM Fusion, Terra, Copr, OBS) are built by third parties."))
            print(f"{tr('  Please verify the risks before installation.')}{RESET}\n")

        # Dry-run mode
        if args.dry_run:
            print(tr("[dry-run] Will execute:"))
            if args.copr:
                print(tr("  1. Use Copr project: {project}").format(project=args.copr))
            else:
                print(tr("  1. Search {package} in Copr/OBS").format(package=package))
            if args.include_local_repo and not args.copr:
                print(tr("     Also search: Fedora/RPM Fusion/Terra"))
            print(
                tr("  2. If found: sudo {binary} install {package}").format(
                    binary=dnf.binary, package=package
                )
            )
            print(tr("  3. If from Copr/OBS, ask whether to keep repo"))
            return 0

        # An explicit --copr selection bypasses keyword search entirely.
        if args.copr:
            return _install_from_copr_spec(
                args, dnf, copr, engine, state, package, fedora_version
            )

        can_search_third_party = (
            not args.official_only and not args.rpmfusion_only
        )

        # Steps 1-3: Search Fedora/RPM Fusion/Terra (only when explicitly requested)
        search_local = args.include_local_repo or args.official_only or args.rpmfusion_only
        if search_local and not args.copr_only and not args.obs_only:
            local_results = _search_local_repos(
                dnf, [package], enabled_repos, args, args.config, verbose=True
            )

            if local_results:
                print()
                print(
                    tr("Found {count} package(s) in local repos:").format(
                        count=len(local_results)
                    )
                )
                print()
                for i, (source, pkg) in enumerate(local_results, 1):
                    print(f"  [{i:2d}] {pkg.name}-{pkg.evr} ({source})")
                    if pkg.summary:
                        print(f"       {pkg.summary}")

                if args.assumeyes:
                    target_name = local_results[0][1].name
                    print()
                    print(tr("  Auto-selected: {name}").format(name=target_name))
                    print()
                    print(
                        tr("Executing: sudo {binary} install {name}").format(
                            binary=dnf.binary, name=target_name
                        )
                    )
                    if dnf.install(target_name):
                        print(tr("Installation successful!"))
                        return 0
                    print(tr("Installation failed"))
                    return 1

                if can_search_third_party:
                    prompt = tr(
                        "Select [1-{count}], 's' to search Copr/OBS, 'q' to cancel: "
                    ).format(count=len(local_results))
                else:
                    prompt = tr(
                        "Select [1-{count}], 'q' to cancel: "
                    ).format(count=len(local_results))
                choice = utils.read_input(f"{BOLD}\n{prompt}{RESET}")
                if choice is None:
                    print(tr("\nNo input, cancelled"))
                    return 0
                choice = choice.strip().lower()
                if choice in utils.CANCEL_ANSWERS:
                    return 0
                if choice in utils.SEARCH_ANSWERS:
                    if not can_search_third_party:
                        print(tr("Copr/OBS search is disabled by the selected source flags"))
                        return 1
                    # fall through to Copr/OBS search
                else:
                    try:
                        idx = int(choice)
                        if 1 <= idx <= len(local_results):
                            target_name = local_results[idx - 1][1].name
                            print()
                            print(
                                tr("Executing: sudo {binary} install {name}").format(
                                    binary=dnf.binary, name=target_name
                                )
                            )
                            if dnf.install(target_name):
                                print(tr("Installation successful!"))
                                return 0
                            print(tr("Installation failed"))
                            return 1
                    except ValueError:
                        pass
                    print(tr("Invalid input, continuing to Copr/OBS search..."))

        # Steps 4-16: Search Copr and OBS (merged results)
        if can_search_third_party:
            chroot = dnf.get_chroot()
            all_sources: list[tuple[str, Any]] = []
            blocked_projects: list[Any] = []

            # Search Copr and OBS in parallel
            search_copr = not args.obs_only and (
                args.copr_only or args.config.search.enable_copr
            )
            search_obs = not args.no_obs and not args.copr_only
            if search_obs and not _is_fedora(dnf):
                print(
                    f"{YELLOW}"
                    f"{tr('OBS: Fedora repositories are not applicable on this system, skipping.')}"
                    f"{RESET}"
                )
                search_obs = False

            # Check OBS auth before searching
            if search_obs and not obs.has_auth:
                print(f"{YELLOW}{tr('OBS: credentials not configured, skipping.')}{RESET}")
                print(tr("  Configure: osc config (set user/pass for api.opensuse.org)"))
                print()
                search_obs = False

            def collect(results: list[Any], source: str) -> None:
                added = 0
                for result in results:
                    if source == "copr" and getattr(result, "risk_level", "") == "blocked":
                        blocked_projects.append(result)
                        continue
                    if added >= 10:
                        break
                    all_sources.append((source, result))
                    added += 1

            if search_copr and search_obs:
                print(tr("Searching Copr and OBS repos..."))
                pool = ThreadPoolExecutor(max_workers=2)
                try:
                    future_copr = pool.submit(
                        engine.search_copr, package, chroot, fedora_version,
                    )
                    future_obs = pool.submit(engine.search_obs, package, fedora_version)
                    futures: list[Future[Any]] = [future_copr, future_obs]
                    done, pending = wait(futures, timeout=60)
                    for source, future in (("copr", future_copr), ("obs", future_obs)):
                        if future in done:
                            try:
                                results = future.result()
                            except Exception:
                                results = []
                            collect(results, source)
                    for future in pending:
                        future.cancel()
                        source_name = "Copr" if future is future_copr else "OBS"
                        message = tr(
                            "Warning: {source} search timed out (60s), "
                            "results may be incomplete"
                        ).format(source=source_name)
                        print(f"{YELLOW}{message}{RESET}")
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
            else:
                if search_copr:
                    print(tr("Searching Copr repos..."))
                    collect(engine.search_copr(package, chroot, fedora_version), "copr")
                if search_obs:
                    print(tr("Searching OBS repos..."))
                    collect(engine.search_obs(package, fedora_version), "obs")

            for result in blocked_projects:
                message = tr(
                    "Skipped blocked Copr project {project} ({risk})"
                ).format(
                    project=f"{result.project.owner}/{result.project.name}",
                    risk=tr(result.risk_level),
                )
                print(f"{YELLOW}{message}{RESET}")

            if all_sources:
                print()
                print(
                    tr("Found {count} packages from third-party repos:").format(
                        count=len(all_sources)
                    )
                )
                print()

                # Unified display list
                for i, (source, data) in enumerate(all_sources, 1):
                    if source == "copr":
                        if data.supports_chroot:
                            chroot_status = "✓"
                        elif data.best_chroot:
                            chroot_status = tr("⚠ fallback")
                        else:
                            chroot_status = "✗"
                        print(f"  [{i:2d}] [Copr] {data.project.owner}/{data.project.name}")
                        print(f"       {data.project.description[:50]}...")
                        print(
                            tr("       Chroot: {status} | Risk: {risk}").format(
                                status=chroot_status, risk=tr(data.risk_level)
                            )
                        )
                    else:  # obs
                        version_status = "✓" if data.has_current_version else tr("⚠ fallback")
                        print(f"  [{i:2d}] [OBS]  {data.package.project}/{data.package.name}")
                        print(f"       {data.package.description[:50]}...")
                        print(
                            tr("       Version: {status} | Risk: {risk}").format(
                                status=version_status, risk=tr(data.risk_level)
                            )
                        )

                # User selection
                selected_source: str | None = None
                selected: Any = None
                if args.assumeyes:
                    if len(all_sources) == 1:
                        selected_source, selected = all_sources[0]
                        if selected_source == "copr":
                            print()
                            print(
                                tr("  Auto-selected: [Copr] {project}").format(
                                    project=f"{selected.project.owner}/{selected.project.name}"
                                )
                            )
                        else:
                            print()
                            print(
                                tr("  Auto-selected: [OBS] {project}").format(
                                    project=f"{selected.package.project}/{selected.package.name}"
                                )
                            )
                    else:
                        print()
                        message = tr(
                            "Error: --copr OWNER/PROJECT required in "
                            "non-interactive mode (or narrow results to one)"
                        )
                        print(f"{RED}{message}{RESET}")
                        return 1
                else:
                    prompt = tr(
                        "Select package [1-{count}, q to cancel]: "
                    ).format(count=len(all_sources))
                    choice = utils.read_input(f"{BOLD}\n{prompt}{RESET}")
                    if choice is None:
                        print(tr("\nNo input, cancelled"))
                        return 0
                    choice = choice.strip().lower()
                    if choice in utils.CANCEL_ANSWERS:
                        return 0
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(all_sources):
                            selected_source, selected = all_sources[idx]
                        else:
                            print(tr("Invalid selection"))
                            return 1
                    except ValueError:
                        print(tr("Invalid input"))
                        return 1

                # Execute installation based on source
                if selected_source == "copr":
                    return _install_from_copr(
                        args, dnf, state, engine, package, selected, chroot
                    )
                return _install_from_obs(
                    args, dnf, obs, state, package, selected, fedora_version
                )

            if blocked_projects:
                print(tr("\nAll matching Copr projects were blocked by the risk policy."))
                return 1

        print(tr("\nPackage {package} not found").format(package=package))
        return 1


def _install_from_copr_spec(
    args: Any,
    dnf: Any,
    copr: Any,
    engine: Any,
    state: Any,
    package: str,
    fedora_version: int,
) -> int:
    """Install from an explicitly requested Copr project."""
    parsed = _parse_owner_project(args.copr)
    if not parsed:
        print(f"{RED}{tr('Error: Invalid --copr format, expected OWNER/PROJECT')}{RESET}")
        return 1
    owner, project = parsed
    project_info = copr.get_project(owner, project)
    if not project_info:
        print(
            f"{RED}"
            f"{tr('Error: Copr project {project} not found').format(project=args.copr)}"
            f"{RESET}"
        )
        return 1

    chroot = dnf.get_chroot()
    best_chroot, version_gap = engine._find_best_copr_chroot(
        project_info.chroots, chroot, fedora_version
    )
    selected = CoprSearchResult(
        project=project_info,
        risk_level=engine._assess_copr_risk(
            project_info, version_gap == 0, version_gap
        ),
        supports_chroot=version_gap == 0,
        best_chroot=best_chroot,
        version_gap=version_gap,
    )
    if selected.risk_level == "blocked":
        message = tr(
            "Error: Copr project {project} is blocked "
            "(risk policy or no compatible chroot)"
        ).format(project=args.copr)
        print(f"{RED}{message}{RESET}")
        return 1
    return _install_from_copr(
        args, dnf, state, engine, package, selected, chroot
    )


def _resolve_package_name(
    dnf: Any,
    package: str,
    repo_id: str,
    assumeyes: bool = False,
) -> str | None:
    """Search for actual package name in the repo, list for user selection."""
    found = dnf.search(package, repo=repo_id)

    if not found:
        print(tr("  No packages matching '{package}' found in repo").format(package=package))
        return None

    # Deduplicate
    seen: set[str] = set()
    unique: list[Any] = []
    for pkg in found:
        if pkg.name not in seen:
            seen.add(pkg.name)
            unique.append(pkg)

    # Always list for user selection
    print(tr("  Found {count} package(s):").format(count=len(unique)))
    for i, pkg in enumerate(unique, 1):
        print(f"    [{i}] {pkg.name}-{pkg.evr} ({pkg.repo})")
        if pkg.summary:
            print(f"        {pkg.summary}")

    if assumeyes:
        print(tr("  Auto-selected: {name}").format(name=unique[0].name))
        return str(unique[0].name)

    while True:
        prompt = tr("Select package [1-{count}]: ").format(count=len(unique))
        choice = utils.read_input(f"{BOLD}\n{prompt}{RESET}")
        if choice is None:
            print(tr("\nNo input, cancelled"))
            return None
        try:
            idx = int(choice.strip())
            if 1 <= idx <= len(unique):
                return str(unique[idx - 1].name)
        except ValueError:
            pass
        print(tr("Invalid input, try again."))


def _install_from_copr(
    args: Any,
    dnf: Any,
    state: Any,
    engine: Any,
    package: str,
    selected: Any,
    chroot: str,
) -> int:
    """Install from Copr"""
    owner = selected.project.owner
    project_name = selected.project.name
    owner_project = f"{owner}/{project_name}"
    repo_id = _copr_repo_id(dnf, owner, project_name)

    # Defensive enforcement of the risk policy.
    if getattr(selected, "risk_level", "low") == "blocked" or selected.version_gap < 0:
        message = tr(
            "Error: Copr project {project} is blocked "
            "(risk policy or no compatible chroot)"
        ).format(project=owner_project)
        print(f"{RED}{message}{RESET}")
        return 1

    # Determine chroot to use
    use_chroot = selected.best_chroot or chroot

    # Version fallback risk warning
    if selected.version_gap > 0:
        fedora_version = dnf.get_fedora_version()
        target_version = fedora_version - selected.version_gap
        print(f"\n{RED}{tr('WARNING: Version fallback!')}{RESET}")
        print(tr("Project: {project}").format(project=owner_project))
        print(
            tr("Current system: Fedora {version} ({chroot})").format(
                version=fedora_version, chroot=chroot
            )
        )
        print(
            tr("Fallback to: Fedora {version} ({chroot})").format(
                version=target_version, chroot=use_chroot
            )
        )
        print(f"{RED}{tr('This package was built for an older Fedora version.')}")
        print(f"{tr('It may have dependency issues or not work correctly.')}{RESET}")

        if not args.assumeyes:
            if not utils.confirm(f"{BOLD}{tr('Continue anyway?')}{RESET}", default=False):
                return 0

    print(
        tr("\nEnabling Copr: {project} ({chroot})").format(
            project=owner_project, chroot=use_chroot
        )
    )

    if not dnf.copr_enable(owner_project, use_chroot):
        print(tr("Failed to enable Copr"))
        return 1

    print(tr("Refreshing cache..."))
    dnf.makecache()

    # Search for actual package name in Copr repo
    print(
        tr("Searching for '{package}' in {project}...").format(
            package=package, project=owner_project
        )
    )
    install_name = _resolve_package_name(
        dnf, package, repo_id, args.assumeyes,
    )

    if not install_name:
        print(
            f"{RED}"
            f"{tr('No matching package found in {project}').format(project=owner_project)}"
            f"{RESET}"
        )
        print(f"  copa repo disable copr:{owner_project}")
        print(f"  copa repo remove copr:{owner_project}")
        return 1

    # Pre-install confirmation
    if not args.assumeyes:
        if not utils.confirm(
            f"{BOLD}{tr('Install {name}?').format(name=install_name)}{RESET}",
            default=True,
        ):
            print(tr("Cancelled, Copr repo kept enabled"))
            print(f"  copa repo disable copr:{owner_project}")
            print(f"  copa repo remove copr:{owner_project}")
            return 0

    print(tr("Installing {name}...").format(name=install_name))
    if not dnf.install(install_name):
        print(tr("Installation failed"))
        print(
            f"{YELLOW}"
            f"{tr('Copr repo {project} is kept enabled.').format(project=owner_project)}"
            f"{RESET}"
        )
        print(tr("You can disable or remove it:"))
        print(f"  copa repo disable copr:{owner_project}")
        print(f"  copa repo remove copr:{owner_project}")
        return 1

    print(tr("Installation successful!"))
    state.add_copr_repo(
        owner=owner,
        project=project_name,
        repo_id=repo_id,
        chroot=use_chroot,
    )
    _record_installed(state, "copr", owner, project_name, install_name)
    state.save()

    post_action = getattr(args.config, 'install', None)
    post_action = post_action.default_copr_post_action if post_action else "disable"
    if not args.keep_copr:
        if post_action == "keep":
            print(
                tr("\nCopr repo {project} kept enabled (config).").format(
                    project=owner_project
                )
            )
        elif post_action == "remove":
            print(
                tr("\nRemoving Copr repo {project} (config)...").format(
                    project=owner_project
                )
            )
            if dnf.copr_remove(owner_project):
                state.remove_copr_repo(owner, project_name)
                state.save()
            else:
                print(
                    f"{YELLOW}"
                    f"{tr('Failed to remove Copr repo; it remains enabled.')}"
                    f"{RESET}"
                )
        else:
            # "disable" (default) - ask user, or keep in non-interactive mode
            print()
            print(
                f"{BOLD}"
                f"{tr('Copr repo {project} is kept enabled.').format(project=owner_project)}"
                f"{RESET}"
            )
            print(f"{YELLOW}{tr('Note: This repo will participate in system updates.')}")
            hint = tr("If you don't want this, you can disable or remove it:")
            print(f"{hint}{RESET}")
            print(f"  copa repo disable copr:{owner_project}")
            print(f"  copa repo remove copr:{owner_project}")

            if args.assumeyes:
                print(tr("Keeping repo enabled (non-interactive mode)"))
            elif utils.confirm(
                f"{BOLD}{tr('Disable repo now?')}{RESET}", default=False
            ):
                print(tr("Disabling repo..."))
                if dnf.copr_disable(owner_project):
                    _set_enabled(state, "copr", owner, project_name, False)
                    print(tr("Repo disabled"))
                else:
                    print(
                        f"{YELLOW}"
                        f"{tr('Failed to disable Copr repo; it remains enabled.')}"
                        f"{RESET}"
                    )
            else:
                print(tr("Keeping repo enabled"))

    return 0


def _install_from_obs(
    args: Any,
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
        print(f"\n{RED}{tr('WARNING: Version mismatch!')}{RESET}")
        print(tr("Package: {package}").format(package=package))
        print(
            tr("Available for: Fedora {version}").format(
                version=selected.best_repo.fedora_version
            )
        )
        print(tr("Your system: Fedora {version}").format(version=fedora_version))
        print(f"{RED}{tr('This package was built for an older Fedora version.')}")
        print(f"{tr('It may have dependency issues or not work correctly.')}{RESET}")

        if not args.allow_obs_fallback:
            if not utils.confirm(f"{BOLD}{tr('Continue anyway?')}{RESET}", default=False):
                return 0

    if not selected.best_repo:
        return 0

    print(tr("\nDownloading repo file to /etc/yum.repos.d/..."))
    if not obs.download_repo_file(selected.package.project, selected.best_repo.repository):
        print(tr("✗ Failed to download repo file"))
        return 1

    print(tr("✓ Repo file downloaded"))
    state.add_obs_repo(
        project=selected.package.project,
        repository=selected.best_repo.repository,
        repo_file_name=obs._get_repo_file_name(selected.package.project),
        fedora_version=selected.best_repo.fedora_version or "",
    )
    state.save()

    print(tr("Refreshing cache..."))
    dnf.makecache()

    # Search for actual package name in OBS repo
    obs_repo_id = selected.package.project.replace(":", "_").replace("/", "_")
    print(
        tr("Searching for '{package}' in {project}...").format(
            package=package, project=obs_repo_id
        )
    )
    install_name = _resolve_package_name(
        dnf, package, obs_repo_id, args.assumeyes,
    )

    if not install_name:
        message = tr("No matching package found in {project}").format(
            project=selected.package.project
        )
        print(f"{RED}{message}{RESET}")
        print(f"  copa repo disable obs:{selected.package.project}")
        print(f"  copa repo remove obs:{selected.package.project}")
        return 1

    # Pre-install confirmation
    if not args.assumeyes:
        if not utils.confirm(
            f"{BOLD}{tr('Install {name}?').format(name=install_name)}{RESET}",
            default=True,
        ):
            print(tr("Cancelled, OBS repo kept enabled"))
            print(f"  copa repo disable obs:{selected.package.project}")
            print(f"  copa repo remove obs:{selected.package.project}")
            return 0

    print(tr("Installing {name}...").format(name=install_name))
    if not dnf.install(install_name):
        print(tr("Installation failed"))
        print(
            f"{YELLOW}"
            f"{tr('OBS repo {project} is kept enabled.').format(project=selected.package.project)}"
            f"{RESET}"
        )
        print(tr("You can disable or remove it:"))
        print(f"  copa repo disable obs:{selected.package.project}")
        print(f"  copa repo remove obs:{selected.package.project}")
        return 1

    print(tr("Installation successful!"))
    _record_installed(
        state, "obs", selected.package.project, selected.package.project, install_name
    )
    state.save()

    print()
    print(
        f"{BOLD}"
        f"{tr('OBS repo {project} is kept enabled.').format(project=selected.package.project)}"
        f"{RESET}"
    )
    print(f"{YELLOW}{tr('Note: This repo will participate in system updates.')}")
    hint = tr("If you don't want this, you can disable or remove it:")
    print(f"{hint}{RESET}")
    print(f"  copa repo disable obs:{selected.package.project}")
    print(f"  copa repo remove obs:{selected.package.project}")

    if args.assumeyes:
        print(tr("Keeping repo enabled (non-interactive mode)"))
    elif utils.confirm(f"{BOLD}{tr('Disable repo now?')}{RESET}", default=False):
        print(tr("Disabling repo..."))
        if obs.disable_repo(selected.package.project):
            _set_enabled(state, "obs", "", selected.package.project, False)
            print(tr("Repo disabled"))
        else:
            print(
                f"{YELLOW}"
                f"{tr('Failed to disable OBS repo; it remains enabled.')}"
                f"{RESET}"
            )
    else:
        print(tr("Keeping repo enabled"))

    return 0
