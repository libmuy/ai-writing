"""World generator agent."""

import logging
from typing import Any, Dict, List

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance

logger = logging.getLogger(__name__)


class WorldGenerator(Agent):
    """Generate world candidates."""

    def run(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate world candidates.
        
        Args:
            context: {"synopsis": str}
            prompt_template: Template string with {synopsis} placeholder
            config: Full config dict
            
        Returns:
            List of world candidate dicts
        """
        logger.info("[setup:world] Generating world candidates...")
        
        # Prepare prompt
        synopsis = context.get("synopsis", "")
        prompt = prompt_template.format(synopsis=synopsis)
        
        # Get provider
        agent_config = config.get("agents", {}).get("world_generator", {})
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
        logger.info(f"[setup:world] Generated {len(candidates)} world candidates")
        
        return candidates

