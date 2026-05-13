"""Base agent class."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Agent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize agent.
        
        Args:
            name: Agent identifier
            config: Configuration dict (provider, model, etc.)
        """
        self.name = name
        self.config = config

    @abstractmethod
    def run(self, context: Dict[str, Any], prompt_template: str) -> Any:
        """Execute agent logic.
        
        Args:
            context: Context dict (constitution, world, etc.)
            prompt_template: Prompt template with variables
            
        Returns:
            Agent output (string, JSON object, etc.)
        """
        pass
