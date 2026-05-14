Name:           copa
Version:        0.1.0
Release:        1%{?dist}
Summary:        DNF5-style Fedora Copr Package Assistant

License:        GPL-2.0-or-later
URL:            https://github.com/WenYin-Community/fedora-copa
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       python3 >= 3.11
Requires:       python3-copr
Requires:       python3-httpx
Requires:       dnf5
Requires:       copr-cli

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
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

# Install config directory
install -d %{buildroot}%{_sysconfdir}/copa

# Install example config
install -Dm644 /dev/null %{buildroot}%{_sysconfdir}/copa/config.toml

%files
%license LICENSE
%doc README.md README_zh.md
%{python3_sitelib}/copa/
%{python3_sitelib}/copa-%{version}-py%{python3_version}.egg-info/
%{_bindir}/copa
%dir %{_sysconfdir}/copa
%config(noreplace) %{_sysconfdir}/copa/config.toml

%changelog
* Wed May 14 2026 copa contributors <copa@example.com> - 0.1.0-1
- Initial package
- Search packages from Fedora, RPM Fusion, Terra, Copr, OBS
- Install packages with interactive source selection
- Version fallback for OBS packages
- Post-install repo management (keep/disable/remove)
