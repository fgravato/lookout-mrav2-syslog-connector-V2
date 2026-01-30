# Linux Packaging

This directory contains files for creating Linux packages and installation scripts.

## Quick Install

### Option 1: Automatic Install Script

```bash
# Download and run the installer
curl -sSL https://raw.githubusercontent.com/fgravato/lookout-mrav2-syslog-connector-V2/main/packaging/install.sh | sudo bash

# Or clone and install locally
git clone https://github.com/fgravato/lookout-mrav2-syslog-connector-V2.git
cd lookout-mrav2-syslog-connector-V2
sudo bash packaging/install.sh
```

### Option 2: Debian/Ubuntu Package (.deb)

```bash
cd packaging
make deb
sudo dpkg -i build/mrav2-syslog-connector_2.6.8_all.deb
```

### Option 3: Docker (Recommended for most users)

```bash
docker pull ghcr.io/fgravato/lookout-mrav2-syslog-connector-v2:v2.6.8
docker run -d -v $(pwd)/config.ini:/app/config.ini:ro mrav2-syslog-connector
```

## Files

- `install.sh` - Universal Linux installation script
- `uninstall.sh` - Uninstall script
- `mrav2-connector.service` - systemd service file
- `Makefile` - Build automation for packages

## Post-Installation

After installation:

1. **Edit configuration:**
   ```bash
   sudo nano /etc/mrav2-connector/config.ini
   ```

2. **Start the service:**
   ```bash
   sudo systemctl start mrav2-connector
   ```

3. **Check status:**
   ```bash
   sudo systemctl status mrav2-connector
   ```

4. **View logs:**
   ```bash
   sudo journalctl -u mrav2-connector -f
   ```

## Supported Distributions

- Ubuntu 18.04, 20.04, 22.04, 24.04
- Debian 10, 11, 12
- CentOS 7, 8
- RHEL 7, 8, 9
- Fedora 35+
- Rocky Linux 8, 9
- AlmaLinux 8, 9

## System Requirements

- Python 3.8 or higher
- 512 MB RAM minimum
- 100 MB disk space
- Network access to Lookout API and syslog server
