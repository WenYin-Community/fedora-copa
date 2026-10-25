"""Search command and result filters."""

import json
import re
from typing import Any

from copa.cli_helpers import _is_fedora, _make_dnf, _search_local_repos
from copa.i18n import tr
from copa.ui import RED, RESET, YELLOW


def _regex_seeds(patterns: list[Any]) -> list[str]:
    """Extract literal search seeds from regex patterns.

    The Copr/OBS/dnf APIs have no regex support, so we query each literal
    run and apply the original regex locally.
    """
    seeds: list[str] = []
    for pattern in patterns:
        for raw in re.findall(r"[A-Za-z0-9_+.-]{2,}", pattern.pattern):
            seed = raw.strip(".-")
            if len(seed) >= 2 and seed not in seeds:
                seeds.append(seed)
    return seeds[:8]


def _unique_copr_results(results: list[Any]) -> list[Any]:
    """Deduplicate Copr results by owner/project."""
    seen: set[tuple[str, str]] = set()
    unique: list[Any] = []
    for result in results:
        key = (result.project.owner, result.project.name)
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


def _unique_obs_results(results: list[Any]) -> list[Any]:
    """Deduplicate OBS results by project/package."""
    seen: set[tuple[str, str]] = set()
    unique: list[Any] = []
    for result in results:
        key = (result.package.project, result.package.name)
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


def _search_copr_terms(
    engine: Any, terms: list[str], chroot: str, fedora_version: int
) -> list[Any]:
    """Search Copr for every term and merge the results."""
    results: list[Any] = []
    for term in terms:
        results.extend(engine.search_copr(term, chroot, fedora_version))
    return _unique_copr_results(results)


def _search_obs_terms(
    engine: Any, terms: list[str], fedora_version: int
) -> list[Any]:
    """Search OBS for every term and merge the results."""
    results: list[Any] = []
    for term in terms:
        results.extend(engine.search_obs(term, fedora_version))
    return _unique_obs_results(results)


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


def _filter_obs_by_keywords(
    results: list[Any], keywords: list[str]
) -> list[Any]:
    """Filter OBS results by keywords across package and project names."""
    def matches(result: Any) -> bool:
        name_lower = result.package.name.lower()
        project_lower = result.package.project.lower()
        for kw in keywords:
            if kw not in name_lower and kw not in project_lower:
                return False
        return True
    return [r for r in results if matches(r)]


def _filter_obs_by_regex(
    results: list[Any], patterns: list[Any]
) -> list[Any]:
    """Filter OBS results by regex - match package names only."""
    def matches(result: Any) -> bool:
        name = result.package.name
        for pattern in patterns:
            if not pattern.search(name):
                return False
        return True
    return [r for r in results if matches(r)]


