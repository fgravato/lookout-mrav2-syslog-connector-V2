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
- **QRadar & Splunk Support**: LEEF 2.0 for QRadar, JSON for Splunk — both over syslog TCP/UDP

## Architecture

The connector uses Python's threading model with SSE for I/O-bound event streaming:
- Each tenant runs in its own thread with independent SSE connection
- Events are streamed asynchronously and forwarded to syslog in real-time
- Stream position is tracked to prevent event loss on reconnection

## Requirements

- Python 3.8+
- Network access to Lookout API and syslog server
- Lookout API key (OAuth2 client credentials)

## Installation

### Option 1: Clone and run standalone (recommended)

```bash
git clone https://github.com/fgravato/lookout-mrav2-syslog-connector-V2.git
cd lookout-mrav2-syslog-connector-V2
./install.sh
```

The installer will:
- Verify Python 3.8+ is installed
- Create a virtual environment under `./venv/`
- Install all pip dependencies from `requirements.txt`

Then configure and start:

```bash
cp config.ini.example config.ini
vi config.ini          # add your API key and syslog server details
./start-connector.sh
```

### Option 2: Install from release tar.gz

Download `mrav2_syslog_connector-2.6.12.tar.gz` from the [GitHub Releases page](https://github.com/fgravato/lookout-mrav2-syslog-connector-V2/releases) and install with pip:

```bash
pip install mrav2_syslog_connector-2.6.12.tar.gz
```

Then run directly:

```bash
cp config.ini.example config.ini
vi config.ini
mrav2-syslog-connector --config config.ini --log-file /var/log/mrav2-connector.log
```

### Option 3: Docker (recommended for containerised deployments)

```bash
docker pull ghcr.io/fgravato/lookout-mrav2-syslog-connector-v2:v2.6.12
docker run -d \
  --name mrav2-connector \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/fgravato/lookout-mrav2-syslog-connector-v2:v2.6.12
```

### Option 4: System-wide Linux install (.deb / shell)

See [`packaging/README.md`](packaging/README.md) for `.deb`, RPM, and systemd service instructions.

## Configuration

1. **Copy the example configuration file:**

```bash
cp config.ini.example config.ini
```

2. **Edit `config.ini` with your settings:**

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
host = syslog.corp.internal
port = 514
forwarder_type = qradar   # qradar or splunk
use_udp = false            # false = TCP (recommended), true = UDP

[proxy]
# Leave empty if no proxy is needed
address =
username =
password =
```

### Configuration Options

#### [lookout] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `entity_name` | Your Lookout tenant/entity name | Yes | — |
| `api_domain` | Lookout API domain URL | Yes | — |
| `api_key` | OAuth2 API key / client credentials | Yes | — |
| `threat_enabled` | Enable threat event streaming | No | true |
| `device_enabled` | Enable device event streaming | No | true |
| `audit_enabled` | Enable audit event streaming | No | false |
| `stream_position` | Stream position to resume from | No | 0 |
| `start_time` | ISO timestamp to start from (if `stream_position=0`) | No | — |

#### [syslog] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `host` | Syslog server hostname/IP | Yes | localhost |
| `port` | Syslog server port | Yes | 514 |
| `forwarder_type` | `qradar` (LEEF 2.0) or `splunk` (JSON) | No | qradar |
| `use_udp` | `false` = TCP (recommended), `true` = UDP | No | false |
| `log_identifier_key` | Custom identifier key added to events (QRadar only) | No | — |
| `log_identifier` | Custom identifier value added to events (QRadar only) | No | — |

#### [proxy] Section

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `address` | Proxy URL (e.g., `http://proxy:8080`) | No | — |
| `username` | Proxy authentication username | No | — |
| `password` | Proxy authentication password | No | — |

## Usage

### Running the Connector

#### Using control scripts (standalone install)

```bash
# Start the connector in the background
./start-connector.sh

# Check status
./status-connector.sh

# Stop the connector
./stop-connector.sh

# Restart the connector
./restart-connector.sh
```

Logs are written to `logs/mrav2-connector.log` within the installation directory.

#### Manual execution

```bash
# Foreground (useful for debugging)
./mrav2-connector --config config.ini --log-file logs/connector.log

# With verbose logging
./mrav2-connector --config config.ini --verbose
```

The `./mrav2-connector` wrapper automatically uses the virtual environment created by `install.sh`.

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
ExecStart=/opt/mrav2-connector/venv/bin/mrav2-syslog-connector \
    --config /opt/mrav2-connector/config.ini \
    --log-file /var/log/mrav2-connector/connector.log
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
        <string>/Users/youruser/mrav2-connector/venv/bin/mrav2-syslog-connector</string>
        <string>--config</string>
        <string>/Users/youruser/mrav2-connector/config.ini</string>
        <string>--log-file</string>
        <string>/Users/youruser/mrav2-connector/logs/connector.log</string>
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

```bash
# View real-time logs
tail -f logs/mrav2-connector.log

# Search for errors
grep ERROR logs/mrav2-connector.log

# Confirm startup
grep "started successfully" logs/mrav2-connector.log
```

### Health Checks

```bash
# Check process status
./status-connector.sh

# Manual check
ps aux | grep mrav2-syslog-connector

# Verify syslog port is reachable
nc -zv <syslog_host> <port>
```

### Key Log Messages

| Message | Meaning |
|---------|---------|
| `MRAv2 Syslog Connector started successfully` | Connector running |
| `Using QRadar event forwarder to host:port (TCP)` | QRadar path active |
| `Using Splunk event forwarder to host:port (TCP)` | Splunk path active |
| `received heartbeat` | SSE connection alive (debug mode) |
| `Restarting MRA v2 stream` | Auto-reconnection triggered |
| `Access token expired, refreshing token` | OAuth token refresh |

## Scaling

### Multi-tenant Deployment

Run multiple instances with separate config files:

```bash
mrav2-syslog-connector --config tenant1.ini --log-file tenant1.log &
mrav2-syslog-connector --config tenant2.ini --log-file tenant2.log &
```

### Performance Tuning

- **Network Bandwidth**: Each tenant typically uses ~1–5 Mbps depending on event volume
- **Memory**: ~50–100 MB per tenant thread
- **CPU**: Minimal — I/O-bound workload
- **Stream Position**: Automatically tracked to prevent duplicate events on restart

### Capacity Guidelines

| Devices | Tenants | Recommended Resources |
|---------|---------|----------------------|
| 10k | 1–5 | 2 CPU, 2 GB RAM |
| 30k | 1–5 | 2 CPU, 4 GB RAM |
| 50k+ | 5–10 | 4 CPU, 8 GB RAM |

## Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to MRA v2`

- Verify `api_domain` is correct (`https://api.lookout.com`)
- Check network connectivity to Lookout API
- Verify proxy settings if behind a proxy
- Check firewall rules allow outbound HTTPS

### Authentication Issues

**Problem**: `Access token expired` or OAuth errors

- Verify `api_key` is correct and not revoked
- Ensure system clock is accurate (NTP)

### Syslog Forwarding Issues

**Problem**: Events not appearing in SIEM

- Verify syslog server is listening: `nc -zv <host> <port>`
- Check firewall allows outbound TCP/UDP to the syslog port
- Confirm `forwarder_type` matches your SIEM (`qradar` → LEEF, `splunk` → JSON)
- For Splunk: ensure the Universal Forwarder or HEC receiver is configured to accept syslog input on the configured port
- Check SIEM ingestion rules and index filters

### Stream Position Reset

**Problem**: Duplicate events after restart

- Ensure `stream_position` in `config.ini` is being updated (check file write permissions)
- Do not run two instances against the same `config.ini`

## Development

### Project Structure

```
lookout_mra_client/
├── main.py                   # Main entry point and CLI
├── mra_v2_stream.py          # SSE stream client
├── mra_v2_stream_thread.py   # Thread wrapper
├── sse_client.py             # SSE protocol implementation
├── oauth2_client.py          # OAuth2 authentication
├── syslog_client.py          # Syslog TCP/UDP sender
├── event_forwarders/
│   ├── event_forwarder.py    # Base class
│   ├── qradar_event_forwarder.py   # LEEF 2.0 → syslog
│   └── splunk_event_forwarder.py   # JSON → syslog
├── event_translators/        # LEEF formatters
├── event_store/              # Stream position persistence
└── models/                   # Data models
```

### Running Tests

**1. Install development dependencies:**

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**2. Run tests:**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=lookout_mra_client

# Run specific test file
pytest tests/test_event_forwarders.py

# Run with verbose output
pytest -v
```

**3. Code quality checks:**

```bash
mypy lookout_mra_client/ --ignore-missing-imports
flake8 lookout_mra_client/
black lookout_mra_client/ tests/
```

### Test Coverage

- Configuration loading and parsing
- Event type parsing
- Proxy configuration
- QRadar forwarder: persistent client, idle reconnect, SMISHING flattening
- Splunk forwarder: JSON syslog transport, reconnect, no stdout output
- LEEF translator: MRA v1 and v2 formats, missing/null/empty field guards
- Logger initialization
- Stream thread behaviour

## Docker

### Building the Docker Image

```bash
docker build -t mrav2-syslog-connector:latest .
docker build -f Dockerfile.test -t mrav2-syslog-connector:test .
```

### Running with Docker

```bash
cp config.ini.example config.ini
# edit config.ini with your credentials

docker run -d \
  --name mrav2-connector \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/fgravato/lookout-mrav2-syslog-connector-v2:v2.6.12
```

View logs:

```bash
docker logs -f mrav2-connector
```

### Using Docker Compose

```bash
# Start with local syslog server for testing
docker-compose up -d

# Run tests in Docker
docker-compose run --rm test

# View logs
docker-compose logs -f connector

# Stop
docker-compose down
```

## CI/CD

Every push and pull request triggers:

1. **Tests** — pytest across Python 3.8–3.12
2. **Type Checking** — mypy
3. **Linting** — flake8
4. **Docker Build** — validates image builds successfully
5. **Security Scan** — bandit

### Releasing

To cut a new release:

```bash
# Bump version in setup.py and packaging/Makefile, then:
git add setup.py packaging/Makefile
git commit -m "Bump version to X.Y.Z"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

GitHub Actions will automatically:
- Build and push a multi-arch Docker image to `ghcr.io/fgravato/lookout-mrav2-syslog-connector-v2:vX.Y.Z`
- Create a GitHub Release with the Python source distribution attached

### Local CI Testing

```bash
pytest
mypy lookout_mra_client/ --ignore-missing-imports
flake8 lookout_mra_client/
bandit -r lookout_mra_client/
docker build -t mrav2-syslog-connector:test .
```

## License

See [LICENSE](LICENSE) for details.

## Support

For issues or questions:
- Check the logs first: `tail -f logs/mrav2-connector.log`
- Review this README and `config.ini.example`
- Open an issue at [github.com/fgravato/lookout-mrav2-syslog-connector-V2/issues](https://github.com/fgravato/lookout-mrav2-syslog-connector-V2/issues)

## Version History

- **2.6.12** — Fix Splunk forwarder (JSON over syslog TCP/UDP, not stdout); persist QRadar SyslogClient across batches with idle reconnect; harden LEEF translator against malformed events; 87-test suite
- **2.6.11** — Source distribution release improvements
- **2.6.10** — Version bump and packaging updates
- **2.6.9** — Merged SMISHING_ALERT feature from upstream
- **2.6.8** — Added comprehensive test suite, Docker support, CI/CD pipeline, Linux packaging
- **2.6.7** — Renamed to MRAv2 Syslog Connector, removed demo scripts, added packaging

---

**Note**: This connector is designed for production use and can handle high-volume event streaming. For optimal performance, ensure your syslog server can handle the expected event throughput.
