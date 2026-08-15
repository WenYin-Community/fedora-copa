Name:           fedora-copa
Version:        0.9.8
Release:        1%{?dist}
Summary:        DNF5-style Fedora Copr Package Assistant

License:        GPL-2.0-or-later
URL:            https://github.com/WenYin-Community/fedora-copa
Source0:        %{url}/releases/download/v%{version}/fedora-copa-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-pytest
BuildRequires:  python3-copr
BuildRequires:  python3-httpx

Requires:       python3 >= 3.11
Requires:       python3-copr
Requires:       python3-httpx
Requires:       (dnf5 or dnf)

%description
copa is a Copr package assistant for the Fedora / DNF5 ecosystem, providing
a search and install experience similar to paru/yay on Arch, but with DNF-style
command format.

Supported package sources:
- Fedora official repos
- RPM Fusion
- Terra
- Copr (Fedora community build service)
- openSUSE OBS (cross-distro build service)

%prep
%autosetup -n fedora-copa-%{version}

%build
%{__python3} -m pip wheel --no-build-isolation --no-deps --wheel-dir=%{_builddir} .

%install
%{__python3} -m pip install --no-deps --ignore-installed --root=%{buildroot} --prefix=%{_prefix} %{_builddir}/fedora_copa-%{version}-py3-none-any.whl

# Install config directory
install -d %{buildroot}%{_sysconfdir}/copa

# Install example config
install -Dm644 /dev/null %{buildroot}%{_sysconfdir}/copa/config.toml

# Install man page
install -Dm644 man/copa.1 %{buildroot}%{_mandir}/man1/copa.1

# Install bash completion
install -Dm644 completions/copa.bash %{buildroot}%{_datadir}/bash-completion/completions/copa

# Install zsh completion
install -Dm644 completions/_copa %{buildroot}%{_datadir}/zsh/site-functions/_copa

%check
%{__python3} -m pytest tests/ -v

%files
%doc README.md README_zh.md
%{python3_sitelib}/copa/
%{python3_sitelib}/fedora_copa-%{version}.dist-info/
%{_bindir}/copa
%{_mandir}/man1/copa.1*
%{_datadir}/bash-completion/completions/copa
%{_datadir}/zsh/site-functions/_copa
%dir %{_sysconfdir}/copa
%config(noreplace) %{_sysconfdir}/copa/config.toml

%changelog
* Sun Aug 16 2026 copa contributors <copa@example.com> - 0.9.8-1
- Config is now fully wired: search source switches, dnf binary preference,
  risk blocking, and default JSON output take effect; unimplemented options removed
- Risk: "experimental" projects now warn (medium) instead of being blocked;
  risk keyword lists shared between search and audit
- CLI: --json accepted after info/list/repoquery/provides subcommands;
  deduplicated local-repo search logic; -y auto-selects a single third-party result
- Backend: rawhide OBS repo matching, glob escaping for keywords,
  public repoquery/provides methods replace private _run calls
- State: atomic state.json writes (temp file + rename)
- CI: version-consistency check across pyproject.toml/__init__.py/spec,
  git archive for release tarballs, concurrency guard, gh-release v2
- Packaging: runtime deps slimmed to (dnf5 or dnf); copr-cli and osc no longer required
- Tests: +15 covering config wiring, risk flags, rawhide OBS, glob escaping, cmd_search/cmd_remove

* Mon Aug 03 2026 copa contributors <copa@example.com> - 0.9.6-1
- Robustness fixes: EOFError handling in confirm(), per-section config tolerance, per-entry state tolerance
- Copr backend: drop ineffective retry decorator, unified API error handling (404/403 silent, network errors warn)
- OBS backend: sudo commands show password prompt (capture_output=False); remove dead search_binaries
- CLI: remove dead code; OBS unavailability now warns instead of silent skip
- Tests: +44 covering risk assessment, version fallback, install flow, Copr backend error handling

* Wed Jun 04 2025 copa contributors <copa@example.com> - 0.9.5.1-1
- Fix missing shell completions and man page in RPM package

* Wed Jun 04 2025 copa contributors <copa@example.com> - 0.9.5-1
- Fix duplicate return 0 in cmd_search
- Extract extract_fedora_version as module-level function
- Use context manager for OBSBackend in cmd_install and cmd_repo
- Wire config.install.default_copr_post_action into cmd_install
- Remove redundant hasattr checks for argparse arguments
- Remove unused utility functions from utils.py
- Deduplicate _parse_repoquery with _build_package helper
- Cache /etc/os-release reads in DnfBackend
- Lazy-initialise httpx.Client in OBSBackend
- Remove implicit requests dependency from copr_backend

* Wed May 21 2025 copa contributors <copa@example.com> - 0.8.0-1
- Version bump to 0.8.0

* Thu May 15 2025 copa contributors <copa@example.com> - 0.5.0-1
- OBS authentication support (reads ~/.config/osc/oscrc)
- Fix Copr repo ID format (colon-separated)
- Fix OBS API endpoint and repo file URL
- Add --include-local-repo flag for install command

* Thu May 15 2025 copa contributors <copa@example.com> - 0.2.0-1
- Fix sudo password prompt hidden by capture_output in DnfBackend

* Wed May 14 2025 copa contributors <copa@example.com> - 0.1.0-1
- Initial package
