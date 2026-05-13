"""Chapter planner agent."""

import logging
import json
from typing import Any, Dict, List

from src.agents import Agent
from src.core.llm_call import call_llm
from src.core.config import get_provider_instance
from src.core.file_io import write_json, read_json
from pathlib import Path

logger = logging.getLogger(__name__)


class ChapterPlanner(Agent):
    """Elaborate arc beats into detailed chapter plans."""

    def run(self, context: Dict[str, Any], prompt_template: str, config: Dict[str, Any], chapters: List[int]) -> List[Dict[str, Any]]:
        """Generate chapter plans.
        
        Args:
            context: {"arc_plan": dict, "constitution": str}
            prompt_template: Template string with {arc_plan}, {constitution}
            config: Full config dict
            chapters: List of chapter numbers to plan
            
        Returns:
            List of chapter plan dicts
        """
        logger.info(f"[plan:chapter] Planning chapters {chapters}...")
        
        try:
            arc_plan = context.get("arc_plan", {})
            constitution = context.get("constitution", "")
            
            chapter_plans = []
            
            for chapter_num in chapters:
                logger.info(f"[plan:chapter] Generating plan for chapter {chapter_num}...")
                
                # Find beat for this chapter
                beat = self._find_beat_for_chapter(arc_plan, chapter_num)
                
                prompt = prompt_template.format(
                    arc_plan=json.dumps(arc_plan, indent=2),
                    constitution=constitution,
                    chapter_num=chapter_num,
                    beat=json.dumps(beat, indent=2) if beat else "{}",
                )
                
                agent_config = config.get("agents", {}).get("chapter_planner", {})
                provider_name = agent_config.get("provider", "anthropic")
                provider = get_provider_instance(provider_name, config)
                
                result = call_llm(
                    provider=provider,
                    prompt=prompt,
                    expect_json=True,
                    max_tokens=config.get("defaults", {}).get("max_tokens", 4096),
                    temperature=config.get("defaults", {}).get("temperature", 1.0),
                )
                
                chapter_plans.append(result)
                
                # Write chapter plan to file
                arc_id = context.get("arc_id", 1)
                root = Path.cwd()
                plan_path = root / "arcs" / f"arc_{arc_id:02d}" / f"ch_{chapter_num:03d}_plan.json"
                write_json(plan_path, result)
            
            logger.info(f"[plan:chapter] ✓ Generated {len(chapter_plans)} chapter plans")
            return chapter_plans
        except Exception as e:
            logger.error(f"[plan:chapter] Failed: {e}")
            raise

    def _find_beat_for_chapter(self, arc_plan: Dict[str, Any], chapter_num: int) -> Dict[str, Any]:
        """Find the beat entry for a specific chapter."""
        chapters = arc_plan.get("chapters", [])
        for chapter in chapters:
            if chapter.get("chapter") == chapter_num:
                return chapter
        return {}

