"""
Tests for StreamPositionFile.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.stream_position_file import StreamPositionFile


@pytest.fixture
def state_path(tmp_path):
    return str(tmp_path / "test.state")


# ---------------------------------------------------------------------------
# read()
# ---------------------------------------------------------------------------

class TestStreamPositionFileRead:
    def test_returns_none_when_file_absent(self, state_path):
        assert StreamPositionFile(state_path).read() is None

    def test_returns_position_from_valid_file(self, state_path):
        data = {
            "stream_position": "abc-123-uuid",
            "entity_name": "test",
            "last_updated": "2024-01-01T00:00:00+00:00",
        }
        with open(state_path, "w") as fh:
            json.dump(data, fh)
        assert StreamPositionFile(state_path).read() == "abc-123-uuid"

    def test_returns_none_for_zero_position(self, state_path):
        with open(state_path, "w") as fh:
            json.dump({"stream_position": "0"}, fh)
        assert StreamPositionFile(state_path).read() is None

    def test_returns_none_for_empty_position(self, state_path):
        with open(state_path, "w") as fh:
            json.dump({"stream_position": ""}, fh)
        assert StreamPositionFile(state_path).read() is None

    def test_returns_none_on_malformed_json(self, state_path):
        with open(state_path, "w") as fh:
            fh.write("not-json{{{")
        assert StreamPositionFile(state_path).read() is None

    def test_returns_none_when_key_missing(self, state_path):
        with open(state_path, "w") as fh:
            json.dump({"entity_name": "test"}, fh)
        assert StreamPositionFile(state_path).read() is None


# ---------------------------------------------------------------------------
# write()
# ---------------------------------------------------------------------------

class TestStreamPositionFileWrite:
    def test_creates_file_on_first_write(self, state_path):
        StreamPositionFile(state_path).write("uuid-001", "my-ent")
        assert os.path.exists(state_path)

    def test_written_file_contains_position(self, state_path):
        StreamPositionFile(state_path).write("uuid-abc", "ent-x")
        with open(state_path) as fh:
            data = json.load(fh)
        assert data["stream_position"] == "uuid-abc"
        assert data["entity_name"] == "ent-x"
        assert "last_updated" in data

    def test_write_is_roundtrippable(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("round-trip-uuid", "ent")
        assert spf.read() == "round-trip-uuid"

    def test_write_overwrites_previous(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("first-uuid", "ent")
        spf.write("second-uuid", "ent")
        assert spf.read() == "second-uuid"

    def test_no_temp_file_left_behind(self, tmp_path):
        spf = StreamPositionFile(str(tmp_path / "pos.state"))
        spf.write("uuid-xyz", "ent")
        leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".stream_pos_tmp_")]
        assert leftovers == []

    def test_write_without_entity_name(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("uuid-no-ent")
        assert spf.read() == "uuid-no-ent"


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

class TestStreamPositionFileClear:
    def test_clear_removes_file(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("some-uuid", "ent")
        spf.clear()
        assert not os.path.exists(state_path)

    def test_clear_on_absent_file_does_not_raise(self, state_path):
        StreamPositionFile(state_path).clear()  # must not raise

    def test_after_clear_read_returns_none(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("some-uuid", "ent")
        spf.clear()
        assert spf.read() is None


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------

class TestStreamPositionFileExists:
    def test_false_when_absent(self, state_path):
        assert not StreamPositionFile(state_path).exists()

    def test_true_after_write(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("uuid", "ent")
        assert spf.exists()

    def test_false_after_clear(self, state_path):
        spf = StreamPositionFile(state_path)
        spf.write("uuid", "ent")
        spf.clear()
        assert not spf.exists()
