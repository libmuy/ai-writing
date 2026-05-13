"""LLM call wrapper with retry logic."""

import logging
from typing import Any, Dict

from src.providers import BaseProvider
from src.utils.json_utils import parse_json_with_retry

logger = logging.getLogger(__name__)


def call_llm(
    provider: BaseProvider,
    prompt: str,
    expect_json: bool = False,
    max_tokens: int = 4096,
    temperature: float = 1.0,
) -> Any:
    """Unified LLM call wrapper.
    
    Args:
        provider: BaseProvider instance
        prompt: Prompt text
        expect_json: If True, parse JSON and retry on failure
        max_tokens: Max tokens
        temperature: Temperature
        
    Returns:
        String or parsed JSON object
    """
    logger.info(f"LLM call via {provider.name}")
    
    return provider.call(
        prompt=prompt,
        expect_json=expect_json,
        max_tokens=max_tokens,
        temperature=temperature,
    )
