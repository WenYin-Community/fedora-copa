"""Package information command."""

import json
from typing import Any

from copa.cli_helpers import _make_dnf
from copa.i18n import tr


def cmd_info(args: Any) -> int:
    """info command implementation"""
    from copa.copr_backend import CoprBackend

    package = args.package
    use_json = args.json
    dnf = _make_dnf(args)
    copr = CoprBackend()

    result_data: dict[str, Any] = {
        "package": package,
        "type": "unknown",
        "repos": [],
        "copr_projects": [],
    }

    # Check if it is owner/project format
    if "/" in package:
        owner, project = package.split("/", 1)
        result_data["type"] = "copr_project"
        project_info = copr.get_project(owner, project)
        if not project_info:
            result_data["error"] = "Copr project not found: {project}".format(
                project=f"{owner}/{project}"
            )
            if use_json:
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(tr("Package: {package}").format(package=package))
                print()
                print(
                    tr("  Project not found: {project}").format(
                        project=f"{owner}/{project}"
                    )
                )
            return 1

        result_data["copr_projects"].append({
            "owner": project_info.owner,
            "name": project_info.name,
            "description": project_info.description,
            "chroots": project_info.chroots[:5],
        })
        if not use_json:
            print(tr("Package: {package}").format(package=package))
            print()
            print(
                tr("Fetching Copr project info: {project}").format(
                    project=f"{owner}/{project}"
                )
            )
            print(tr("  Name: {value}").format(value=project_info.name))
            print(tr("  Owner: {value}").format(value=project_info.owner))
            print(
                tr("  Description: {value}").format(
                    value=project_info.description[:200]
                )
            )
            print(
                tr("  Supported chroots: {value}").format(
                    value=', '.join(project_info.chroots[:5])
                )
            )
            if project_info.instructions:
                print(
                    tr("  Instructions: {value}").format(
                        value=project_info.instructions[:200]
                    )
                )
    else:
        # Package details
        result_data["type"] = "package"
        if not use_json:
            print(tr("Package: {package}").format(package=package))
            print()
            print(tr("Searching in enabled repos..."))

        enabled_repos = dnf.get_enabled_repos(
            terra_patterns=args.config.search.terra_repo_patterns
        )
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
                print()
                print(tr("Found {count} packages:").format(count=len(results)))
                for pkg in results[:10]:
                    print()
                    print(f"  {pkg.name}-{pkg.evr}")
                    print(tr("    Arch: {value}").format(value=pkg.arch))
                    print(tr("    Repo: {value}").format(value=pkg.repo))
                    print(tr("    Summary: {value}").format(value=pkg.summary))
            elif not use_json:
                print()
                print(
                    tr("Package '{package}' not found in enabled repos").format(
                        package=package
                    )
                )

        # Search Copr
        if not use_json:
            print()
            print(tr("Searching Copr projects..."))
        copr_results = copr.search_projects(package)
        for proj in copr_results[:5]:
            result_data["copr_projects"].append({
                "owner": proj.owner,
                "name": proj.name,
                "description": proj.description[:100],
            })
        if not use_json and copr_results:
            print(tr("Found {count} Copr projects:").format(count=len(copr_results)))
            for proj in copr_results[:5]:
                print(
                    tr("  - {project}: {description}...").format(
                        project=f"{proj.owner}/{proj.name}",
                        description=proj.description[:60],
                    )
                )

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0
