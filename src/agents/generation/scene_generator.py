"""Scene generator agent."""

from src.agents import Agent
from typing import Any, Dict


class SceneGenerator(Agent):
    """Generate prose for chapters."""

    def run(self, context: Dict[str, Any], prompt_template: str) -> Any:
        """Generate chapter prose.
        
        Args:
            context: {"chapter_plan": dict, "constitution": str, "world": str, "characters": dict}
            prompt_template: Template string
            
        Returns:
            Chapter markdown text
        """
        # TODO: Implement scene generation
        pass
