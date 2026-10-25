"""Copr backend - handles interaction with Copr API and copr-cli"""

import sys
import threading
from dataclasses import dataclass
from typing import Any

from copr.v3 import Client
from copr.v3.exceptions import CoprAuthException, CoprException, CoprNoResultException

from copa.i18n import tr


def _warn_copr_api_error(exc: CoprException) -> None:
    """Print a warning for transient Copr API/network errors.

    HTTP 404 (CoprNoResultException) and 403 (CoprAuthException) are normal
    outcomes (project missing / auth rejected) and are swallowed silently.
    """
    if not isinstance(exc, (CoprNoResultException, CoprAuthException)):
        print(
            tr("  Warning: Copr API error: {error}").format(error=exc),
            file=sys.stderr,
        )


@dataclass
class CoprProject:
    """Copr project info"""
    owner: str
    name: str
    description: str
    chroots: list[str]
    instructions: str


@dataclass
class CoprPackage:
    """Copr package info"""
    name: str
    source_name: str


@dataclass
class CoprBuild:
    """Copr build info"""
    id: int
    state: str
    chroot: str
    started_on: int | None
    ended_on: int | None


class CoprBackend:
    """Copr backend wrapper"""

    def __init__(self):
        self.client = Client.create_from_config_file()

    def search_projects(
        self, query: str, limit: int = 20, timeout: float = 15.0
    ) -> list[CoprProject]:
        """Search Copr projects with a bounded wait.

        The public Copr search endpoint can take a very long time for broad
        terms, so the request runs in a daemon thread and is abandoned after
        ``timeout`` seconds.
        """
        outcome: dict[str, Any] = {}

        def run_search() -> None:
            try:
                outcome["projects"] = self.client.project_proxy.search(query)
            except Exception as exc:  # handled in the calling thread
                outcome["error"] = exc

        thread = threading.Thread(target=run_search, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            print(
                tr("  Warning: Copr search for '{query}' timed out after {timeout}s")
                .format(query=query, timeout=f"{timeout:g}"),
                file=sys.stderr,
            )
            return []

        error = outcome.get("error")
        if isinstance(error, CoprException):
            _warn_copr_api_error(error)
            return []
        if error is not None:
            raise error

        projects = outcome.get("projects") or []
        result = []
        for project in projects[:limit]:
            chroots = (
                list(project.chroot_repos.keys())
                if hasattr(project, 'chroot_repos')
                else []
            )
            result.append(CoprProject(
                owner=project.ownername,
                name=project.name,
                description=project.description or "",
                chroots=chroots,
                instructions=project.instructions or "",
            ))
        return result

    def get_project(self, owner: str, name: str) -> CoprProject | None:
        """Get project details"""
        try:
            project = self.client.project_proxy.get(owner, name)
            chroots = (
                list(project.chroot_repos.keys())
                if hasattr(project, 'chroot_repos')
                else []
            )
            return CoprProject(
                owner=project.ownername,
                name=project.name,
                description=project.description or "",
                chroots=chroots,
                instructions=project.instructions or "",
            )
        except CoprException as exc:
            _warn_copr_api_error(exc)
            return None

    def list_packages(self, owner: str, project: str) -> list[CoprPackage]:
        """List packages in project"""
        try:
            packages = self.client.package_proxy.get_list(owner, project)
            result = []
            for pkg in packages:
                result.append(CoprPackage(
                    name=pkg.name,
                    source_name=pkg.name,  # Usually the source package name
                ))
            return result
        except CoprException as exc:
            _warn_copr_api_error(exc)
            return []

    def get_builds(
        self,
        owner: str,
        project: str,
        package: str | None = None,
        limit: int = 10
    ) -> list[CoprBuild]:
        """Get build list"""
        try:
            kwargs: dict[str, Any] = {"pagination": {"limit": limit}}
            if package:
                kwargs["packagename"] = package
            builds = self.client.build_proxy.get_list(
                owner, project, **kwargs
            )
            result: list[CoprBuild] = []
            for build in builds:
                result.append(CoprBuild(
                    id=build.id,
                    state=build.state,
                    chroot=(
                        build.chroot
                        if hasattr(build, 'chroot')
                        else ""
                    ),
                    started_on=(
                        build.started_on
                        if hasattr(build, 'started_on')
                        else None
                    ),
                    ended_on=(
                        build.ended_on
                        if hasattr(build, 'ended_on')
                        else None
                    ),
                ))
            return result
        except CoprException as exc:
            _warn_copr_api_error(exc)
            return []

    def check_package_exists(
        self,
        owner: str,
        project: str,
        package_name: str
    ) -> bool:
        """Check if package exists in project"""
        try:
            self.client.package_proxy.get(owner, project, package_name)
            return True
        except CoprException as exc:
            _warn_copr_api_error(exc)
            return False
