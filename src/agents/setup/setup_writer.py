"""Setup writer agent."""

import logging
import yaml
from typing import Any, Dict

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance
from src.core.file_io import write_file, write_json
from pathlib import Path

logger = logging.getLogger(__name__)


class SetupWriter(Agent):
    """Write constitution and world files."""

    def run(self, context: Dict[str, Any], prompt_templates: Dict[str, str], config: Dict[str, Any]) -> Dict[str, str]:
        """Write setup artifacts.
        
        Args:
            context: {"synopsis": str, "world": str, "idea": str}
            prompt_templates: {"constitution": template, "world_yaml": template}
            config: Full config dict
            
        Returns:
            {"constitution": str, "world_yaml": str}
        """
        logger.info("[setup:writer] Writing setup artifacts...")
        
        try:
            # Generate constitution
            logger.info("[setup:writer] Generating constitution...")
            constitution = self._generate_constitution(context, prompt_templates["constitution"], config)
            
            # Generate world YAML
            logger.info("[setup:writer] Generating world YAML...")
            world_yaml = self._generate_world_yaml(context, prompt_templates["world_yaml"], config)
            
            # Write files
            root = Path.cwd()
            write_file(root / "constitution.md", constitution)
            write_file(root / "world.yaml", world_yaml)
            
            logger.info("[setup:writer] SUCCESS: Setup artifacts written")
            
            return {
                "constitution": constitution,
                "world_yaml": world_yaml,
            }
        except Exception as e:
            logger.error(f"[setup:writer] Failed to write setup artifacts: {e}")
            raise

    def _generate_constitution(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any]) -> str:
        """Generate constitution markdown."""
        synopsis = context.get("synopsis", "")
        world = context.get("world", "")
        idea = context.get("idea", "")
        
        prompt = prompt_template.format(synopsis=synopsis, world=world, idea=idea)
        
        agent_config = config.get("agents", {}).get("setup_writer", {})
        provider_name = agent_config.get("provider", "anthropic")
        provider = get_provider_instance(provider_name, config)
        
        result = call_llm(
            provider=provider,
            prompt=prompt,
            expect_json=False,
            max_tokens=config.get("defaults", {}).get("max_tokens", 4096),
            temperature=config.get("defaults", {}).get("temperature", 1.0),
        )
        
        return result

    def _generate_world_yaml(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any]) -> str:
        """Generate world YAML."""
        world = context.get("world", "")
        
        prompt = prompt_template.format(world_desc=world)
        
        agent_config = config.get("agents", {}).get("setup_writer", {})
        provider_name = agent_config.get("provider", "anthropic")
        provider = get_provider_instance(provider_name, config)
        
        result = call_llm(
            provider=provider,
            prompt=prompt,
            expect_json=False,
            max_tokens=config.get("defaults", {}).get("max_tokens", 2048),
            temperature=config.get("defaults", {}).get("temperature", 1.0),
        )
        
        return result

