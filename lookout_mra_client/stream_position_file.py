"""
Standalone stream position tracking.

Analogous to a PID file: written at runtime by the connector, consulted at
startup to resume without replaying events, and ignored if absent.  The
position is stored in a small JSON file that lives next to config.ini (or at
a path the operator specifies) and is never merged back into config.ini.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

from .lookout_logger import LOGGER_NAME


class StreamPositionFile:
    """Atomic read/write of a stream position state file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.logger = logging.getLogger(LOGGER_NAME)

    def read(self) -> Optional[str]:
        """Return the saved stream position, or None if absent or unset."""
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r") as fh:
                data = json.load(fh)
            position = data.get("stream_position", "")
            return str(position) if position and str(position) != "0" else None
        except (OSError, ValueError) as e:
            self.logger.warning(f"Could not read stream position file {self.path}: {e}")
            return None

    def write(self, position: str, entity_name: str = "") -> None:
        """Atomically persist the current stream position.

        Writes to a temp file in the same directory then renames it so that a
        crash mid-write never leaves a truncated or corrupt state file.
        """
        payload = {
            "stream_position": position,
            "entity_name": entity_name,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        directory = os.path.dirname(os.path.abspath(self.path))
        try:
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".stream_pos_tmp_")
            try:
                with os.fdopen(fd, "w") as fh:
                    json.dump(payload, fh, indent=2)
                    fh.write("\n")
                os.replace(tmp_path, self.path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            self.logger.error(f"Could not write stream position file {self.path}: {e}")

    def clear(self) -> None:
        """Delete the position file, forcing a replay from start_time on the next start."""
        try:
            os.unlink(self.path)
            self.logger.info(f"Stream position file cleared: {self.path}")
        except FileNotFoundError:
            pass
        except OSError as e:
            self.logger.error(f"Could not clear stream position file {self.path}: {e}")

    def exists(self) -> bool:
        """Return True if the position file is present on disk."""
        return os.path.exists(self.path)
