"""state 模块测试"""

import json
import pytest
import tempfile
from pathlib import Path
from copa.state import AppState, CoprState, OBSState


@pytest.fixture
def temp_state_file(tmp_path):
    """创建临时状态文件"""
    return tmp_path / "state.json"


@pytest.fixture
def sample_state():
    """创建示例状态"""
    state = AppState()
    state.add_copr_repo(
        owner="testuser",
        project="testproject",
        repo_id="copr:testuser/testproject",
        chroot="fedora-43-x86_64",
    )
    state.add_obs_repo(
        project="home:user1",
        repository="Fedora_43",
        repo_file_name="obs_home_user1.repo",
        fedora_version="43",
    )
    return state


class TestAppState:
    """测试 AppState 类"""

    def test_create_empty_state(self):
        """创建空状态"""
        state = AppState()
        assert len(state.copr_repos) == 0
        assert len(state.obs_repos) == 0

    def test_add_copr_repo(self):
        """添加 Copr 仓库"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
        )
        assert len(state.copr_repos) == 1
        assert state.copr_repos[0].owner == "testuser"
        assert state.copr_repos[0].project == "testproject"
        assert state.copr_repos[0].enabled_by_copa is True

    def test_add_obs_repo(self):
        """添加 OBS 仓库"""
        state = AppState()
        state.add_obs_repo(
            project="home:user1",
            repository="Fedora_43",
            repo_file_name="obs_home_user1.repo",
            fedora_version="43",
        )
        assert len(state.obs_repos) == 1
        assert state.obs_repos[0].project == "home:user1"
        assert state.obs_repos[0].enabled_by_copa is True

    def test_get_copr_repo(self):
        """获取 Copr 仓库"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
        )
        repo = state.get_copr_repo("testuser", "testproject")
        assert repo is not None
        assert repo.owner == "testuser"

    def test_get_copr_repo_not_found(self):
        """获取不存在的 Copr 仓库"""
        state = AppState()
        repo = state.get_copr_repo("nonexistent", "project")
        assert repo is None

    def test_remove_copr_repo(self):
        """移除 Copr 仓库"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
        )
        result = state.remove_copr_repo("testuser", "testproject")
        assert result is True
        assert len(state.copr_repos) == 0

    def test_remove_copr_repo_not_found(self):
        """移除不存在的 Copr 仓库"""
        state = AppState()
        result = state.remove_copr_repo("nonexistent", "project")
        assert result is False

    def test_was_enabled_by_copa(self):
        """检查是否由 copa 启用"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
            enabled_by_copa=True,
        )
        assert state.was_enabled_by_copa("testuser", "testproject") is True

    def test_was_not_enabled_by_copa(self):
        """检查是否不由 copa 启用"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
            enabled_by_copa=False,
        )
        assert state.was_enabled_by_copa("testuser", "testproject") is False

    def test_save_and_load(self, temp_state_file, sample_state):
        """保存和加载状态"""
        sample_state.save(temp_state_file)
        loaded = AppState.load(temp_state_file)
        assert len(loaded.copr_repos) == 1
        assert len(loaded.obs_repos) == 1
        assert loaded.copr_repos[0].owner == "testuser"
        assert loaded.obs_repos[0].project == "home:user1"

    def test_load_nonexistent_file(self, temp_state_file):
        """加载不存在的文件"""
        state = AppState.load(temp_state_file)
        assert len(state.copr_repos) == 0
        assert len(state.obs_repos) == 0

    def test_load_invalid_json(self, temp_state_file):
        """加载无效 JSON"""
        temp_state_file.write_text("invalid json")
        state = AppState.load(temp_state_file)
        assert len(state.copr_repos) == 0

    def test_update_existing_copr_repo(self):
        """更新已存在的 Copr 仓库"""
        state = AppState()
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-43-x86_64",
        )
        state.add_copr_repo(
            owner="testuser",
            project="testproject",
            repo_id="copr:testuser/testproject",
            chroot="fedora-44-x86_64",
        )
        assert len(state.copr_repos) == 1
        assert state.copr_repos[0].chroot == "fedora-44-x86_64"
