"""Setup prompts."""

SYNOPSIS_PROMPT = """Given the novel idea: {idea}

Generate 3-5 distinct story concept candidates. For each, provide:
- A compelling title
- A one-paragraph description
- 2-3 key themes

Output as JSON with structure: {{"candidates": [{{"id": 1, "title": "...", "description": "...", "themes": ["...", "..."]}}]}}
"""

WORLD_PROMPT = """Given the selected synopsis: {synopsis}

Generate 3 diverse world candidates. For each, provide:
- World name
- Setting (location/geography)
- Time period
- 3-4 key worldbuilding features

Output as JSON with structure: {{"candidates": [{{"id": 1, "name": "...", "setting": "...", "time_period": "...", "key_features": ["...", "..."]}}]}}
"""

CONSTITUTION_PROMPT = """Based on the selected synopsis and world, write a novel constitution:

**Synopsis:** {synopsis}
**World:** {world}

The constitution should define:
1. Core themes and narrative goals
2. Tone and voice
3. Character archetypes
4. Plot pillars
5. Pacing guidelines

Write in a clear, concise style suitable for writers to reference.
"""

WORLD_YAML_PROMPT = """Based on the selected world details, generate a structured YAML world file:

**World Details:** {world_desc}

Create YAML with sections:
- setting
- time_period
- climate
- geography
- key_locations (list)
- culture
- languages
- magic_or_tech_level

Output pure YAML, no markdown.
"""
