"""Environment, audit and package removal commands."""

import json
from typing import Any

from copa import utils
from copa.cli_helpers import _is_fedora, _make_dnf
from copa.i18n import tr
from copa.ui import BOLD, RESET


def cmd_doctor(args: Any) -> int:
    """doctor command implementation"""
    import importlib.util
    import os
    import subprocess
    from pathlib import Path

    from copa.utils import check_command_exists

    env = {**os.environ, "LANG": "C", "LC_ALL": "C"}

    use_json = getattr(args, "json", False)
    if not use_json:
        print(tr("copa doctor - Check system environment"))
        print()

    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "", required: bool = False) -> None:
        checks.append({
            "name": name,
            "ok": ok,
            "detail": detail,
            "required": required,
        })

    # Check dnf5
    dnf5_exists = check_command_exists("dnf5")
    dnf5_version = ""
    if dnf5_exists:
        try:
            result = subprocess.run(
                ["dnf5", "--version"], capture_output=True, text=True, env=env
            )
            dnf5_version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else ""
        except OSError:
            pass
    add("dnf5", dnf5_exists, dnf5_version)

    # Check dnf (fallback)
    dnf_exists = check_command_exists("dnf")
    add("dnf", dnf_exists, "fallback")

    # Check copr-cli (optional, publishing only)
    copr_cli_exists = check_command_exists("copr-cli")
    copr_cli_version = ""
    if copr_cli_exists:
        try:
            result = subprocess.run(
                ["copr-cli", "--version"], capture_output=True, text=True, env=env
            )
            copr_cli_version = result.stdout.strip() if result.returncode == 0 else ""
        except OSError:
            pass
    add("copr-cli", copr_cli_exists, copr_cli_version)

    # Check python-copr
    copr_available = False
    try:
        copr_available = importlib.util.find_spec("copr.v3") is not None
    except (ImportError, AttributeError, ValueError):
        pass
    add("python-copr", copr_available, required=True)

    # Check Copr network connection
    copr_network_ok = False
    try:
        import httpx
        client = httpx.Client(timeout=10.0)
        try:
            response = client.head(
                "https://copr.fedorainfracloud.org", follow_redirects=True
            )
            copr_network_ok = response.status_code < 500
        finally:
            client.close()
    except ImportError:
        pass
    except (OSError, httpx.HTTPError):
        pass
    add("Copr API", copr_network_ok, "copr.fedorainfracloud.org", required=True)

    # Check OBS auth and network connection (optional)
    obs_auth_exists = (Path.home() / ".config" / "osc" / "oscrc").exists()
    obs_network_ok = False
    if obs_auth_exists:
        try:
            import httpx
            client = httpx.Client(timeout=10.0)
            try:
                response = client.head(
                    "https://api.opensuse.org", follow_redirects=True
                )
                obs_network_ok = response.status_code < 500
            finally:
                client.close()
        except ImportError:
            pass
        except (OSError, httpx.HTTPError):
            pass
    add("OBS auth", obs_auth_exists, "~/.config/osc/oscrc")
    add("OBS API", obs_network_ok, "api.opensuse.org")

    # Check if it is a rpm-ostree system
    is_ostree = False
    try:
        result = subprocess.run(
            ["rpm-ostree", "status"],
            capture_output=True,
            text=True
        )
        is_ostree = result.returncode == 0
    except OSError:
        pass
    if is_ostree:
        add("rpm-ostree", True, "Atomic system detected, not supported yet")

    required_ok = all(c["ok"] for c in checks if c["required"])
    ready = required_ok and (dnf5_exists or dnf_exists)

    if use_json:
        print(json.dumps({
            "checks": checks,
            "ready": ready,
        }, indent=2, ensure_ascii=False))
        return 0 if ready else 1

    for check in checks:
        status = "✓" if check["ok"] else "✗"
        detail_str = f" ({tr(check['detail'])})" if check["detail"] else ""
        suffix = "" if check["required"] or check["ok"] else tr(" [optional]")
        print(f"  {status} {tr(check['name'])}{detail_str}{suffix}")

    print()
    if not dnf5_exists and not dnf_exists:
        print(tr("Error: dnf5 or dnf not found, cannot continue"))
        return 1

    if not copr_cli_exists:
        print(tr("Note: copr-cli not installed (only needed for publishing packages to Copr)"))
        print(tr(
            "  Copr search uses the python-copr API; "
            "enabling repos uses the dnf5 copr plugin"
        ))

    if is_ostree:
        print(tr("Warning: rpm-ostree system detected, copa does not support Atomic desktops yet"))
        print(tr("  Please use on traditional Fedora Workstation"))

    if ready:
        print(tr("All checks passed, system ready"))
    else:
        print(tr("Some required checks failed, some features may be unavailable"))

    return 0 if ready else 1


