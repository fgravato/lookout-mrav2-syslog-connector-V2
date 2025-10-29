# MRAv2 Syslog Connector

A high-performance Python connector that streams security events from Lookout Mobile Risk API v2 and forwards them to syslog servers (QRadar, Splunk, etc).

## Features

- **Real-time Event Streaming**: Uses Server-Sent Events (SSE) for efficient, continuous event streaming
- **Multi-tenant Support**: Handle multiple API tenants with concurrent threads
- **Auto-reconnection**: Automatic reconnection with exponential backoff on connection failures
- **OAuth2 Authentication**: Secure authentication with automatic token refresh
- **Configurable Event Types**: Stream THREAT, DEVICE, and/or AUDIT events
- **Proxy Support**: HTTP/HTTPS proxy configuration with authentication
- **Scalable**: Designed to handle 10k-30k+ devices per tenant
- **QRadar & Splunk Support**: Built-in formatters for both platforms

## Architecture

The connector uses Python's threading model with SSE for I/O-bound event streaming:
- Each tenant runs in its own thread with independent SSE connection
- Events are streamed asynchronously and forwarded to syslog in real-time
- Stream position is tracked to prevent event loss on reconnection

## Requirements

- Python 3.7+
- Network access to Lookout API and syslog server
- Lookout API key (OAuth2 client credentials)

## Installation

### Standalone Installation (Recommended)

The connector is distributed as a standalone tar.gz package with all dependencies.

**1. Extract the package:**

```bash
tar -xzf mrav2-syslog-connector-2.6.7.tar.gz
cd mrav2-syslog-connector-2.6.7
```

**2. Run the installer:**

```bash
./install.sh
```

The installer will:
- Check Python 3.7+ is installed
- Create a virtual environment
- Install all pip dependencies
- Set up configuration files
- Create log directory

**3. Configure:**

```bash
vi config.ini
# Add your Lookout API credentials and syslog server details
```

**4. Start the connector:**

```bash
./start-connector.sh
```

That's it! The connector runs standalone without affecting system Python packages.

### Alternative: System-wide Installation

If you prefer to install globally:

```bash
pip3 install .
```

Then run directly:

```bash
mrav2-syslog-connector --config config.ini
```

## Configuration

1. **Copy the example configuration file:**

```bash
cp config.ini.example config.ini
```

2. **Edit config.ini with your settings:**

```ini
[lookout]
entity_name = my-company
api_domain = https://api.lookout.com
api_key = YOUR_API_KEY_HERE
threat_enabled = true
device_enabled = true
audit_enabled = false
stream_position = 0

[syslog]
host = localhost
port = 514
forwarder_type = qradar

[proxy]
# Optional: Leave empty if no proxy needed
address = 
username = 
password = 
```

### Configuration Options

#### [lookout] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `entity_name` | Your Lookout tenant/entity name | Yes | - |
| `api_domain` | Lookout API domain URL | Yes | - |
| `api_key` | OAuth2 API key/client credentials | Yes | - |
| `threat_enabled` | Enable threat event streaming | No | true |
| `device_enabled` | Enable device event streaming | No | true |
| `audit_enabled` | Enable audit event streaming | No | false |
| `stream_position` | Stream position to resume from | No | 0 |
| `start_time` | ISO timestamp to start from (if stream_position=0) | No | - |

#### [syslog] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `host` | Syslog server hostname/IP | Yes | localhost |
| `port` | Syslog server port | Yes | 514 |
| `forwarder_type` | Event formatter: `qradar` or `splunk` | No | qradar |
| `log_identifier_key` | Custom identifier key for log routing | No | - |
| `log_identifier` | Custom identifier value for log routing | No | - |

#### [proxy] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `address` | Proxy URL (e.g., http://proxy:8080) | No | - |
| `username` | Proxy authentication username | No | - |
| `password` | Proxy authentication password | No | - |

## Usage

### Running the Connector

#### Using Control Scripts (Recommended)

The package includes convenience scripts for daemon-like operation:

```bash
# Start the connector in background
./start-connector.sh

# Check status
./status-connector.sh

# Stop the connector
./stop-connector.sh

# Restart the connector
./restart-connector.sh
```

All logs are written to the `logs/` directory within the installation.

#### Manual Execution

You can also run the connector directly in foreground:

```bash
# Using the standalone wrapper
./mrav2-connector --config config.ini --log-file logs/connector.log

# With verbose logging
./mrav2-connector --config config.ini --verbose
```

**Note:** The `./mrav2-connector` wrapper automatically uses the virtual environment created during installation.

### Running as a Service

#### systemd (Linux)

Create `/etc/systemd/system/mrav2-connector.service`:

