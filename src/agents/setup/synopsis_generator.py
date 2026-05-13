"""Synopsis generator agent."""

import logging
from typing import Any, Dict, List

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance
from src.core.schema import SynopsisCandidate
from src.core.file_io import write_json
from pathlib import Path

logger = logging.getLogger(__name__)


class SynopsisGenerator(Agent):
    """Generate story concept candidates."""

    def run(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate synopsis candidates.
        
        Args:
            context: {"idea": str}
            prompt_template: Prompt template with {idea} placeholder
            config: Full config dict
            
        Returns:
            List of synopsis candidate dicts
        """
        logger.info("[setup:synopsis] Generating synopsis candidates...")
        
        # Prepare prompt
        idea = context.get("idea", "")
        prompt = prompt_template.format(idea=idea)
        
        # Get provider
        agent_config = config.get("agents", {}).get("synopsis_generator", {})
        provider_name = agent_config.get("provider", "anthropic")
        provider = get_provider_instance(provider_name, config)
        
        # Call LLM
        result = call_llm(
            provider=provider,
            prompt=prompt,
            expect_json=True,
            max_tokens=config.get("defaults", {}).get("max_tokens", 4096),
            temperature=config.get("defaults", {}).get("temperature", 1.0),
        )
        
        # Parse and return candidates
        candidates = result.get("candidates", [])
        logger.info(f"[setup:synopsis] Generated {len(candidates)} synopsis candidates")
        
        return candidates

