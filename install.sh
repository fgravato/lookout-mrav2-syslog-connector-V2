#!/bin/bash

# MRAv2 Syslog Connector - Installation Script
# This script sets up a standalone installation with virtual environment

set -e

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${INSTALL_DIR}/venv"

echo "========================================"
echo "MRAv2 Syslog Connector - Installation"
echo "========================================"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.7 or higher and try again"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Check Python version is 3.7+
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
    echo "ERROR: Python 3.7 or higher is required"
    echo "You have Python $PYTHON_VERSION"
    exit 1
fi

echo "Python version check passed"
echo ""

# Check for pip3
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed"
    echo "Please install pip3 and try again"
    exit 1
fi

echo "Installing MRAv2 Syslog Connector to: $INSTALL_DIR"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists, removing..."
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
echo "Virtual environment created"
echo ""

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install requests>=2.25.0 \
    requests-oauthlib>=1.3.0 \
    oauthlib>=3.1.0 \
    backoff>=1.10.0 \
    peewee>=3.14.0 \
    furl>=2.1.0 \
    importlib-metadata>=4.0.0

echo ""
echo "Dependencies installed successfully"
echo ""

# Create config if it doesn't exist
if [ ! -f "${INSTALL_DIR}/config.ini" ]; then
    echo "Creating default configuration file..."
    cp "${INSTALL_DIR}/config.ini.example" "${INSTALL_DIR}/config.ini"
    echo "Configuration file created: ${INSTALL_DIR}/config.ini"
    echo "Please edit this file with your Lookout API credentials"
else
    echo "Configuration file already exists: ${INSTALL_DIR}/config.ini"
fi

echo ""

# Create log directory
LOG_DIR="${INSTALL_DIR}/logs"
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    echo "Created log directory: $LOG_DIR"
fi

# Make scripts executable
chmod +x "${INSTALL_DIR}/mrav2-connector" \
    "${INSTALL_DIR}/start-connector.sh" \
    "${INSTALL_DIR}/stop-connector.sh" \
    "${INSTALL_DIR}/restart-connector.sh" \
    "${INSTALL_DIR}/status-connector.sh"

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit the configuration file:"
echo "   vi ${INSTALL_DIR}/config.ini"
echo ""
echo "2. Start the connector:"
echo "   ${INSTALL_DIR}/start-connector.sh"
echo ""
echo "3. Check status:"
echo "   ${INSTALL_DIR}/status-connector.sh"
echo ""
echo "Logs will be written to: ${LOG_DIR}/"
echo ""
