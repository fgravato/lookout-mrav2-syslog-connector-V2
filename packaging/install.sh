#!/bin/bash
#
# Lookout MRAv2 Syslog Connector - Linux Installation Script
# Supports: Ubuntu, Debian, CentOS, RHEL, Fedora
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/mrav2-connector"
CONFIG_DIR="/etc/mrav2-connector"
LOG_DIR="/var/log/mrav2-connector"
SERVICE_USER="mrav2"
SERVICE_GROUP="mrav2"
VERSION="2.6.8"

echo "=========================================="
echo "MRAv2 Syslog Connector - Linux Installer"
echo "Version: $VERSION"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION_ID=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        OS="centos"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    else
        echo -e "${RED}Error: Unable to detect OS${NC}"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    echo "Installing dependencies..."
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y python3 python3-venv python3-pip
            ;;
        centos|rhel|fedora|rocky|almalinux)
            if command -v dnf &> /dev/null; then
                dnf install -y python3 python3-virtualenv
            else
                yum install -y python3 python3-virtualenv
            fi
            ;;
        *)
            echo -e "${YELLOW}Warning: Unknown OS, assuming Python 3 is installed${NC}"
            ;;
    esac
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Create user and directories
create_user_and_dirs() {
    echo "Creating user and directories..."
    
    # Create user
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    fi
    
    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    
    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$CONFIG_DIR"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$LOG_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod 750 "$CONFIG_DIR"
    chmod 755 "$LOG_DIR"
    
    echo -e "${GREEN}✓ User and directories created${NC}"
}

# Install application
install_application() {
    echo "Installing application..."
    
    # Create virtual environment
    python3 -m venv "$INSTALL_DIR/venv"
    
    # Install package
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    
    # Check if we're installing from local directory or PyPI
    if [ -f "setup.py" ]; then
        echo "Installing from local directory..."
        "$INSTALL_DIR/venv/bin/pip" install .
    else
        echo "Installing from PyPI..."
        "$INSTALL_DIR/venv/bin/pip" install "mrav2-syslog-connector==$VERSION"
    fi
    
    # Create symlink for easy access
    ln -sf "$INSTALL_DIR/venv/bin/mrav2-syslog-connector" /usr/local/bin/mrav2-syslog-connector
    
    echo -e "${GREEN}✓ Application installed${NC}"
}

# Install systemd service
install_service() {
    echo "Installing systemd service..."
    
    if [ -f "packaging/mrav2-connector.service" ]; then
        cp packaging/mrav2-connector.service /etc/systemd/system/
    else
        # Download service file
        curl -sL "https://raw.githubusercontent.com/fgravato/lookout-mrav2-syslog-connector-V2/v$VERSION/packaging/mrav2-connector.service" \
            -o /etc/systemd/system/mrav2-connector.service
    fi
    
    systemctl daemon-reload
    systemctl enable mrav2-connector
    
    echo -e "${GREEN}✓ Systemd service installed${NC}"
}

# Create default config
create_default_config() {
    echo "Creating default configuration..."
    
    if [ ! -f "$CONFIG_DIR/config.ini" ]; then
        cat > "$CONFIG_DIR/config.ini" << 'CONFIG'
[lookout]
entity_name = your-company-name
api_domain = https://api.lookout.com
api_key = your-api-key-here
threat_enabled = true
device_enabled = true
audit_enabled = false
stream_position = 0

[syslog]
host = localhost
port = 514
forwarder_type = qradar

[proxy]
address = 
username = 
password = 
CONFIG
        chown "$SERVICE_USER:$SERVICE_GROUP" "$CONFIG_DIR/config.ini"
        chmod 640 "$CONFIG_DIR/config.ini"
        echo -e "${YELLOW}⚠ Please edit $CONFIG_DIR/config.ini with your credentials${NC}"
    fi
}

# Print completion message
print_completion() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Edit configuration: sudo nano $CONFIG_DIR/config.ini"
    echo "  2. Start service: sudo systemctl start mrav2-connector"
    echo "  3. Check status: sudo systemctl status mrav2-connector"
    echo "  4. View logs: sudo journalctl -u mrav2-connector -f"
    echo ""
    echo "Commands:"
    echo "  Start:   sudo systemctl start mrav2-connector"
    echo "  Stop:    sudo systemctl stop mrav2-connector"
    echo "  Restart: sudo systemctl restart mrav2-connector"
    echo "  Status:  sudo systemctl status mrav2-connector"
    echo ""
}

# Main installation
main() {
    detect_os
    echo "Detected OS: $OS"
    echo ""
    
    install_dependencies
    create_user_and_dirs
    install_application
    install_service
    create_default_config
    
    print_completion
}

main "$@"
