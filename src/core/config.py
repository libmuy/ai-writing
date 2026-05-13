"""Configuration loading."""

import os
import logging
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from src.core.errors import ConfigError

logger = logging.getLogger(__name__)


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """Load config.yaml from CWD or specified path."""
    if config_path is None:
        config_path = Path.cwd() / "config.yaml"
    
    if not config_path.exists():
        raise ConfigError(f"config.yaml not found at {config_path}")
    
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded config from {config_path}")
        return config
    except Exception as e:
        raise ConfigError(f"Failed to load config: {e}")


def load_env(env_path: Path = None):
    """Load .env file."""
    if env_path is None:
        env_path = Path.cwd() / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env from {env_path}")
    else:
        logger.warning(f".env not found at {env_path}")


def validate_provider_keys(config: Dict[str, Any]):
    """Validate that required provider keys are present."""
    providers = config.get("providers", {})
    
    for provider_name, provider_config in providers.items():
        provider_type = provider_config.get("type")
        # Mock provider does not require API keys
        if provider_type == "mock":
            continue

        api_key_env = provider_config.get("api_key_env")

        if not api_key_env:
            raise ConfigError(f"Provider {provider_name} missing api_key_env")

        if not os.getenv(api_key_env):
            raise ConfigError(f"Environment variable {api_key_env} not set for provider {provider_name}")
    
    logger.info("Provider keys validated")


def get_provider_instance(provider_name: str, config: Dict[str, Any]):
    """Get provider instance by name.
    
    Args:
        provider_name: Name of provider (e.g., 'anthropic')
        config: Full config dict
        
    Returns:
        Provider instance
    """
    provider_config = config.get("providers", {}).get(provider_name)
    
    if not provider_config:
        raise ConfigError(f"Provider {provider_name} not found in config")
    
    provider_type = provider_config.get("type")
    
    if provider_type == "anthropic":
        from src.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(provider_name, provider_config)
    elif provider_type == "openai":
        from src.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(provider_name, provider_config)
    elif provider_type == "mock":
        from src.providers.mock_provider import MockProvider
        return MockProvider(provider_name, provider_config)
    else:
        raise ConfigError(f"Unknown provider type: {provider_type}")
