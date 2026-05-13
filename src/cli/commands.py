"""Command handlers for CLI."""

import logging

logger = logging.getLogger(__name__)


def init_cmd():
    """Initialize novel workspace."""
    logger.info("Initializing novel workspace...")
    # TODO: Implement init logic
    pass


def status_cmd():
    """Show workspace status."""
    logger.info("Showing workspace status...")
    # TODO: Implement status logic
    pass


def setup_cmd(mode: str, idea: str = None):
    """Setup novel world and constitution.
    
    Args:
        mode: 'full', 'constitution', or 'world'
        idea: Novel idea (required for full setup)
    """
    logger.info(f"Running setup in {mode} mode...")
    # TODO: Implement setup logic
    pass


def plan_cmd(target: str, range_str: str = None):
    """Plan novel structure.
    
    Args:
        target: 'novel', 'arc', or 'chapter'
        range_str: Range string (e.g., '1-3')
    """
    logger.info(f"Planning {target}...")
    # TODO: Implement planning logic
    pass


def generate_cmd(range_str: str = None):
    """Generate chapter(s).
    
    Args:
        range_str: Chapter range (e.g., '1-3'); auto-resume if None
    """
    logger.info(f"Generating chapters...")
    # TODO: Implement generation logic
    pass
