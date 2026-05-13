"""Arc manager agent."""

import logging
import json
from typing import Any, Dict

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance
from src.core.file_io import write_json, read_file
from pathlib import Path

logger = logging.getLogger(__name__)


class ArcManager(Agent):
    """Break novel into arcs and generate structure."""

    def run(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate novel plan and arc structures.
        
        Args:
            context: {"constitution": str, "world": str, "idea": str}
            prompt_template: Template string with {constitution}, {world}, {idea}
            config: Full config dict
            
        Returns:
            {"novel_plan": dict}
        """
        logger.info("[plan:arc] Generating novel plan...")
        
        try:
            constitution = context.get("constitution", "")
            world = context.get("world", "")
            idea = context.get("idea", "")
            
            prompt = prompt_template.format(constitution=constitution, world=world, idea=idea)
            
            agent_config = config.get("agents", {}).get("arc_manager", {})
            provider_name = agent_config.get("provider", "anthropic")
            provider = get_provider_instance(provider_name, config)
            
            result = call_llm(
                provider=provider,
                prompt=prompt,
                expect_json=True,
                max_tokens=config.get("defaults", {}).get("max_tokens", 4096),
                temperature=config.get("defaults", {}).get("temperature", 1.0),
            )
            
            # Write novel_plan.json
            root = Path.cwd()
            write_json(root / "novel_plan.json", result)
            
            logger.info("[plan:arc] ✓ Novel plan generated")
            
            return {"novel_plan": result}
        except Exception as e:
            logger.error(f"[plan:arc] Failed: {e}")
            raise