def cmd_search(args: Any) -> int:
    """search command implementation - AND keywords and regex search"""
    from copa.copr_backend import CoprBackend
    from copa.search import SearchEngine

    keywords = [k.lower() for k in args.keyword]
    search_query = " ".join(args.keyword)
    use_json = args.json
    use_regex = args.regex
    if args.obs_only and args.no_obs:
        if not use_json:
            print(f"{RED}{tr('Error: --obs-only cannot be used with --no-obs')}{RESET}")
        return 1

    # Regex pattern validation
    regex_patterns = []
    if use_regex:
        for kw in args.keyword:
            try:
                regex_patterns.append(re.compile(kw, re.IGNORECASE))
            except re.error as e:
                if not use_json:
                    message = tr("Invalid regex '{pattern}': {error}").format(
                        pattern=kw, error=e
                    )
                    print(f"{RED}{message}{RESET}")
                return 1

    search_terms = _regex_seeds(regex_patterns) if use_regex else list(args.keyword)
    if use_regex and not search_terms:
        message_en = (
            "Regex search needs at least two literal characters "
            "(the backends cannot search expressions)"
        )
        message = tr(message_en)
        if use_json:
            print(json.dumps({"error": message_en}, indent=2))
        else:
            print(f"{RED}{tr('Error: {message}').format(message=message)}{RESET}")
        return 1

    # Initialize backends
    dnf = _make_dnf(args)
    copr = CoprBackend()
    engine = SearchEngine(dnf=dnf, copr=copr, risk=args.config.risk)

    # Get enabled repos
    enabled_repos = dnf.get_enabled_repos(
        terra_patterns=args.config.search.terra_repo_patterns
    )

    # Collect all results
    all_results: dict[str, Any] = {
        "query": search_query,
        "regex": use_regex,
        "fedora": [],
        "rpmfusion": [],
        "terra": [],
        "copr": [],
        "obs": [],
    }

    if not use_json:
        print(tr("Searching: {query}").format(query=search_query))
        if use_regex:
            print(f"{YELLOW}{tr('(regex mode - matching package names only)')}{RESET}")
        print()

        # Third-party source risk warning
        if not args.official_only:
            print(f"{RED}{tr('WARNING: Packages from sources other than Fedora official repos')}")
            print(tr("  (RPM Fusion, Terra, Copr, OBS) are built by third parties."))
            print(f"{tr('  Please verify the risks before installation.')}{RESET}\n")

    # Search Fedora official repos / RPM Fusion / Terra (local repos)
    local_results = _search_local_repos(
        dnf, search_terms, enabled_repos, args, args.config
    )
    for source_label, json_key in (
        ("Fedora", "fedora"),
        ("RPM Fusion", "rpmfusion"),
        ("Terra", "terra"),
    ):
        packages = [pkg for src, pkg in local_results if src == source_label]
        if use_regex:
            packages = _filter_by_regex(packages, regex_patterns)
        else:
            packages = _filter_by_keywords(packages, keywords, match_desc=False)
        if not packages:
            continue
        if not use_json:
            print(tr("Searching {source}...").format(source=source_label))
            print(tr("  Found {count} results:").format(count=len(packages)))
            for pkg in packages[:5]:
                print(f"    {pkg.name}-{pkg.evr} ({pkg.repo})")
                print(f"      {pkg.summary}")
            print()
        for pkg in packages[:10]:
            all_results[json_key].append({
                "name": pkg.name,
                "evr": pkg.evr,
                "arch": pkg.arch,
                "repo": pkg.repo,
                "summary": pkg.summary,
            })

    # Search Copr
    search_third_party = not args.official_only and not args.rpmfusion_only
    fedora_version = dnf.get_fedora_version() if search_third_party else 0
    if (
        search_third_party
        and not args.obs_only
        and (args.copr_only or args.config.search.enable_copr)
    ):
        if not use_json:
            print(tr("Searching Copr repos..."))
        chroot = dnf.get_chroot()
        if use_regex:
            copr_results = _search_copr_terms(
                engine, search_terms, chroot, fedora_version
            )
            copr_results = _filter_copr_by_regex(copr_results, regex_patterns)
        else:
            copr_results = engine.search_copr(
                search_query, chroot, fedora_version,
            )
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
            print(tr("  Found {count} Copr projects:").format(count=len(copr_results)))
            for i, result in enumerate(copr_results[:10], 1):
                if result.supports_chroot:
                    chroot_status = "✓"
                elif result.best_chroot:
                    chroot_status = tr("⚠ fallback ({chroot})").format(
                        chroot=result.best_chroot
                    )
                else:
                    chroot_status = "✗"
                print(f"    [{i}] {result.project.owner}/{result.project.name}")
                print(f"        {result.project.description[:60]}...")
                print(
                    tr("        Chroot: {status} | Risk: {risk}").format(
                        status=chroot_status, risk=tr(result.risk_level)
                    )
                )
            print()

    search_obs = args.obs_only or (
        search_third_party
        and not args.no_obs
        and not args.copr_only
    )
    if search_obs and not _is_fedora(dnf):
        if not use_json:
            print(
                f"{YELLOW}"
                f"{tr('OBS: Fedora repositories are not applicable on this system, skipping.')}"
                f"{RESET}"
            )
        search_obs = False
    if search_obs:
        if not engine.obs.is_available():
            if not use_json:
                print(f"{YELLOW}{tr('OBS is unavailable, skipping.')}{RESET}")
        else:
            if not use_json:
                print(tr("Searching OBS repos..."))
            if use_regex:
                obs_results = _search_obs_terms(engine, search_terms, fedora_version)
                obs_results = _filter_obs_by_regex(obs_results, regex_patterns)
            else:
                obs_results = engine.search_obs(search_query, fedora_version)
                obs_results = _filter_obs_by_keywords(obs_results, keywords)
            for obs_result in obs_results[:10]:
                all_results["obs"].append({
                    "project": obs_result.package.project,
                    "name": obs_result.package.name,
                    "description": obs_result.package.description[:100],
                    "has_current_version": obs_result.has_current_version,
                    "risk_level": obs_result.risk_level,
                })
            if not use_json and obs_results:
                print(tr("  Found {count} OBS packages:").format(count=len(obs_results)))
                for i, obs_result in enumerate(obs_results[:10], 1):
                    version_status = "✓" if obs_result.has_current_version else tr("⚠ fallback")
                    print(f"    [{i}] {obs_result.package.project}/{obs_result.package.name}")
                    print(f"        {obs_result.package.description[:60]}...")
                    print(
                        tr("        Version: {status} | Risk: {risk}").format(
                            status=version_status, risk=tr(obs_result.risk_level)
                        )
                    )
                print()

    # JSON output
    if use_json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
        return 0

    return 0
