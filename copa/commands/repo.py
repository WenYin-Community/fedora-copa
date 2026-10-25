"""Third-party repository management command."""

import json
from typing import Any

from copa.cli_helpers import (
    _is_fedora,
    _make_dnf,
    _obs_project_exists_in_system,
    _parse_owner_project,
)
from copa.i18n import tr
from copa.ui import RED, RESET


def _copr_owner_project(repo_id: str) -> tuple[str, str] | None:
    """Extract owner/project from a Copr repo id."""
    parts = repo_id.split(":")
    if len(parts) >= 4:
        return parts[2], parts[3]
    return None


def _repo_list(dnf: Any, obs: Any, state: Any, use_json: bool) -> int:
    """List all third-party repos (enabled, disabled and copa-managed)."""
    all_repos = dnf.repolist(enabled_only=False)
    enabled_ids = {r.id for r in dnf.repolist(enabled_only=True)}

    copr_all = [
        r for r in all_repos
        if r.id.lower().startswith("copr:") or r.id.lower().startswith("coprdep:")
    ]

    obs_ids: set[str] = set()
    try:
        obs_ids = obs.installed_repo_ids()
    except Exception:
        obs_ids = set()
    obs_all = [
        r for r in all_repos
        if r.id in obs_ids or r.id.lower().startswith(("home_", "home:"))
    ]

    data: dict[str, list[dict[str, str]]] = {"copr_repos": [], "obs_repos": []}
    copr_system_ids = {r.id for r in copr_all}

    for repo in copr_all:
        parsed = _copr_owner_project(repo.id)
        if parsed:
            owner, project = parsed
            label = f"copr:{owner}/{project}"
        else:
            owner, project = "", ""
            label = f"copr:{repo.id}"
        data["copr_repos"].append({
            "repo": label,
            "owner": owner,
            "project": project,
            "status": "enabled" if repo.id in enabled_ids else "disabled",
            "source": "system",
        })

    for copr_repo in state.copr_repos:
        if not any(
            repo_id.endswith(f":{copr_repo.owner}:{copr_repo.project}")
            for repo_id in copr_system_ids
        ):
            data["copr_repos"].append({
                "repo": f"copr:{copr_repo.owner}/{copr_repo.project}",
                "owner": copr_repo.owner,
                "project": copr_repo.project,
                "status": "enabled" if copr_repo.enabled_by_copa else "disabled",
                "source": "copa",
                "chroot": copr_repo.chroot,
                "packages": ", ".join(copr_repo.installed_packages),
            })

    for repo in obs_all:
        data["obs_repos"].append({
            "repo": f"obs:{repo.id}",
            "project": repo.id,
            "status": "enabled" if repo.id in enabled_ids else "disabled",
            "source": "system",
        })

    obs_system_ids = {r.id for r in obs_all}
    for obs_repo in state.obs_repos:
        if not _obs_project_exists_in_system(obs_repo.project, obs_system_ids):
            data["obs_repos"].append({
                "repo": f"obs:{obs_repo.project}",
                "project": obs_repo.project,
                "status": "enabled" if obs_repo.enabled_by_copa else "disabled",
                "source": "copa",
                "fedora_version": obs_repo.fedora_version,
                "packages": ", ".join(obs_repo.installed_packages),
            })

    if use_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(tr("Third-party repos:"))
    print()

    if data["copr_repos"]:
        print(tr("Copr repos:"))
        for entry in data["copr_repos"]:
            print(
                tr("  {repo} [{status}] [{source}]").format(
                    repo=entry['repo'],
                    status=tr(entry['status']),
                    source=tr(entry['source']),
                )
            )
            if entry.get("chroot"):
                print(tr("    Chroot: {value}").format(value=entry['chroot']))
            if entry.get("packages"):
                print(tr("    Packages: {value}").format(value=entry['packages']))

    if data["obs_repos"]:
        print()
        print(tr("OBS repos:"))
        for entry in data["obs_repos"]:
            print(
                tr("  {repo} [{status}] [{source}]").format(
                    repo=entry['repo'],
                    status=tr(entry['status']),
                    source=tr(entry['source']),
                )
            )
            if entry.get("fedora_version"):
                print(tr("    Fedora: {value}").format(value=entry['fedora_version']))
            if entry.get("packages"):
                print(tr("    Packages: {value}").format(value=entry['packages']))

    if not data["copr_repos"] and not data["obs_repos"]:
        print(tr("  No third-party repos found"))

    return 0


