"""Base provider class."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize provider.
        
        Args:
            name: Provider identifier
            config: Configuration (api_key_env, model, etc.)
        """
        self.name = name
        self.config = config

    @abstractmethod
    def call(self, prompt: str, expect_json: bool = False, max_tokens: int = 4096, temperature: float = 1.0) -> Any:
        """Make LLM call.
        
        Args:
            prompt: Prompt text
            expect_json: If True, retry on JSON parse failure
            max_tokens: Max tokens in response
            temperature: Temperature (0-2)
            
        Returns:
            String or parsed JSON object
        """
        pass
