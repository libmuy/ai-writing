"""Logging setup."""

import logging
from pathlib import Path


def setup_logging(log_dir: Path = None):
    """Setup logging to file and console."""
    if log_dir is None:
        log_dir = Path.cwd() / "logs"
    
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "latest.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to {log_file}")
