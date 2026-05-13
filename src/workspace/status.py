"""Workspace status checking."""

import logging
from pathlib import Path
from typing import Dict

from src.utils.constants import (
    CONFIG_FILE, CONSTITUTION_FILE, WORLD_FILE, NOVEL_PLAN_FILE,
    ARCS_DIR, CHAPTERS_DIR
)
from src.workspace.layout import get_workspace_root

logger = logging.getLogger(__name__)


def check_status() -> Dict[str, bool]:
    """Check workspace progress status.
    
    Returns:
        Dict with status keys and boolean values
    """
    root = get_workspace_root()
    
    status = {
        "init": (root / CONFIG_FILE).exists(),
        "setup": (root / CONSTITUTION_FILE).exists() and (root / WORLD_FILE).exists(),
        "novel_plan": (root / NOVEL_PLAN_FILE).exists(),
        "arc_plan": _has_arc_plans(root),
        "chapter_plans": _has_chapter_plans(root),
        "chapters": _get_chapter_count(root),
    }
    
    return status


def format_status(status: Dict[str, bool]) -> str:
    """Format status for display.
    
    Returns:
        Status string like "[✓] init | [ ] setup | ..."
    """
    parts = []
    for key, value in status.items():
        check = "✓" if value else " "
        parts.append(f"[{check}] {key}")
    
    return " | ".join(parts)


def _has_arc_plans(root: Path) -> bool:
    """Check if any arc plans exist."""
    arcs_dir = root / ARCS_DIR
    if not arcs_dir.exists():
        return False
    
    for arc_dir in arcs_dir.glob("arc_*"):
        if (arc_dir / "arc_plan.json").exists():
            return True
    
    return False


def _has_chapter_plans(root: Path) -> bool:
    """Check if any chapter plans exist."""
    arcs_dir = root / ARCS_DIR
    if not arcs_dir.exists():
        return False
    
    for plan_file in arcs_dir.glob("*/ch_*_plan.json"):
        return True
    
    return False


def _get_chapter_count(root: Path) -> int:
    """Count generated chapters."""
    chapters_dir = root / CHAPTERS_DIR
    if not chapters_dir.exists():
        return 0
    
    return len(list(chapters_dir.glob("ch_*.md")))
