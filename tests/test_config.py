"""config module tests"""


import pytest

from copa.config import (
    Config,
    InstallConfig,
    SearchConfig,
)


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temp config file"""
    return tmp_path / "config.toml"


@pytest.fixture
def sample_config():
    """Create sample config"""
    config = Config()
    config.search.enable_fedora = True
    config.search.enable_rpmfusion = False
    config.install.default_copr_post_action = "disable"
    config.backend.prefer_dnf5 = True
    return config


class TestSearchConfig:
    """Test SearchConfig"""

    def test_default_values(self):
        """Default values"""
        config = SearchConfig()
        assert config.enable_fedora is True
        assert config.enable_rpmfusion is True
        assert config.enable_terra_if_present is True
        assert config.enable_copr is True

    def test_custom_values(self):
        """Custom values"""
        config = SearchConfig(enable_fedora=False, enable_copr=False)
        assert config.enable_fedora is False
        assert config.enable_copr is False


class TestInstallConfig:
    """Test InstallConfig"""

    def test_default_values(self):
        """Default values"""
        config = InstallConfig()
        assert config.default_copr_post_action == "disable"
        assert config.strict_selected_repo is True


class TestConfig:
    """Test Config"""

    def test_create_default_config(self):
        """Create default config"""
        config = Config()
        assert config.search.enable_fedora is True
        assert config.install.default_copr_post_action == "disable"

    def test_save_and_load(self, temp_config_file, sample_config):
        """Save and load config"""
        sample_config.save(temp_config_file)
        loaded = Config.load(temp_config_file)
        assert loaded.search.enable_fedora is True
        assert loaded.search.enable_rpmfusion is False
        assert loaded.install.default_copr_post_action == "disable"

    def test_load_nonexistent_file(self, temp_config_file):
        """Load non-existent file"""
        config = Config.load(temp_config_file)
        assert config.search.enable_fedora is True  # Default value

    def test_load_invalid_file(self, temp_config_file):
        """Load invalid file"""
        temp_config_file.write_text("invalid toml")
        config = Config.load(temp_config_file)
        assert config.search.enable_fedora is True  # Default value

    def test_generate_example(self, temp_config_file):
        """Generate example config"""
        Config.generate_example(temp_config_file)
        assert temp_config_file.exists()
        content = temp_config_file.read_text()
        assert "enable_fedora = true" in content
        assert "default_copr_post_action" in content
