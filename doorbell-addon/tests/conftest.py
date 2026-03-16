"""Shared pytest fixtures for WhoRang tests."""
import os
import sys

# Make src importable as both 'src.module' and 'module'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
