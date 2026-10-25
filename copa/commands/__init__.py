"""CLI command implementations."""

from copa.commands.admin import cmd_audit, cmd_doctor, cmd_remove
from copa.commands.info import cmd_info
from copa.commands.install import (
    _install_from_copr,
    _install_from_copr_spec,
    _install_from_obs,
    _resolve_package_name,
    cmd_install,
)
from copa.commands.list import cmd_list
from copa.commands.query import cmd_provides, cmd_repoquery
from copa.commands.repo import cmd_repo
from copa.commands.search import (
    _filter_by_keywords,
    _filter_by_regex,
    _filter_copr_by_keywords,
    _filter_copr_by_regex,
    _filter_obs_by_keywords,
    _filter_obs_by_regex,
    _regex_seeds,
    cmd_search,
)

__all__ = [
    "cmd_audit",
    "cmd_doctor",
    "cmd_info",
    "cmd_install",
    "cmd_list",
    "cmd_provides",
    "cmd_remove",
    "cmd_repo",
    "cmd_repoquery",
    "cmd_search",
    "_filter_by_keywords",
    "_filter_by_regex",
    "_filter_copr_by_keywords",
    "_filter_copr_by_regex",
    "_filter_obs_by_keywords",
    "_filter_obs_by_regex",
    "_install_from_copr",
    "_install_from_copr_spec",
    "_install_from_obs",
    "_regex_seeds",
    "_resolve_package_name",
]
