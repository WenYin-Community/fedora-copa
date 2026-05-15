"""Configuration management"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "copa" / "config.toml"

DEFAULT_CONFIG = {
    "search": {
        "enable_fedora": True,
        "enable_rpmfusion": True,
        "enable_terra_if_present": True,
        "enable_copr": True,
        "terra_repo_patterns": ["terra*"],
    },
    "install": {
        "default_copr_post_action": "disable",
        "default_chroot_auto_detect": True,
        "strict_selected_repo": True,
        "single_package_only": True,
    },
    "backend": {
        "prefer_dnf5": True,
        "fallback_to_dnf": True,
        "require_copr_cli": True,
    },
    "ui": {
        "language": "auto",
        "json": False,
    },
    "risk": {
        "block_mock_only": True,
        "block_do_not_use": True,
        "warn_experimental": True,
    },
}


@dataclass
class SearchConfig:
    """Search configuration"""
    enable_fedora: bool = True
    enable_rpmfusion: bool = True
    enable_terra_if_present: bool = True
    enable_copr: bool = True
    terra_repo_patterns: list[str] = field(default_factory=lambda: ["terra*"])


@dataclass
class InstallConfig:
    """Install configuration"""
    default_copr_post_action: str = "disable"
    default_chroot_auto_detect: bool = True
    strict_selected_repo: bool = True
    single_package_only: bool = True


@dataclass
class BackendConfig:
    """Backend configuration"""
    prefer_dnf5: bool = True
    fallback_to_dnf: bool = True
    require_copr_cli: bool = True


@dataclass
class UIConfig:
    """UI configuration"""
    language: str = "auto"
    json: bool = False


@dataclass
class RiskConfig:
    """Risk configuration"""
    block_mock_only: bool = True
    block_do_not_use: bool = True
    warn_experimental: bool = True


@dataclass
class Config:
    """Application configuration"""
    search: SearchConfig = field(default_factory=SearchConfig)
    install: InstallConfig = field(default_factory=InstallConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load configuration file"""
        config_path = path or DEFAULT_CONFIG_PATH

        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            config = cls()
            if "search" in data:
                config.search = SearchConfig(**data["search"])
            if "install" in data:
                config.install = InstallConfig(**data["install"])
            if "backend" in data:
                config.backend = BackendConfig(**data["backend"])
            if "ui" in data:
                config.ui = UIConfig(**data["ui"])
            if "risk" in data:
                config.risk = RiskConfig(**data["risk"])

            return config
        except Exception:
            return cls()

    def save(self, path: Path | None = None) -> None:
        """Save configuration file"""
        config_path = path or DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Save using simple string format
        lines = ["# copa configuration file\n"]

        lines.append("[search]")
        lines.append(
            f"enable_fedora = "
            f"{str(self.search.enable_fedora).lower()}"
        )
        lines.append(
            f"enable_rpmfusion = "
            f"{str(self.search.enable_rpmfusion).lower()}"
        )
        lines.append(
            f"enable_terra_if_present = "
            f"{str(self.search.enable_terra_if_present).lower()}"
        )
        lines.append(
            f"enable_copr = "
            f"{str(self.search.enable_copr).lower()}"
        )
        patterns = ', '.join(
            f'"{p}"' for p in self.search.terra_repo_patterns
        )
        lines.append(f"terra_repo_patterns = [{patterns}]")
        lines.append("")

        lines.append("[install]")
        lines.append(
            f'default_copr_post_action = '
            f'"{self.install.default_copr_post_action}"'
        )
        lines.append(
            f"default_chroot_auto_detect = "
            f"{str(self.install.default_chroot_auto_detect).lower()}"
        )
        lines.append(
            f"strict_selected_repo = "
            f"{str(self.install.strict_selected_repo).lower()}"
        )
        lines.append(
            f"single_package_only = "
            f"{str(self.install.single_package_only).lower()}"
        )
        lines.append("")

        lines.append("[backend]")
        lines.append(
            f"prefer_dnf5 = "
            f"{str(self.backend.prefer_dnf5).lower()}"
        )
        lines.append(
            f"fallback_to_dnf = "
            f"{str(self.backend.fallback_to_dnf).lower()}"
        )
        lines.append(
            f"require_copr_cli = "
            f"{str(self.backend.require_copr_cli).lower()}"
        )
        lines.append("")

        lines.append("[ui]")
        lines.append(f'language = "{self.ui.language}"')
        lines.append(f"json = {str(self.ui.json).lower()}")
        lines.append("")

        lines.append("[risk]")
        lines.append(f"block_mock_only = {str(self.risk.block_mock_only).lower()}")
        lines.append(f"block_do_not_use = {str(self.risk.block_do_not_use).lower()}")
        lines.append(f"warn_experimental = {str(self.risk.warn_experimental).lower()}")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @classmethod
    def generate_example(cls, path: Path | None = None) -> None:
        """Generate example configuration file"""
        config_path = path or DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        example = """# copa configuration file
# Location: ~/.config/copa/config.toml

[search]
# Enable/disable search sources
enable_fedora = true
enable_rpmfusion = true
enable_terra_if_present = true
enable_copr = true

# Terra repo patterns to match
terra_repo_patterns = ["terra*"]

[install]
# Default action after installing from Copr: "disable", "keep", "remove"
default_copr_post_action = "disable"

# Auto-detect chroot for Copr enable
default_chroot_auto_detect = true

# Strictly limit package to selected repo source
strict_selected_repo = true

# Only install single package at a time
single_package_only = true

[backend]
# Prefer dnf5 over dnf
prefer_dnf5 = true

# Fallback to dnf if dnf5 not available
fallback_to_dnf = true

# Require copr-cli for Copr operations
require_copr_cli = true

[ui]
# Language: "auto", "en", "zh"
language = "auto"

# Output in JSON format
json = false

[risk]
# Block packages with these risk words
block_mock_only = true
block_do_not_use = true

# Warn about experimental packages
warn_experimental = true
"""

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(example)
