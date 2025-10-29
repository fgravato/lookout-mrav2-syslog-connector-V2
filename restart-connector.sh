#!/bin/bash

# MRAv2 Syslog Connector - Restart Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Restarting MRAv2 Syslog Connector..."

# Stop the connector
"${SCRIPT_DIR}/stop-connector.sh"

# Wait a moment
sleep 2

# Start the connector
"${SCRIPT_DIR}/start-connector.sh"
