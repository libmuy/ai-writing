"""Runtime state management."""

from typing import Any, Dict, Optional


class RuntimeState:
    """Minimal runtime state container."""

    def __init__(self):
        """Initialize runtime state."""
        self.novel_plan: Optional[Dict[str, Any]] = None
        self.chapter_plan: Optional[Dict[str, Any]] = None
        self.characters: Dict[str, Any] = {}
        self.world: Dict[str, Any] = {}
        self.constitution: str = ""
        self.chapter_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state."""
        return {
            "novel_plan": self.novel_plan,
            "chapter_plan": self.chapter_plan,
            "characters": self.characters,
            "world": self.world,
            "constitution": self.constitution,
            "chapter_index": self.chapter_index,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RuntimeState":
        """Deserialize state."""
        state = RuntimeState()
        state.novel_plan = data.get("novel_plan")
        state.chapter_plan = data.get("chapter_plan")
        state.characters = data.get("characters", {})
        state.world = data.get("world", {})
        state.constitution = data.get("constitution", "")
        state.chapter_index = data.get("chapter_index", 0)
        return state
