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
class OBSBinary:
    """OBS binary package info"""
    name: str
    project: str
    repository: str
    arch: str
    version: str
    release: str
    filename: str
    url: str


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
        self.client = httpx.Client(
            headers={"Accept": "application/xml; charset=utf-8"},
            timeout=60.0,
            auth=self._auth,
        )
        self._available: bool | None = None  # cached health check result

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

    def search_binaries(
        self,
        package_name: str,
        repository: str | None = None,
        limit: int = 20,
    ) -> list[OBSBinary]:
        """Search binary packages"""
        package_literal = _xpath_string_literal(package_name)
        match_parts = [f"name={package_literal}"]
        if repository:
            repo_literal = _xpath_string_literal(repository)
            match_parts.append(f"repository={repo_literal}")

        match = "+and+".join(match_parts)
        try:
            root = self._get("/search/released/binary", {"match": match})
            binaries = []
            for binary_elem in root.findall(".//binary")[:limit]:
                binaries.append(OBSBinary(
                    name=binary_elem.get("name", ""),
                    project=binary_elem.get("project", ""),
                    repository=binary_elem.get("repository", ""),
                    arch=binary_elem.get("arch", ""),
                    version=binary_elem.get("version", ""),
                    release=binary_elem.get("release", ""),
                    filename=binary_elem.get("filename", ""),
                    url=binary_elem.get("url", ""),
                ))
            return binaries
        except (httpx.HTTPError, ET.ParseError):
            return []

    def get_project_repos(self, project: str) -> list[OBSRepo]:
        """Get project repo list"""
        try:
            root = self._get(f"/source/{project}/_meta")
            repos = []
            for repo_elem in root.findall(".//repository"):
                repo_name = repo_elem.get("name", "")
                # Try to extract Fedora version from repo name
                fedora_version = self._extract_fedora_version(repo_name)
                repo_url = f"https://download.opensuse.org/repositories/{project}/{repo_name}"
                repo_file_name = self._get_repo_file_name(project)

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

    def _extract_fedora_version(self, repo_name: str) -> str | None:
        """Extract Fedora version from repo name"""
        # Common formats: Fedora_43, Fedora_43_x86_64, fedora-43-x86_64
        patterns = [
            r"[Ff]edora[_-](\d+)",
            r"[Ff]c(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_name)
            if match:
                return match.group(1)
        return None

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
                capture_output=True,
                text=True,
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
                capture_output=True,
                text=True,
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
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except OSError:
            return False

    def close(self) -> None:
        """Close client"""
        self.client.close()

    def __enter__(self) -> "OBSBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