```ini
[Unit]
Description=MRAv2 Syslog Connector
After=network.target

[Service]
Type=simple
User=lookout
WorkingDirectory=/opt/mrav2-connector
ExecStart=/usr/local/bin/mrav2-syslog-connector --config /opt/mrav2-connector/config.ini --log-file /var/log/mrav2-connector.log
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mrav2-connector
sudo systemctl start mrav2-connector
sudo systemctl status mrav2-connector
```

#### launchd (macOS)

Create `~/Library/LaunchAgents/com.lookout.mrav2-connector.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lookout.mrav2-connector</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/mrav2-syslog-connector</string>
        <string>--config</string>
        <string>/Users/youruser/mrav2-connector/config.ini</string>
        <string>--log-file</string>
        <string>/Users/youruser/mrav2-connector/connector.log</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.lookout.mrav2-connector.plist
launchctl start com.lookout.mrav2-connector
```

## Monitoring

### Log Files

The connector generates detailed logs at the specified log file location:

```bash
# View real-time logs
tail -f /var/log/mrav2-connector.log

# Search for errors
grep ERROR /var/log/mrav2-connector.log

# Check connection status
grep "started successfully" /var/log/mrav2-connector.log
```

### Health Checks

```bash
# Check if process is running
./status-connector.sh

# Or manually
ps aux | grep mrav2-syslog-connector

# Check network connectivity
netstat -an | grep <syslog_port>
```

### Key Log Messages

- `MRAv2 Syslog Connector started successfully` - Connector running
- `Wrote X events to syslog` - Events successfully forwarded
- `received heartbeat` - Connection alive (debug mode)
- `Restarting MRA v2 stream` - Auto-reconnection triggered
- `Access token expired, refreshing token` - OAuth token refresh

## Scaling

### Multi-tenant Deployment

For multiple tenants, you can:

1. **Run multiple instances** with separate config files:
```bash
mrav2-syslog-connector --config tenant1.ini --log-file tenant1.log &
mrav2-syslog-connector --config tenant2.ini --log-file tenant2.log &
```

2. **Use the built-in threading** by modifying the code to load multiple configs

### Performance Tuning

- **Network Bandwidth**: Each tenant typically uses ~1-5 Mbps depending on event volume
- **Memory**: ~50-100 MB per tenant thread
- **CPU**: Minimal, I/O-bound workload
- **Stream Position**: Automatically saved to prevent duplicate events

### Capacity Guidelines

| Devices | Tenants | Recommended Resources |
|---------|---------|----------------------|
| 10k | 1-5 | 2 CPU, 2 GB RAM |
| 30k | 1-5 | 2 CPU, 4 GB RAM |
| 50k+ | 5-10 | 4 CPU, 8 GB RAM |

## Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to MRA v2`

**Solutions**:
- Verify `api_domain` is correct
- Check network connectivity to Lookout API
- Verify proxy settings if using proxy
- Check firewall rules

### Authentication Issues

**Problem**: `Access token expired` or OAuth errors

**Solutions**:
- Verify `api_key` is correct
- Check API key has not been revoked
- Ensure system time is synchronized (NTP)

### Syslog Forwarding Issues

**Problem**: Events not appearing in SIEM

**Solutions**:
- Verify syslog server is listening: `netstat -an | grep <port>`
- Check firewall allows UDP/TCP to syslog port
- Verify `forwarder_type` matches your SIEM (qradar/splunk)
- Check SIEM ingestion rules/filters

### Stream Position Reset

**Problem**: Duplicate events after restart

**Solutions**:
- Ensure `stream_position` in config.ini is updated
- Check file permissions on config.ini
- For QRadar integration, verify database persistence

## Development

### Project Structure

```
lookout_mra_client/
├── __init__.py              # Package initialization
├── main.py                  # Main entry point
├── mra_v2_stream.py         # SSE stream client
├── mra_v2_stream_thread.py  # Thread wrapper
├── sse_client.py            # SSE protocol implementation
├── oauth2_client.py         # OAuth2 authentication
├── syslog_client.py         # Syslog sender
├── event_forwarders/        # Event formatters
│   ├── qradar_event_forwarder.py
│   └── splunk_event_forwarder.py
├── event_translators/       # Event translators
├── event_store/             # Event persistence
└── models/                  # Data models
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=lookout_mra_client
```

## License

See LICENSE.txt for details.

## Support

For issues or questions:
- Check the logs first: `/var/log/mrav2-connector.log`
- Review this README and configuration examples
- Contact Lookout support with log excerpts

## Version History

- **2.6.7** - Renamed to MRAv2 Syslog Connector, removed demo scripts, added packaging
- Previous versions - Lookout MRA Client library

---

**Note**: This connector is designed for production use and can handle high-volume event streaming. For optimal performance, ensure your syslog server can handle the expected event throughput.
