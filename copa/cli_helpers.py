"""Helpers shared by the CLI command modules."""

from typing import Any

from copa.i18n import tr


def _parse_owner_project(value: str) -> tuple[str, str] | None:
    """Parse OWNER/PROJECT format safely."""
    if "/" not in value:
        return None
    owner, project = value.split("/", 1)
    if not owner or not project:
        return None
    return owner, project


def _obs_project_exists_in_system(project: str, repo_ids: set[str]) -> bool:
    """Check whether OBS project already exists in system repo ids."""
    normalized = project.replace(":", "_").replace("/", "_")
    return project in repo_ids or normalized in repo_ids


def _make_dnf(args: Any) -> Any:
    """Build a DnfBackend honoring backend configuration."""
    from copa.dnf_backend import DnfBackend

    return DnfBackend(
        prefer_dnf5=args.config.backend.prefer_dnf5,
        fallback_to_dnf=args.config.backend.fallback_to_dnf,
        assumeyes=getattr(args, "assumeyes", False),
    )


def _is_fedora(dnf: Any) -> bool:
    """Return whether the host is Fedora (older backends default to True)."""
    checker = getattr(dnf, "is_fedora", None)
    if not callable(checker):
        return True
    try:
        return bool(checker())
    except Exception:
        return True


def _search_local_repos(
    dnf: Any,
    keywords: list[str],
    enabled_repos: dict[str, list[str]],
    args: Any,
    config: Any,
    verbose: bool = False,
) -> list[tuple[str, Any]]:
    """Search Fedora/RPM Fusion/Terra repos for every keyword.

    Returns deduplicated ``(source, package)`` pairs. CLI flags
    (--official-only / --rpmfusion-only / --include-local-repo) take
    precedence over the corresponding config switches.
    """
    search_local = args.include_local_repo or args.official_only or args.rpmfusion_only
    if not search_local or args.copr_only or args.obs_only:
        return []

    sources: list[tuple[str, list[str]]] = []

    if not args.rpmfusion_only and (args.official_only or config.search.enable_fedora):
        sources.append(("Fedora", enabled_repos["fedora"]))

    if (
        not args.official_only
        and (args.rpmfusion_only or config.search.enable_rpmfusion)
        and enabled_repos["rpmfusion"]
    ):
        sources.append(("RPM Fusion", enabled_repos["rpmfusion"]))

    if (
        args.include_local_repo
        and not args.official_only
        and not args.rpmfusion_only
        and config.search.enable_terra_if_present
        and enabled_repos["terra"]
    ):
        sources.append(("Terra", enabled_repos["terra"]))

    results: list[tuple[str, Any]] = []
    for source, repo_ids in sources:
        if verbose:
            print(tr("Searching {source}...").format(source=source))
        for keyword in keywords:
            for pkg in dnf.search_in_repos(keyword, repo_ids):
                results.append((source, pkg))

    # Deduplicate by package name (first source wins)
    seen: set[str] = set()
    unique: list[tuple[str, Any]] = []
    for source, pkg in results:
        if pkg.name not in seen:
            seen.add(pkg.name)
            unique.append((source, pkg))
    return unique
