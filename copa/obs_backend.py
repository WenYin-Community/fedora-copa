"""OBS backend - handles interaction with openSUSE Build Service"""

import configparser
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

OBS_API_BASE = "https://api.opensuse.org"
OBS_REPO_DIR = Path("/etc/yum.repos.d")


def _xpath_string_literal(value: str) -> str:
    """Build safe XPath string literal for values containing quotes."""
    if "'" not in value:
        return f"'{value}'"
    parts = value.split("'")
    quoted_parts: list[str] = []
    for i, part in enumerate(parts):
        quoted_parts.append(f"'{part}'")
        if i < len(parts) - 1:
            quoted_parts.append('"\'"')
    return f"concat({', '.join(quoted_parts)})"


def extract_fedora_version(repo_name: str) -> str | None:
    """Extract Fedora version from repo name.

    Common formats: Fedora_43, Fedora_43_x86_64, fedora-43-x86_64
    """
    patterns = [
        r"[Ff]edora[_-](\d+)",
        r"[Ff]c(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, repo_name)
        if match:
            return match.group(1)
    return None


@dataclass
class OBSProject:
    """OBS project info"""
    name: str
    title: str
    description: str


@dataclass
class OBSPackage:
    """OBS package info"""
    name: str
    project: str
    title: str
    description: str


@dataclass
class OBSRepo:
    """OBS repo info"""
    project: str
    repository: str
    repo_url: str
    fedora_version: str | None
    is_current_version: bool
    version_gap: int  # Gap with current version
    repo_file_name: str = ""  # Local repo file name


class OBSBackend:
    """OBS backend wrapper"""

    def __init__(self, api_base: str = OBS_API_BASE):
        self.api_base = api_base
        self._auth = self._load_osc_auth()
        self._client: httpx.Client | None = None
        self._available: bool | None = None  # cached health check result

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialised httpx client."""
        if self._client is None:
            self._client = httpx.Client(
                headers={"Accept": "application/xml; charset=utf-8"},
                timeout=60.0,
                auth=self._auth,
            )
        return self._client

    @staticmethod
    def _load_osc_auth() -> httpx.BasicAuth | None:
        """Load credentials from ~/.config/osc/oscrc"""
        oscrc = Path.home() / ".config" / "osc" / "oscrc"
        if not oscrc.exists():
            return None
        try:
            cfg = configparser.ConfigParser()
            cfg.read(oscrc)
            for section in cfg.sections():
                if "api.opensuse.org" in section:
                    user = cfg.get(section, "user", fallback=None)
                    passwd = cfg.get(section, "pass", fallback=None)
                    if user and passwd:
                        return httpx.BasicAuth(user, passwd)
        except (OSError, configparser.Error):
            pass
        return None

    @property
    def has_auth(self) -> bool:
        """Whether OBS credentials are configured"""
        return self._auth is not None

    def is_available(self) -> bool:
        """Quick health check - result cached after first call"""
        if self._available is not None:
            return self._available
        if not self.has_auth:
            self._available = False
            return False
        try:
            resp = self.client.head(f"{self.api_base}/", timeout=10.0, follow_redirects=True)
            self._available = resp.status_code < 500
        except httpx.HTTPError:
            self._available = False
        return self._available

    def _get(
        self, path: str, params: dict[str, str] | None = None
    ) -> ET.Element:
        """Send GET request - no retry, fail fast"""
        url = f"{self.api_base}{path}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def search_projects(self, query: str, limit: int = 20) -> list[OBSProject]:
        """Search projects"""
        if not self.is_available():
            return []
        try:
            query_literal = _xpath_string_literal(query)
            root = self._get("/search/project", {"match": f"contains(@name,{query_literal})"})
            projects = []
            for project_elem in root.findall(".//project")[:limit]:
                name = project_elem.get("name", "")
                title = project_elem.findtext("title", "")
                description = project_elem.findtext("description", "")
                projects.append(OBSProject(
                    name=name,
                    title=title,
                    description=description,
                ))
            return projects
        except (httpx.HTTPError, ET.ParseError):
            return []

    def search_packages(self, query: str, limit: int = 20) -> list[OBSPackage]:
        """Search packages - substring match"""
        if not self.is_available():
            return []
        try:
            # Use contains() for substring matching
            query_literal = _xpath_string_literal(query)
            root = self._get("/search/package", {"match": f"contains(@name,{query_literal})"})
            packages = []
            for pkg_elem in root.findall(".//package")[:limit]:
                name = pkg_elem.get("name", "")
                project = pkg_elem.get("project", "")
                title = pkg_elem.findtext("title", "")
                description = pkg_elem.findtext("description", "")
                packages.append(OBSPackage(
                    name=name,
                    project=project,
                    title=title,
                    description=description,
                ))
            return packages
        except (httpx.HTTPError, ET.ParseError):
            return []

    def get_project_repos(self, project: str) -> list[OBSRepo]:
        """Get project repo list"""
        try:
            root = self._get(f"/source/{project}/_meta")
            repo_file_name = self._get_repo_file_name(project)
            repos = []
            for repo_elem in root.findall(".//repository"):
                repo_name = repo_elem.get("name", "")
                # Try to extract Fedora version from repo name
                fedora_version = extract_fedora_version(repo_name)
                repo_url = f"https://download.opensuse.org/repositories/{project}/{repo_name}"

                repos.append(OBSRepo(
                    project=project,
                    repository=repo_name,
                    repo_url=repo_url,
                    fedora_version=fedora_version,
                    is_current_version=False,  # Needs external determination
                    version_gap=0,  # Needs external calculation
                    repo_file_name=repo_file_name,
                ))
            return repos
        except (httpx.HTTPError, ET.ParseError):
            return []

    def _get_repo_file_name(self, project: str) -> str:
        """Generate repo file name (matches OBS download filename)"""
        return f"{project}.repo"

    def find_fedora_repos(
        self,
        project: str,
        current_fedora_version: int,
        max_fallback: int = 2,
    ) -> list[OBSRepo]:
        """Find Fedora repos with version fallback"""
        repos = self.get_project_repos(project)
        fedora_repos = []

        # Rawhide has no numeric version; treat the newest Fedora repo as
        # current and accept the rest without a version gap.
        if current_fedora_version == 0:
            versions = [
                int(r.fedora_version)
                for r in repos
                if r.fedora_version
            ]
            newest = max(versions) if versions else None
            for repo in repos:
                if repo.fedora_version:
                    repo.is_current_version = (
                        newest is not None and int(repo.fedora_version) == newest
                    )
                    repo.version_gap = 0
                    fedora_repos.append(repo)
            fedora_repos.sort(key=lambda r: not r.is_current_version)
            return fedora_repos

        for repo in repos:
            if repo.fedora_version:
                try:
                    version = int(repo.fedora_version)
                    gap = current_fedora_version - version
                    if 0 <= gap <= max_fallback:
                        repo.is_current_version = (gap == 0)
                        repo.version_gap = gap
                        fedora_repos.append(repo)
                except ValueError:
                    continue

        # Sort by version gap, prioritize current version
        fedora_repos.sort(key=lambda r: r.version_gap)
        return fedora_repos

    def get_repo_file_url(self, project: str, repository: str) -> str:
        """Get repo file download link"""
        return (
            f"https://download.opensuse.org/repositories/"
            f"{project}/{repository}/{project}.repo"
        )

    def download_repo_file(self, project: str, repository: str) -> bool:
        """Download repo file to /etc/yum.repos.d/"""
        repo_file_name = self._get_repo_file_name(project)
        repo_file_path = OBS_REPO_DIR / repo_file_name
        repo_file_url = self.get_repo_file_url(project, repository)

        try:
            result = subprocess.run(
                [
                    "sudo", "curl", "-sSfL",
                    "-o", str(repo_file_path),
                    repo_file_url
                ],
            )
            return result.returncode == 0
        except OSError:
            return False

    def disable_repo(self, project: str) -> bool:
        """Disable OBS repo"""
        repo_id = project.replace(":", "_").replace("/", "_")
        try:
            result = subprocess.run(
                [
                    "sudo", "dnf", "config-manager",
                    "--set-disabled", repo_id
                ],
            )
            return result.returncode == 0
        except OSError:
            return False

    def remove_repo_file(self, project: str) -> bool:
        """Delete OBS repo file"""
        # OBS repo files may use colons (home:user.repo) or underscores (home_user.repo)
        # depending on how they were added. Try both formats.
        paths = [
            OBS_REPO_DIR / self._get_repo_file_name(project),
        ]
        # If project has underscores, also try with colons (original OBS naming)
        if "_" in project:
            alt_name = project.replace("_", ":")
            paths.append(OBS_REPO_DIR / self._get_repo_file_name(alt_name))

        try:
            # rm -f succeeds even if file doesn't exist
            result = subprocess.run(
                ["sudo", "rm", "-f"] + [str(p) for p in paths],
            )
            return result.returncode == 0
        except OSError:
            return False

    def close(self) -> None:
        """Close client"""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OBSBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
