"""Dependency and file-provider query commands."""

import json
from typing import Any

from copa.cli_helpers import _make_dnf
from copa.i18n import tr


def cmd_repoquery(args: Any) -> int:
    """repoquery command implementation - query package dependencies"""
    package = args.package
    dnf = _make_dnf(args)
    use_json = args.json

    result_data: dict[str, Any] = {
        "package": package,
        "type": "unknown",
        "items": [],
    }

    if args.requires:
        result_data["type"] = "requires"
        result_data["items"] = dnf.query_requires(package)
    elif args.provides:
        result_data["type"] = "provides"
        result_data["items"] = dnf.query_provides(package)
    elif args.files:
        result_data["type"] = "files"
        result_data["items"] = dnf.query_files(package)
    else:
        result_data["type"] = "info"
        info = dnf.query_info(package)
        if info:
            result_data["info"] = info.strip()
        else:
            result_data["error"] = f"Package {package} not found"
            if use_json:
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(tr("Querying package: {package}").format(package=package))
                print()
                print(tr("  Package {package} not found").format(package=package))
            return 1

    if not use_json:
        print(tr("Querying package: {package}").format(package=package))
        print()
        if result_data["type"] == "requires":
            print(tr("Dependencies:"))
            for item in result_data["items"]:
                print(f"  {item}")
        elif result_data["type"] == "provides":
            print(tr("Provides:"))
            for item in result_data["items"]:
                print(f"  {item}")
        elif result_data["type"] == "files":
            print(tr("Files:"))
            for item in result_data["items"]:
                print(f"  {item}")
        else:
            print(tr("Package info:"))
            print(result_data["info"])

    if not result_data.get("items") and result_data["type"] != "info":
        result_data["error"] = f"Package {package} not found or error querying"
        if use_json:
            print(json.dumps(result_data, indent=2, ensure_ascii=False))
        else:
            print(
                tr("  Package {package} not found or error querying").format(
                    package=package
                )
            )
        return 1

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0


def cmd_provides(args: Any) -> int:
    """provides command implementation - find packages providing a file"""
    file_path = args.file
    dnf = _make_dnf(args)
    use_json = args.json

    result_data: dict[str, Any] = {
        "file": file_path,
        "providers": [],
    }

    result_data["providers"] = dnf.search_providers(file_path)

    if not result_data["providers"]:
        result_data["error"] = f"No packages found providing {file_path}"
        if use_json:
            print(json.dumps(result_data, indent=2, ensure_ascii=False))
        else:
            print(tr("Finding packages providing: {file}").format(file=file_path))
            print()
            print(tr("No packages found providing {file}").format(file=file_path))
        return 1

    if not use_json:
        print(tr("Finding packages providing: {file}").format(file=file_path))
        print()
        print(tr("Found in repositories:"))
        for line in result_data["providers"]:
            print(f"  {line}")

    if use_json:
        print(json.dumps(result_data, indent=2, ensure_ascii=False))

    return 0
