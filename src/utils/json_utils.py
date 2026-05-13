"""JSON utilities with retry logic."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def parse_json_with_retry(raw_output: str, provider, original_prompt: str, max_retries: int = 1) -> Any:
    """Parse JSON with retry on failure.
    
    Args:
        raw_output: Raw LLM output
        provider: Provider instance for retry
        original_prompt: Original prompt for retry
        max_retries: Number of retries (Phase 1: default 1)
        
    Returns:
        Parsed JSON object
    """
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}")
        
        if max_retries > 0:
            logger.info(f"Retrying JSON parse ({max_retries} retries left)...")
            
            retry_prompt = (
                f"{original_prompt}\n\n"
                "Please output ONLY valid JSON, no markdown, no explanation."
            )
            
            retry_output = provider.call(
                prompt=retry_prompt,
                expect_json=False,
                max_tokens=4096,
                temperature=0.7,
            )
            
            try:
                return json.loads(retry_output)
            except json.JSONDecodeError:
                logger.error("JSON parse retry failed")
                raise
        else:
            logger.error("No retries left for JSON parse")
            raise
