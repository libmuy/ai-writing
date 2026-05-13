"""Mock LLM provider for offline testing and CI.

Use this provider in `config.yaml` (set `type: mock`) to run the system
without real API keys. It returns simple deterministic JSON or text suitable
for exercising the agents and CLI flows.
"""

import logging
import re
from typing import Any, Dict

from src.providers import BaseProvider

logger = logging.getLogger(__name__)


class MockProvider(BaseProvider):
    """A minimal mock provider that returns canned responses.

    It returns Python dicts when `expect_json=True` and plain strings when
    `expect_json=False`.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)

    def call(self, prompt: str, expect_json: bool = False, max_tokens: int = 4096, temperature: float = 1.0) -> Any:
        lp = (prompt or "").lower()

        if expect_json:
            # Synopsis candidates (be permissive for test prompts)
            if "synopsis" in lp:
                return {
                    "candidates": [
                        {"id": 1, "title": "Mock Novel", "description": "A mock story summary.", "themes": ["mock", "test"]},
                        {"id": 2, "title": "Mock Novel 2", "description": "Another mock summary.", "themes": ["sample"]},
                        {"id": 3, "title": "Mock Novel 3", "description": "Yet another mock summary.", "themes": ["demo"]},
                    ]
                }

            # World candidates
            if "world" in lp and "candidate" in lp or "world candidates" in lp:
                return {
                    "candidates": [
                        {"id": 1, "name": "Mockland", "setting": "Futuristic City", "time_period": "Near Future", "key_features": ["neon", "ai", "megacorp"]},
                        {"id": 2, "name": "Oldrealm", "setting": "Castle Kingdom", "time_period": "Medieval", "key_features": ["feudal"]},
                        {"id": 3, "name": "Wilderness", "setting": "Islands", "time_period": "Unknown", "key_features": ["mystery"]},
                    ]
                }

            # Novel plan
            if "novel plan" in lp or "total_chapters" in lp or "create a novel plan" in lp:
                return {
                    "total_chapters": 6,
                    "total_arcs": 2,
                    "arc_summaries": [
                        {"arc": 1, "title": "Act 1", "summary": "Beginning and setup."},
                        {"arc": 2, "title": "Act 2", "summary": "Resolution and climax."},
                    ],
                }

            # Chapter plan
            if "chapter" in lp and ("scene" in lp or "elaborate" in lp or "scenes" in lp):
                m = re.search(r'chapter\W*(\d{1,3})', lp)
                ch = int(m.group(1)) if m else 1
                return {
                    "chapter": ch,
                    "arc_id": 1,
                    "title": f"Mock Chapter {ch}",
                    "scenes": [
                        {"number": 1, "setting": "Room", "pov": "Protagonist", "beats": ["enter", "conflict"]},
                        {"number": 2, "setting": "Street", "pov": "Protagonist", "beats": ["search", "discover"]},
                    ],
                    "key_developments": ["setup", "inciting incident"],
                }

            # Fallback: return a minimal candidate set for general prompts
            return {
                "candidates": [
                    {"id": 1, "title": "Mock Novel", "description": "A mock story summary.", "themes": ["mock", "test"]},
                    {"id": 2, "title": "Mock Novel 2", "description": "Another mock summary.", "themes": ["sample"]},
                ]
            }

        # Non-JSON responses: prose or generic
        if "write the following chapter" in lp or "write" in lp and "chapter" in lp:
            return "## Scene 1: Mock Scene\n\nThis is mock prose for testing chapter generation.\n"

        # Default plain response
        return "MOCK RESPONSE"
