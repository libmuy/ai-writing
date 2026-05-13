"""Anthropic provider."""

import os
import json
import logging
from typing import Any, Dict

from src.providers import BaseProvider
from src.utils.json_utils import parse_json_with_retry

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize Anthropic provider."""
        super().__init__(name, config)
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=os.getenv(config.get("api_key_env", "ANTHROPIC_API_KEY")))
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")

    def call(self, prompt: str, expect_json: bool = False, max_tokens: int = 4096, temperature: float = 1.0) -> Any:
        """Make Anthropic API call."""
        model = self.config.get("model", "claude-3-sonnet-20240229")
        
        logger.info(f"Calling Anthropic {model}...")
        
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            result = message.content[0].text
            
            if expect_json:
                return parse_json_with_retry(result, self.client, prompt)
            return result
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
