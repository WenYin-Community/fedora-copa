"""state module tests"""


import pytest

from copa.state import AppState


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temp state file"""
    return tmp_path / "state.json"


@pytest.fixture
def sample_state():
    """Create sample state"""
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
    """Test AppState class"""

    def test_create_empty_state(self):
        """Create empty state"""
        state = AppState()
        assert len(state.copr_repos) == 0
        assert len(state.obs_repos) == 0

    def test_add_copr_repo(self):
        """Add Copr repo"""
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
        """Add OBS repo"""
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
        """Get Copr repo"""
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
        """Get non-existent Copr repo"""
        state = AppState()
        repo = state.get_copr_repo("nonexistent", "project")
        assert repo is None

    def test_remove_copr_repo(self):
        """Remove Copr repo"""
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
        """Remove non-existent Copr repo"""
        state = AppState()
        result = state.remove_copr_repo("nonexistent", "project")
        assert result is False

    def test_was_enabled_by_copa(self):
        """Check if enabled by copa"""
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
        """Check if not enabled by copa"""
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
        """Save and load state"""
        sample_state.save(temp_state_file)
        loaded = AppState.load(temp_state_file)
        assert len(loaded.copr_repos) == 1
        assert len(loaded.obs_repos) == 1
        assert loaded.copr_repos[0].owner == "testuser"
        assert loaded.obs_repos[0].project == "home:user1"

    def test_load_nonexistent_file(self, temp_state_file):
        """Load non-existent file"""
        state = AppState.load(temp_state_file)
        assert len(state.copr_repos) == 0
        assert len(state.obs_repos) == 0

    def test_load_invalid_json(self, temp_state_file):
        """Load invalid JSON"""
        temp_state_file.write_text("invalid json")
        state = AppState.load(temp_state_file)
        assert len(state.copr_repos) == 0

    def test_update_existing_copr_repo(self):
        """Update existing Copr repo"""
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
