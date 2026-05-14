"""状态管理 - 跟踪 Copr 仓库启用状态"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


STATE_DIR = Path.home() / ".local" / "share" / "copa"
STATE_FILE = STATE_DIR / "state.json"


@dataclass
class CoprState:
    """单个 Copr 仓库的状态"""
    owner: str
    project: str
    repo_id: str
    enabled_by_copa: bool
    enabled_at: str  # ISO format
    installed_packages: list[str] = field(default_factory=list)
    chroot: str = ""


@dataclass
class OBSState:
    """单个 OBS 仓库的状态"""
    project: str
    repository: str
    repo_file_name: str
    enabled_by_copa: bool
    enabled_at: str  # ISO format
    installed_packages: list[str] = field(default_factory=list)
    fedora_version: str = ""


@dataclass
class AppState:
    """应用状态"""
    copr_repos: list[CoprState] = field(default_factory=list)
    obs_repos: list[OBSState] = field(default_factory=list)
    last_updated: str = ""  # ISO format

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppState":
        """加载状态文件"""
        state_path = path or STATE_FILE

        if not state_path.exists():
            return cls()

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = cls()
            state.last_updated = data.get("last_updated", "")

            for repo_data in data.get("copr_repos", []):
                state.copr_repos.append(CoprState(**repo_data))

            for repo_data in data.get("obs_repos", []):
                state.obs_repos.append(OBSState(**repo_data))

            return state
        except Exception:
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        """保存状态文件"""
        state_path = path or STATE_FILE
        state_path.parent.mkdir(parents=True, exist_ok=True)

        self.last_updated = datetime.now().isoformat()

        data = {
            "copr_repos": [asdict(repo) for repo in self.copr_repos],
            "obs_repos": [asdict(repo) for repo in self.obs_repos],
            "last_updated": self.last_updated,
        }

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_copr_repo(
        self,
        owner: str,
        project: str,
        repo_id: str,
        chroot: str,
        enabled_by_copa: bool = True,
    ) -> None:
        """添加 Copr 仓库状态"""
        # 检查是否已存在
        for repo in self.copr_repos:
            if repo.owner == owner and repo.project == project:
                # 更新现有记录
                repo.repo_id = repo_id
                repo.chroot = chroot
                repo.enabled_by_copa = enabled_by_copa
                return

        # 添加新记录
        self.copr_repos.append(CoprState(
            owner=owner,
            project=project,
            repo_id=repo_id,
            enabled_by_copa=enabled_by_copa,
            enabled_at=datetime.now().isoformat(),
            chroot=chroot,
        ))

    def get_copr_repo(self, owner: str, project: str) -> Optional[CoprState]:
        """获取 Copr 仓库状态"""
        for repo in self.copr_repos:
            if repo.owner == owner and repo.project == project:
                return repo
        return None

    def remove_copr_repo(self, owner: str, project: str) -> bool:
        """移除 Copr 仓库状态"""
        for i, repo in enumerate(self.copr_repos):
            if repo.owner == owner and repo.project == project:
                self.copr_repos.pop(i)
                return True
        return False

    def was_enabled_by_copa(self, owner: str, project: str) -> bool:
        """检查是否由 copa 启用"""
        repo = self.get_copr_repo(owner, project)
        return repo.enabled_by_copa if repo else False

    def add_obs_repo(
        self,
        project: str,
        repository: str,
        repo_file_name: str,
        fedora_version: str,
        enabled_by_copa: bool = True,
    ) -> None:
        """添加 OBS 仓库状态"""
        # 检查是否已存在
        for repo in self.obs_repos:
            if repo.project == project:
                # 更新现有记录
                repo.repository = repository
                repo.repo_file_name = repo_file_name
                repo.fedora_version = fedora_version
                repo.enabled_by_copa = enabled_by_copa
                return

        # 添加新记录
        self.obs_repos.append(OBSState(
            project=project,
            repository=repository,
            repo_file_name=repo_file_name,
            enabled_by_copa=enabled_by_copa,
            enabled_at=datetime.now().isoformat(),
            fedora_version=fedora_version,
        ))

    def get_obs_repo(self, project: str) -> Optional[OBSState]:
        """获取 OBS 仓库状态"""
        for repo in self.obs_repos:
            if repo.project == project:
                return repo
        return None

    def remove_obs_repo(self, project: str) -> bool:
        """移除 OBS 仓库状态"""
        for i, repo in enumerate(self.obs_repos):
            if repo.project == project:
                self.obs_repos.pop(i)
                return True
        return False

    def was_obs_enabled_by_copa(self, project: str) -> bool:
        """检查 OBS 仓库是否由 copa 启用"""
        repo = self.get_obs_repo(project)
        return repo.enabled_by_copa if repo else False
