"""Ensure DATABASE_PATH is set before the app imports config (pytest loads conftest first)."""
import atexit
import os
import tempfile

_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_PATH"] = _TEST_DB_PATH


def _cleanup_db_file() -> None:
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass


atexit.register(_cleanup_db_file)
