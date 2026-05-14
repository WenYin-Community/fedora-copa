"""配置管理"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tomllib


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
    """搜索配置"""
    enable_fedora: bool = True
    enable_rpmfusion: bool = True
    enable_terra_if_present: bool = True
    enable_copr: bool = True
    terra_repo_patterns: list[str] = field(default_factory=lambda: ["terra*"])


@dataclass
class InstallConfig:
    """安装配置"""
    default_copr_post_action: str = "disable"
    default_chroot_auto_detect: bool = True
    strict_selected_repo: bool = True
    single_package_only: bool = True


@dataclass
class BackendConfig:
    """后端配置"""
    prefer_dnf5: bool = True
    fallback_to_dnf: bool = True
    require_copr_cli: bool = True


@dataclass
class UIConfig:
    """界面配置"""
    language: str = "auto"
    json: bool = False


@dataclass
class RiskConfig:
    """风险配置"""
    block_mock_only: bool = True
    block_do_not_use: bool = True
    warn_experimental: bool = True


@dataclass
class Config:
    """应用配置"""
    search: SearchConfig = field(default_factory=SearchConfig)
    install: InstallConfig = field(default_factory=InstallConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """加载配置文件"""
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

    def save(self, path: Optional[Path] = None) -> None:
        """保存配置文件"""
        config_path = path or DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # TODO: 实现保存逻辑
