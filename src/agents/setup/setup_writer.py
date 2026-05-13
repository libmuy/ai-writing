"""Setup writer agent."""

from src.agents import Agent
from typing import Any, Dict


class SetupWriter(Agent):
    """Write constitution and world files."""

    def run(self, context: Dict[str, Any], prompt_template: str) -> Any:
        """Write setup artifacts.
        
        Args:
            context: {"synopsis": str, "world": str}
            prompt_template: Template string
            
        Returns:
            {"constitution": str, "world": str}
        """
        # TODO: Implement setup writing
        pass
