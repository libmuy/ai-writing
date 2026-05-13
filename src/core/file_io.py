"""File I/O operations for novel workspace."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def read_json(file_path: Path) -> Dict[str, Any]:
    """Read JSON file."""
    try:
        with open(file_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON from {file_path}: {e}")
        raise


def write_json(file_path: Path, data: Dict[str, Any], pretty: bool = True):
    """Write JSON file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "w") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        logger.info(f"Wrote JSON to {file_path}")
    except Exception as e:
        logger.error(f"Failed to write JSON to {file_path}: {e}")
        raise


def read_file(file_path: Path) -> str:
    """Read text file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def write_file(file_path: Path, content: str):
    """Write text file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote file to {file_path}")
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        raise


def file_exists(file_path: Path) -> bool:
    """Check if file exists."""
    return file_path.exists()
