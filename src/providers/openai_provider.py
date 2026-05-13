"""OpenAI provider (covers OpenAI and OpenAI-compatible services)."""

import os
import json
import logging
from typing import Any, Dict

from src.providers import BaseProvider
from src.utils.json_utils import parse_json_with_retry

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI and OpenAI-compatible (e.g., DeepSeek) provider."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize OpenAI provider."""
        super().__init__(name, config)
        try:
            from openai import OpenAI
            
            api_key = os.getenv(config.get("api_key_env", "OPENAI_API_KEY"))
            base_url = config.get("base_url", "https://api.openai.com/v1")
            
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def call(self, prompt: str, expect_json: bool = False, max_tokens: int = 4096, temperature: float = 1.0) -> Any:
        """Make OpenAI API call."""
        model = self.config.get("model", "gpt-4")
        
        logger.info(f"Calling OpenAI {model}...")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            
            result = response.choices[0].message.content
            
            if expect_json:
                return parse_json_with_retry(result, self.client, prompt)
            return result
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
