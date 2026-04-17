#!/usr/bin/env python3
"""
Simple TCP syslog listener for testing the MRAv2 connector.

Prints each newline-delimited syslog message to stdout as it arrives.
Compatible with the connector's TCP framing (each record ends with \n).

Usage:
    python3 syslog-listener.py [port]   # default port: 514

    # Low port — requires sudo or use a high port for local testing:
    sudo python3 syslog-listener.py 514
    python3 syslog-listener.py 5514
"""
import socket
import sys
import threading
from datetime import datetime


def handle_connection(conn, addr):
    """Read newline-delimited syslog records from a single TCP connection."""
    print(f"[connected] {addr[0]}:{addr[1]}", flush=True)
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            # Each syslog record from the connector ends with \n
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] {msg}", flush=True)
    except Exception as e:
        print(f"[error] {addr}: {e}", flush=True)
    finally:
        conn.close()
        print(f"[disconnected] {addr[0]}:{addr[1]}", flush=True)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 514

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(50)

    print(f"TCP syslog listener ready on 0.0.0.0:{port}", flush=True)
    print("Waiting for events (Ctrl+C to stop)...\n", flush=True)

    while True:
        try:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_connection, args=(conn, addr), daemon=True)
            t.start()
        except KeyboardInterrupt:
            print("\nStopping listener.")
            break
        except Exception as e:
            print(f"[accept error] {e}", flush=True)

    server.close()


if __name__ == "__main__":
    main()
