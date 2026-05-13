"""Workspace layout and initialization."""

import logging
from pathlib import Path

from src.utils.constants import (
    CONFIG_FILE, ENV_FILE, CONSTITUTION_FILE, WORLD_FILE,
    SETUP_DIR, CHARACTERS_DIR, ARCS_DIR, CHAPTERS_DIR, LOGS_DIR
)

logger = logging.getLogger(__name__)


def get_workspace_root() -> Path:
    """Get novel workspace root (CWD)."""
    return Path.cwd()


def get_subdir(subdir: str) -> Path:
    """Get subdirectory path."""
    return get_workspace_root() / subdir


def init_workspace():
    """Initialize workspace directory structure."""
    root = get_workspace_root()
    
    # Create directories
    dirs = [
        root / SETUP_DIR,
        root / CHARACTERS_DIR,
        root / ARCS_DIR,
        root / CHAPTERS_DIR,
        root / LOGS_DIR,
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(exist_ok=True)
        logger.info(f"Created directory: {dir_path}")
    
    # Create template files if they don't exist
    config_path = root / CONFIG_FILE
    if not config_path.exists():
        _create_template_config(config_path)
    
    env_path = root / ENV_FILE
    if not env_path.exists():
        _create_template_env(env_path)
    
    logger.info("Workspace initialized")


def _create_template_config(path: Path):
    """Create template config.yaml."""
    template = """providers:
  anthropic:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
  deepseek:
    type: openai
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1

agents:
  synopsis_generator: { provider: anthropic, model: claude-3-sonnet-20240229 }
  world_generator:    { provider: anthropic, model: claude-3-sonnet-20240229 }
  setup_writer:       { provider: anthropic, model: claude-3-sonnet-20240229 }
  chapter_planner:    { provider: anthropic, model: claude-3-sonnet-20240229 }
  scene_generator:    { provider: anthropic, model: claude-3-sonnet-20240229 }

defaults:
  max_tokens: 4096
  temperature: 1.0
  json_retry_limit: 1
"""
    path.write_text(template)
    logger.info(f"Created template config at {path}")


def _create_template_env(path: Path):
    """Create template .env."""
    template = """ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
"""
    path.write_text(template)
    logger.info(f"Created template .env at {path}")
