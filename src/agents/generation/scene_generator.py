"""Scene generator agent."""

import logging
import json
from typing import Any, Dict

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance
from src.core.file_io import write_file, read_json, read_file
from pathlib import Path

logger = logging.getLogger(__name__)


class SceneGenerator(Agent):
    """Generate prose for chapters."""

    def run(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any], chapter_num: int) -> str:
        """Generate chapter prose.
        
        Args:
            context: {"chapter_plan": dict, "constitution": str, "world": str, "characters": dict}
            prompt_template: Template string with {chapter_plan}, {constitution}, {world}, {characters}
            config: Full config dict
            chapter_num: Chapter number to generate
            
        Returns:
            Chapter markdown text
        """
        logger.info(f"[generate:scene] Generating chapter {chapter_num}...")
        
        try:
            chapter_plan = context.get("chapter_plan", {})
            constitution = context.get("constitution", "")
            world = context.get("world", "")
            characters = context.get("characters", {})
            
            # Prepare prompt context
            scene_count = len(chapter_plan.get("scenes", []))
            target_words = 2000 + (scene_count * 500)  # Rough estimate
            
            prompt = prompt_template.format(
                chapter_plan=json.dumps(chapter_plan, indent=2),
                constitution=constitution,
                world=world,
                characters=json.dumps(characters, indent=2),
                scene_count=scene_count,
                target_words=target_words,
            )
            
            agent_config = config.get("agents", {}).get("scene_generator", {})
            provider_name = agent_config.get("provider", "anthropic")
            provider = get_provider_instance(provider_name, config)
            
            result = call_llm(
                provider=provider,
                prompt=prompt,
                expect_json=False,
                max_tokens=config.get("defaults", {}).get("max_tokens", 8192),
                temperature=config.get("defaults", {}).get("temperature", 1.0),
            )
            
            # Write chapter file
            root = Path.cwd()
            chapter_path = root / "chapters" / f"ch_{chapter_num:03d}.md"
            write_file(chapter_path, result)
            
            logger.info(f"[generate:scene] SUCCESS: Chapter {chapter_num} generated")
            return result
        except Exception as e:
            logger.error(f"[generate:scene] Failed to generate chapter {chapter_num}: {e}")
            raise

