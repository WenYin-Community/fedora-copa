"""List command for copa-managed repositories."""

import json
from typing import Any

from copa.i18n import tr
from copa.ui import RED, RESET


def cmd_list(args: Any) -> int:
    """list command implementation"""
    from copa.copr_backend import CoprBackend
    from copa.state import AppState

    copr = CoprBackend()
    state = AppState.load()
    use_json = args.json

    result_data: dict[str, Any] = {
        "packages": [],
        "copr_repos": [],
        "obs_repos": [],
    }

    if args.packages:
        # List packages in specified Copr project
        if "/" not in args.packages:
            result_data["error"] = "Invalid format, expected OWNER/PROJECT"
            if use_json:
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(f"{RED}{tr('Error: Invalid format, expected OWNER/PROJECT')}{RESET}")
            return 1
        owner, project = args.packages.split("/", 1)
        if not owner or not project:
            result_data["error"] = "Invalid format, expected OWNER/PROJECT"
            if use_json:
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(f"{RED}{tr('Error: Invalid format, expected OWNER/PROJECT')}{RESET}")
            return 1
        if not use_json:
            print(tr("Listing packages in {owner}/{project}:").format(
                owner=owner, project=project
            ))
            print()

        packages = copr.list_packages(owner, project)
        for pkg in packages:
            result_data["packages"].append({
                "name": pkg.name,
            })
            if not use_json:
                print(f"  {pkg.name}")

        if not packages:
            result_data["error"] = "No packages found or project does not exist"
            if use_json:
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(tr("  No packages found or project does not exist"))
            return 1
    else:
        # List enabled Copr and OBS repos from the state file
        if not use_json:
            print(tr("Third-party repos managed by copa:"))
            print()

        for repo in state.copr_repos:
            status = "enabled" if repo.enabled_by_copa else "disabled"
            result_data["copr_repos"].append({
                "owner": repo.owner,
                "project": repo.project,
                "status": status,
                "installed_packages": repo.installed_packages,
            })

        for obs_repo in state.obs_repos:
            status = "enabled" if obs_repo.enabled_by_copa else "disabled"
            result_data["obs_repos"].append({
                "project": obs_repo.project,
                "status": status,
                "fedora_version": obs_repo.fedora_version,
                "installed_packages": obs_repo.installed_packages,
            })

        if not use_json:
            if state.copr_repos:
                print(tr("Copr repos:"))
                for repo in state.copr_repos:
                    status = "enabled" if repo.enabled_by_copa else "disabled"
                    print(
                        tr("  - {owner}/{project} [{status}]").format(
                            owner=repo.owner,
                            project=repo.project,
                            status=tr(status),
                        )
                    )
                    if repo.installed_packages:
                        print(tr("    Packages: {value}").format(
                            value=', '.join(repo.installed_packages)
                        ))

            if state.obs_repos:
                print()
                print(tr("OBS repos:"))
                for obs_repo in state.obs_repos:
                    status = "enabled" if obs_repo.enabled_by_copa else "disabled"
                    print(
                        tr("  - {project} [{status}]").format(
                            project=obs_repo.project,
                            status=tr(status),
                        )
                    )
                    if obs_repo.installed_packages:
                        print(tr("    Packages: {value}").format(
                            value=', '.join(obs_repo.installed_packages)
                        ))

            if not state.copr_repos and not state.obs_repos:
                print(tr("  No third-party repos managed by copa"))

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0