def cmd_audit(args: Any) -> int:
    """audit command implementation"""
    from datetime import datetime

    from copa.copr_backend import CoprBackend
    from copa.search import BLOCK_WORD_TESTING_ONLY, MEDIUM_WORDS
    from copa.state import AppState

    dnf = _make_dnf(args)
    copr = CoprBackend()
    state = AppState.load()
    fedora_version = dnf.get_fedora_version()
    chroot = dnf.get_chroot()
    use_json = getattr(args, "json", False)
    risk = args.config.risk

    block_words = [BLOCK_WORD_TESTING_ONLY]
    if risk.block_do_not_use:
        block_words.append("do not use")
    if risk.block_mock_only:
        block_words.append("mock only")
    medium_words = MEDIUM_WORDS if risk.warn_experimental else ()

    issues: list[str] = []
    issue_texts: list[str] = []
    copr_data: list[dict[str, Any]] = []
    obs_data: list[dict[str, Any]] = []

    def add_issue(key: str, **kwargs: object) -> str:
        """Record the English issue for JSON and its localized text."""
        english = key.format(**kwargs)
        issues.append(english)
        issue_texts.append(tr(key).format(**kwargs))
        return english

    if not use_json:
        print(tr("Auditing third-party repos..."))
        print()

    # Audit Copr repos
    if state.copr_repos and not use_json:
        print(tr("Copr repos:"))

    for repo in state.copr_repos:
        label = f"{repo.owner}/{repo.project}"
        if not use_json:
            print(tr("  Checking {repo}...").format(repo=label))

        project_info = copr.get_project(repo.owner, repo.project)
        if not project_info:
            add_issue(
                "Copr {repo}: Project not found or Copr API error", repo=label
            )
            copr_data.append({"repo": label, "status": "missing"})
            if not use_json:
                print(tr("    WARNING: Project not found or API error"))
            continue

        entry: dict[str, Any] = {"repo": label, "status": "ok", "warnings": []}

        # Check if current chroot is supported
        if chroot not in project_info.chroots:
            message = add_issue(
                "Copr {repo}: Does not support {chroot}",
                repo=label,
                chroot=chroot,
            )
            entry["warnings"].append(message)
            if not use_json:
                print(
                    tr("    WARNING: Does not support current chroot ({chroot})")
                    .format(chroot=chroot)
                )

        # Check latest build status
        builds = copr.get_builds(repo.owner, repo.project, limit=1)
        if builds:
            latest_build = builds[0]
            if latest_build.state != "succeeded":
                message = add_issue(
                    "Copr {repo}: Latest build {state}",
                    repo=label,
                    state=latest_build.state,
                )
                entry["warnings"].append(message)
                if not use_json:
                    print(
                        tr("    WARNING: Latest build {state}").format(
                            state=latest_build.state
                        )
                    )

            # Check build time
            if latest_build.ended_on:
                build_date = datetime.fromtimestamp(latest_build.ended_on)
                days_ago = (datetime.now() - build_date).days
                if days_ago > 180:
                    message = add_issue(
                        "Copr {repo}: Last build {days} days ago",
                        repo=label,
                        days=days_ago,
                    )
                    entry["warnings"].append(message)
                    if not use_json:
                        print(
                            tr("    WARNING: Last build was {days} days ago").format(
                                days=days_ago
                            )
                        )
        elif not use_json:
            print(tr("    No builds found"))

        # Check risk words (shared with search risk assessment)
        text = f"{project_info.description} {project_info.instructions}".lower()
        for word in tuple(block_words) + tuple(medium_words):
            if word in text:
                message = add_issue(
                    "Copr {repo}: Contains risk word '{word}'",
                    repo=label,
                    word=word,
                )
                entry["warnings"].append(message)
                if not use_json:
                    print(
                        tr("    WARNING: Contains risk word '{word}'").format(
                            word=word
                        )
                    )
                break

        copr_data.append(entry)

    if state.copr_repos and not use_json:
        print()

    # Audit OBS repos
    if state.obs_repos and not use_json:
        print(tr("OBS repos:"))

    for obs_repo in state.obs_repos:
        if not use_json:
            print(tr("  Checking {repo}...").format(repo=obs_repo.project))
        entry = {"repo": obs_repo.project, "status": "ok", "warnings": []}

        # Fedora version matching only applies on Fedora hosts.
        if (
            _is_fedora(dnf)
            and obs_repo.fedora_version
            and obs_repo.fedora_version != str(fedora_version)
        ):
            message = add_issue(
                "OBS {repo}: Built for Fedora {old}, current is {current}",
                repo=obs_repo.project,
                old=obs_repo.fedora_version,
                current=fedora_version,
            )
            entry["warnings"].append(message)
            if not use_json:
                print(
                    tr("    WARNING: Version mismatch (Fedora {old} vs {current})")
                    .format(old=obs_repo.fedora_version, current=fedora_version)
                )

        obs_data.append(entry)

    if state.obs_repos and not use_json:
        print()

    # Output summary
    if use_json:
        print(json.dumps({
            "issues": issues,
            "copr_repos": copr_data,
            "obs_repos": obs_data,
        }, indent=2, ensure_ascii=False))
    elif issues:
        print(tr("Found {count} issues:").format(count=len(issue_texts)))
        for i, issue in enumerate(issue_texts, 1):
            print(f"  {i}. {issue}")
    else:
        print(tr("No issues found. All repos look healthy."))

    return 0 if not issues else 1


