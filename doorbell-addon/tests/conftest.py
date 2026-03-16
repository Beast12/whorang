"""Shared pytest fixtures for WhoRang tests."""
import os
import sys

# Make src importable as both 'src.module' and 'module'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Point storage to /tmp so module-level singletons (e.g. db = DatabaseManager())
# can initialise without needing /share/doorbell to exist.
os.environ.setdefault("STORAGE_PATH", "/tmp/whorang-test")
