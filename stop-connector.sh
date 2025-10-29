#!/bin/bash

# MRAv2 Syslog Connector - Stop Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/mrav2-connector.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "MRAv2 Syslog Connector is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "MRAv2 Syslog Connector is not running (process $PID not found)"
    rm -f "$PID_FILE"
    exit 0
fi

echo "Stopping MRAv2 Syslog Connector (PID: $PID)..."
kill -TERM "$PID"

# Wait for process to terminate (max 10 seconds)
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "MRAv2 Syslog Connector stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Process did not terminate gracefully, forcing shutdown..."
    kill -9 "$PID"
    sleep 1
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "MRAv2 Syslog Connector stopped forcefully"
        rm -f "$PID_FILE"
        exit 0
    else
        echo "ERROR: Failed to stop MRAv2 Syslog Connector"
        exit 1
    fi
fi
