"""Pytest configuration for Infinity Pools SDK tests."""

import os
from pathlib import Path

import pytest


def load_env_file(env_path):
    """Load environment variables from a .env file.
    
    Args:
        env_path: Path to the .env file
    """
    if not os.path.exists(env_path):
        return
        
    with open(env_path) as f:
        for line_content in f:
            line = line_content.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Parse key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value


# Load environment variables from .env file
env_path = '/code/infinitypools/.env'
load_env_file(env_path)


def pytest_addoption(parser):
    """Add command-line options to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require a local blockchain",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a local blockchain"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is specified."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
