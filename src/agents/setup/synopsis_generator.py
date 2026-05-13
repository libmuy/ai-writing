"""Synopsis generator agent."""

from src.agents import Agent
from typing import Any, Dict


class SynopsisGenerator(Agent):
    """Generate story concept candidates."""

    def run(self, context: Dict[str, Any], prompt_template: str) -> Any:
        """Generate synopsis candidates.
        
        Args:
            context: {"idea": str}
            prompt_template: Jinja template or simple template
            
        Returns:
            List of synopsis candidates
        """
        # TODO: Implement synopsis generation
        pass
