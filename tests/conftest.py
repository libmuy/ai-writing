"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import MagicMock


@pytest.fixture
def temp_workspace():
    """Create temporary novel workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    provider = MagicMock()
    provider.name = "mock"
    provider.call.return_value = '{"test": "data"}'
    return provider


@pytest.fixture
def sample_config():
    """Sample config dict."""
    return {
        "providers": {
            "anthropic": {
                "type": "anthropic",
                "api_key_env": "ANTHROPIC_API_KEY",
                "model": "claude-3-sonnet-20240229",
            }
        },
        "agents": {
            "synopsis_generator": {"provider": "anthropic"},
        },
        "defaults": {
            "max_tokens": 4096,
            "temperature": 1.0,
        },
    }
