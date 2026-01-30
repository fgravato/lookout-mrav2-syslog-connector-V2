#!/bin/bash
#
# Lookout MRAv2 Syslog Connector - Uninstall Script
#

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (use sudo)"
    exit 1
fi

echo "Uninstalling MRAv2 Syslog Connector..."

# Stop and disable service
systemctl stop mrav2-connector 2>/dev/null || true
systemctl disable mrav2-connector 2>/dev/null || true

# Remove service file
rm -f /etc/systemd/system/mrav2-connector.service
systemctl daemon-reload

# Backup config before removal
if [ -f /etc/mrav2-connector/config.ini ]; then
    cp /etc/mrav2-connector/config.ini /etc/mrav2-connector/config.ini.bak.$(date +%Y%m%d)
    echo "Config backed up to /etc/mrav2-connector/config.ini.bak.$(date +%Y%m%d)"
fi

# Remove files
rm -rf /opt/mrav2-connector
rm -f /usr/local/bin/mrav2-syslog-connector

# Optionally remove user and logs
read -p "Remove user 'mrav2' and logs? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    userdel mrav2 2>/dev/null || true
    rm -rf /var/log/mrav2-connector
    rm -rf /etc/mrav2-connector
    echo "User and logs removed"
else
    echo "User and logs preserved"
fi

echo "Uninstallation complete!"
