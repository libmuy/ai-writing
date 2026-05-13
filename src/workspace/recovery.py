"""Resume and recovery logic."""

import logging
from pathlib import Path

from src.core.file_io import read_json, file_exists
from src.utils.constants import NOVEL_PLAN_FILE, CHAPTERS_DIR

logger = logging.getLogger(__name__)


def find_last_generated_chapter(root: Path) -> int:
    """Find index of last generated chapter.
    
    Returns:
        Chapter number (1-indexed) or 0 if none
    """
    chapters_dir = root / CHAPTERS_DIR
    
    if not chapters_dir.exists():
        return 0
    
    chapters = sorted(chapters_dir.glob("ch_*.md"))
    
    if chapters:
        # Extract chapter number from filename (ch_NNN.md)
        last_chapter_file = chapters[-1]
        chapter_num = int(last_chapter_file.stem.split("_")[1])
        return chapter_num
    
    return 0


def get_total_chapters(root: Path) -> int:
    """Get total planned chapters from novel_plan.json."""
    novel_plan_path = root / NOVEL_PLAN_FILE
    
    if not novel_plan_path.exists():
        return 0
    
    try:
        plan = read_json(novel_plan_path)
        return plan.get("total_chapters", 0)
    except Exception as e:
        logger.error(f"Failed to read total chapters: {e}")
        return 0
