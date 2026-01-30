.PHONY: all install uninstall clean deb rpm

VERSION := 2.6.8
PACKAGE_NAME := mrav2-syslog-connector

all: help

help:
	@echo "MRAv2 Syslog Connector - Linux Packaging"
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install on local system (requires root)"
	@echo "  uninstall   - Uninstall from local system (requires root)"
	@echo "  deb         - Create Debian/Ubuntu package (.deb)"
	@echo "  rpm         - Create RPM package"
	@echo "  clean       - Clean build artifacts"
	@echo ""

install:
	@echo "Installing MRAv2 Syslog Connector..."
	@sudo bash install.sh

uninstall:
	@echo "Uninstalling MRAv2 Syslog Connector..."
	@sudo bash uninstall.sh

# Create .deb package
deb:
	@echo "Creating Debian package..."
	@mkdir -p build/deb/$(PACKAGE_NAME)-$(VERSION)/DEBIAN
	@mkdir -p build/deb/$(PACKAGE_NAME)-$(VERSION)/opt/$(PACKAGE_NAME)
	@mkdir -p build/deb/$(PACKAGE_NAME)-$(VERSION)/etc/$(PACKAGE_NAME)
	@mkdir -p build/deb/$(PACKAGE_NAME)-$(VERSION)/var/log/$(PACKAGE_NAME)
	@mkdir -p build/deb/$(PACKAGE_NAME)-$(VERSION)/lib/systemd/system
	
	# Create control file
	@cat > build/deb/$(PACKAGE_NAME)-$(VERSION)/DEBIAN/control << CONTROL
Package: $(PACKAGE_NAME)
Version: $(VERSION)
Section: net
Priority: optional
Architecture: all
Depends: python3, python3-venv
Maintainer: Your Name <your.email@example.com>
Description: Lookout MRAv2 Syslog Connector
 Streams security events from Lookout Mobile Risk API v2
 and forwards them to syslog servers (QRadar, Splunk, etc).
CONTROL

	# Copy files
	@cp -r ../lookout_mra_client build/deb/$(PACKAGE_NAME)-$(VERSION)/opt/$(PACKAGE_NAME)/
	@cp ../setup.py build/deb/$(PACKAGE_NAME)-$(VERSION)/opt/$(PACKAGE_NAME)/
	@cp ../README.md build/deb/$(PACKAGE_NAME)-$(VERSION)/opt/$(PACKAGE_NAME)/
	@cp ../requirements.txt build/deb/$(PACKAGE_NAME)-$(VERSION)/opt/$(PACKAGE_NAME)/
	@cp mrav2-connector.service build/deb/$(PACKAGE_NAME)-$(VERSION)/lib/systemd/system/
	
	# Create postinst script
	@cat > build/deb/$(PACKAGE_NAME)-$(VERSION)/DEBIAN/postinst << POSTINST
#!/bin/bash
set -e

# Create user
if ! id mrav2 &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false mrav2
fi

# Set permissions
chown -R mrav2:mrav2 /opt/$(PACKAGE_NAME)
chown -R mrav2:mrav2 /etc/$(PACKAGE_NAME)
chown -R mrav2:mrav2 /var/log/$(PACKAGE_NAME)

# Create virtual environment and install
python3 -m venv /opt/$(PACKAGE_NAME)/venv
/opt/$(PACKAGE_NAME)/venv/bin/pip install --upgrade pip
/opt/$(PACKAGE_NAME)/venv/bin/pip install /opt/$(PACKAGE_NAME)/

# Enable and start service
systemctl daemon-reload
systemctl enable $(PACKAGE_NAME)

echo "$(PACKAGE_NAME) installed successfully!"
echo "Edit /etc/$(PACKAGE_NAME)/config.ini and run: sudo systemctl start $(PACKAGE_NAME)"
POSTINST
	@chmod 755 build/deb/$(PACKAGE_NAME)-$(VERSION)/DEBIAN/postinst
	
	# Build package
	@dpkg-deb --build build/deb/$(PACKAGE_NAME)-$(VERSION) build/$(PACKAGE_NAME)_$(VERSION)_all.deb
	@echo "Debian package created: build/$(PACKAGE_NAME)_$(VERSION)_all.deb"

# Create RPM package
rpm:
	@echo "Creating RPM package..."
	@echo "Note: RPM packaging requires rpmbuild to be installed"
	@mkdir -p build/rpm/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	
	# Create spec file
	@cat > build/rpm/SPECS/$(PACKAGE_NAME).spec << 'SPEC'
Name:           mrav2-syslog-connector
Version:        2.6.8
Release:        1%{?dist}
Summary:        Lookout MRAv2 Syslog Connector
License:        MIT
BuildArch:      noarch
Requires:       python3, python3-virtualenv

%description
Streams security events from Lookout Mobile Risk API v2
and forwards them to syslog servers (QRadar, Splunk, etc).

%install
mkdir -p %{buildroot}/opt/%{name}
mkdir -p %{buildroot}/etc/%{name}
mkdir -p %{buildroot}/var/log/%{name}
mkdir -p %{buildroot}/%{_unitdir}
cp -r %{_sourcedir}/lookout_mra_client %{buildroot}/opt/%{name}/
cp %{_sourcedir}/setup.py %{buildroot}/opt/%{name}/
cp %{_sourcedir}/requirements.txt %{buildroot}/opt/%{name}/
cp %{_sourcedir}/packaging/mrav2-connector.service %{buildroot}/%{_unitdir}/

%post
if ! id mrav2 &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false mrav2
fi
chown -R mrav2:mrav2 /opt/%{name}
chown -R mrav2:mrav2 /etc/%{name}
chown -R mrav2:mrav2 /var/log/%{name}
python3 -m venv /opt/%{name}/venv
/opt/%{name}/venv/bin/pip install /opt/%{name}/
systemctl daemon-reload
systemctl enable %{name}

%files
/opt/%{name}/
%config(noreplace) /etc/%{name}/
%{_unitdir}/mrav2-connector.service
/var/log/%{name}/

%changelog
* Fri Jan 30 2026 - Version 2.6.8
- Initial RPM release
SPEC
	@echo "RPM spec file created. To build: rpmbuild -ba build/rpm/SPECS/$(PACKAGE_NAME).spec"

clean:
	@rm -rf build/
	@echo "Build artifacts cleaned"
