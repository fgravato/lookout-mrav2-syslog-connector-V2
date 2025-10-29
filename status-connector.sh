#!/bin/bash

# MRAv2 Syslog Connector - Status Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/mrav2-connector.pid"
LOG_FILE="${SCRIPT_DIR}/logs/mrav2-connector.log"

if [ ! -f "$PID_FILE" ]; then
    echo "Status: NOT RUNNING (no PID file found)"
    exit 3
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Status: NOT RUNNING (process $PID not found)"
    rm -f "$PID_FILE"
    exit 3
fi

echo "Status: RUNNING"
echo "PID: $PID"
echo "Install Dir: $SCRIPT_DIR"
echo "Log file: $LOG_FILE"

# Show process info
echo ""
ps -p "$PID" -o pid,etime,vsz,rss,cmd

# Show last few log entries if log file exists
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "Last 10 log entries:"
    tail -n 10 "$LOG_FILE"
fi
