%global debug_package %{nil}

Name:           easyview
Version:        0.1.1
Release:        1%{?dist}
Summary:        Lightweight RTSP/HTTP-HLS video surveillance preview client
License:        MIT
URL:            https://github.com/yaoyongli1974-dotcom/EasyVIEW
Source0:        %{name}-bundle.tar.gz
Source1:        easyview.desktop
Source2:        icon.png
BuildArch:      x86_64
Recommends:     vlc

%description
EasyVIEW is a minimal video surveillance preview client (PyQt6 + LibVLC).
It focuses on putting RTSP / HTTP-HLS cameras on a 1-64 pane wall, with
device/channel management, auto split layouts and connection diagnosis.
libvlc (VLC) is required at runtime.

%prep
%setup -q -c

%build
# prebuilt PyInstaller bundle, nothing to compile

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/easyview
cp -r EasyVIEW/. %{buildroot}/opt/easyview/

mkdir -p %{buildroot}/usr/bin
ln -s /opt/easyview/EasyVIEW %{buildroot}/usr/bin/easyview

mkdir -p %{buildroot}/usr/share/applications
cp %{SOURCE1} %{buildroot}/usr/share/applications/easyview.desktop

mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps
cp %{SOURCE2} %{buildroot}/usr/share/icons/hicolor/256x256/apps/easyview.png

%files
/opt/easyview
/usr/bin/easyview
/usr/share/applications/easyview.desktop
/usr/share/icons/hicolor/256x256/apps/easyview.png

%changelog
* Fri Oct 09 2026 EasyVIEW Maintainers <maintainer@example.com> - 0.1.1-1
- Minimal preview client release 0.1.1
