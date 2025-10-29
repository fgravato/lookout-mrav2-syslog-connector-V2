#!/bin/bash

# MRAv2 Syslog Connector - Start Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/mrav2-connector.pid"
CONFIG_FILE="${SCRIPT_DIR}/config.ini"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/mrav2-connector.log"
STDOUT_LOG="${LOG_DIR}/mrav2-connector-stdout.log"

# Check if installed
if [ ! -d "${SCRIPT_DIR}/venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run ./install.sh first"
    exit 1
fi

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Configuration file not found: $CONFIG_FILE"
    echo "Please edit config.ini with your Lookout API credentials"
    exit 1
fi

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "MRAv2 Syslog Connector is already running (PID: $PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

echo "Starting MRAv2 Syslog Connector..."

# Start the connector in the background
nohup "${SCRIPT_DIR}/mrav2-connector" \
    --config "$CONFIG_FILE" \
    --log-file "$LOG_FILE" \
    > "$STDOUT_LOG" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

# Wait a moment and check if process is still running
sleep 2
if ps -p "$PID" > /dev/null 2>&1; then
    echo "MRAv2 Syslog Connector started successfully (PID: $PID)"
    echo "Log file: $LOG_FILE"
    echo "Use './stop-connector.sh' to stop the connector"
else
    echo "ERROR: Failed to start MRAv2 Syslog Connector"
    rm -f "$PID_FILE"
    echo "Check logs at: $STDOUT_LOG"
    exit 1
fi