def cmd_repo(args: Any) -> int:
    """repo subcommand implementation - manage Copr and OBS repos"""
    from copa.obs_backend import OBSBackend
    from copa.state import AppState

    dnf = _make_dnf(args)
    use_json = getattr(args, "json", False)
    with OBSBackend(dnf_binary=dnf.binary) as obs:
        state = AppState.load()

        if not args.repo_command:
            print(tr("Please specify a repo subcommand: list, enable, disable, remove"))
            return 1

        if args.repo_command == "list":
            return _repo_list(dnf, obs, state, use_json)

        # Parse repo argument: copr:owner/project or obs:project
        repo_arg = args.repo
        if repo_arg.startswith("copr:"):
            repo_type = "copr"
            repo_name = repo_arg[5:]
        elif repo_arg.startswith("obs:"):
            repo_type = "obs"
            repo_name = repo_arg[4:]
        else:
            message = tr(
                "Error: Invalid repo format. "
                "Use copr:owner/project or obs:project"
            )
            print(f"{RED}{message}{RESET}")
            return 1

        if args.repo_command == "enable":
            if repo_type == "copr":
                parsed_repo = _parse_owner_project(repo_name)
                if not parsed_repo:
                    message = tr(
                        "Error: Invalid copr repo format, "
                        "expected owner/project"
                    )
                    print(f"{RED}{message}{RESET}")
                    return 1
                owner, project = parsed_repo
                chroot = args.chroot or dnf.get_chroot()
                print(tr("Enabling Copr repo: {repo}").format(repo=repo_name))
                if dnf.copr_enable(repo_name, chroot):
                    print(tr("✓ Copr repo enabled"))
                    state.add_copr_repo(
                        owner=owner,
                        project=project,
                        repo_id=f"copr:{repo_name}",
                        chroot=chroot,
                        enabled_by_copa=True,
                    )
                    state.save()
                else:
                    print(tr("✗ Failed to enable Copr repo"))
                    return 1
            else:  # obs
                if not _is_fedora(dnf):
                    print(tr("✗ OBS Fedora repositories are only supported on Fedora"))
                    return 1
                print(tr("Enabling OBS repo: {repo}").format(repo=repo_name))
                # OBS needs to download repo file
                fedora_version = dnf.get_fedora_version()
                repos = obs.find_fedora_repos(repo_name, fedora_version)
                if repos:
                    best_repo = repos[0]
                    if obs.download_repo_file(repo_name, best_repo.repository):
                        print(tr("✓ OBS repo enabled (repo file downloaded)"))
                        state.add_obs_repo(
                            project=repo_name,
                            repository=best_repo.repository,
                            repo_file_name=obs._get_repo_file_name(repo_name),
                            fedora_version=best_repo.fedora_version or "",
                            enabled_by_copa=True,
                        )
                        state.save()
                    else:
                        print(tr("✗ Failed to download OBS repo file"))
                        return 1
                else:
                    if not obs.has_auth:
                        print(tr("✗ OBS credentials are not configured (~/.config/osc/oscrc)"))
                    else:
                        print(
                            tr("✗ No Fedora repos found for OBS project: {repo}")
                            .format(repo=repo_name)
                        )
                    return 1

        elif args.repo_command == "disable":
            if repo_type == "copr":
                parsed_repo = _parse_owner_project(repo_name)
                print(tr("Disabling Copr repo: {repo}").format(repo=repo_name))
                if dnf.copr_disable(repo_name):
                    print(tr("✓ Copr repo disabled"))
                    if parsed_repo:
                        state.set_copr_enabled(
                            parsed_repo[0], parsed_repo[1], False
                        )
                        state.save()
                else:
                    print(tr("✗ Failed to disable Copr repo"))
                    return 1
            else:  # obs
                print(tr("Disabling OBS repo: {repo}").format(repo=repo_name))
                if obs.disable_repo(repo_name):
                    print(tr("✓ OBS repo disabled"))
                    state.set_obs_enabled(repo_name, False)
                    state.save()
                else:
                    print(tr("✗ Failed to disable OBS repo"))
                    return 1

        elif args.repo_command == "remove":
            if repo_type == "copr":
                parsed_repo = _parse_owner_project(repo_name)
                if not parsed_repo:
                    message = tr(
                        "Error: Invalid copr repo format, "
                        "expected owner/project"
                    )
                    print(f"{RED}{message}{RESET}")
                    return 1
                owner, project = parsed_repo
                print(tr("Removing Copr repo: {repo}").format(repo=repo_name))
                if dnf.copr_remove(repo_name):
                    print(tr("✓ Copr repo removed"))
                    state.remove_copr_repo(owner, project)
                    state.save()
                else:
                    print(tr("✗ Failed to remove Copr repo"))
                    return 1
            else:  # obs
                print(tr("Removing OBS repo: {repo}").format(repo=repo_name))
                if obs.remove_repo_file(repo_name):
                    dnf.makecache()
                    print(tr("✓ OBS repo removed"))
                    state.remove_obs_repo(repo_name)
                    state.save()
                else:
                    print(tr("✗ Failed to remove OBS repo"))
                    return 1

        else:
            print(tr("Please specify a repo subcommand: list, enable, disable, remove"))
            return 1

        return 0
