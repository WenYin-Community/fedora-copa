Name:           fedora-copa
Version:        0.5.0
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

Requires:       python3 >= 3.11
Requires:       python3-copr
Requires:       python3-httpx
Requires:       dnf5
Requires:       copr-cli
Requires:       osc

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
%{__python3} -m pip wheel --no-deps --wheel-dir=%{_builddir} .

%install
%{__python3} -m pip install --no-deps --ignore-installed --root=%{buildroot} --prefix=%{_prefix} %{_builddir}/fedora_copa-%{version}-py3-none-any.whl

# Install config directory
install -d %{buildroot}%{_sysconfdir}/copa

# Install example config
install -Dm644 /dev/null %{buildroot}%{_sysconfdir}/copa/config.toml

# Install man page
install -Dm644 man/copa.1 %{buildroot}%{_mandir}/man1/copa.1

# Install bash completion
install -Dm644 completions/copa.bash %{buildroot}%{bash_completions_dir}/copa

# Install zsh completion
install -Dm644 completions/_copa %{buildroot}%{zsh_completions_dir}/_copa

%check
%{__python3} -m pytest tests/ -v

%files
%license LICENSE
%doc README.md README_zh.md
%{python3_sitelib}/copa/
%{python3_sitelib}/fedora_copa-%{version}.dist-info/
%{_bindir}/copa
%{_mandir}/man1/copa.1*
%{bash_completions_dir}/copa
%{zsh_completions_dir}/_copa
%dir %{_sysconfdir}/copa
%config(noreplace) %{_sysconfdir}/copa/config.toml

%changelog
* Thu May 15 2025 copa contributors <copa@example.com> - 0.5.0-1
- OBS authentication support (reads ~/.config/osc/oscrc)
- Fix Copr repo ID format (colon-separated)
- Fix OBS API endpoint and repo file URL
- Add --include-local-repo flag for install command

* Thu May 15 2025 copa contributors <copa@example.com> - 0.2.0-1
- Fix sudo password prompt hidden by capture_output in DnfBackend

* Wed May 14 2025 copa contributors <copa@example.com> - 0.1.0-1
- Initial package