def cmd_remove(args: Any) -> int:
    """remove command - uninstall a locally installed package"""
    package = args.package
    dnf = _make_dnf(args)

    # Search installed packages matching input
    found = dnf.search_installed(package)
    if not found:
        print(tr("Package '{package}' is not installed").format(package=package))
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
            if not utils.confirm(
                f"{BOLD}{tr('Remove {name}?').format(name=pkg.name)}{RESET}",
                default=False,
            ):
                print(tr("Cancelled"))
                return 0
        print(tr("Removing {name}...").format(name=pkg.name))
        if dnf.remove(pkg.name):
            print(tr("Removed successfully"))
            return 0
        print(tr("Remove failed"))
        return 1

    print(tr("Found {count} packages:").format(count=len(unique)))
    for i, pkg in enumerate(unique, 1):
        print(f"  [{i}] {pkg.name}-{pkg.evr} ({pkg.repo})")
        if pkg.summary:
            print(f"      {pkg.summary}")

    if args.assumeyes:
        target = unique[0]
        print(tr("  Auto-selected: {name}").format(name=target.name))
    else:
        while True:
            prompt = tr(
                "Select package to remove [1-{count}, q to cancel]: "
            ).format(count=len(unique))
            choice = utils.read_input(f"{BOLD}\n{prompt}{RESET}")
            if choice is None:
                print(tr("\nNo input, cancelled"))
                return 0
            choice = choice.strip().lower()
            if choice in utils.CANCEL_ANSWERS:
                return 0
            try:
                idx = int(choice)
                if 1 <= idx <= len(unique):
                    target = unique[idx - 1]
                    break
            except ValueError:
                pass
            print(tr("Invalid input, try again."))

        if not utils.confirm(
            f"{BOLD}{tr('Remove {name}?').format(name=target.name)}{RESET}",
            default=False,
        ):
            print(tr("Cancelled"))
            return 0

    print(tr("Removing {name}...").format(name=target.name))
    if dnf.remove(target.name):
        print(tr("Removed successfully"))
        return 0
    print(tr("Remove failed"))
    return 1
