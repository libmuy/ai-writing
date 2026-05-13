"""Generation prompts."""

SCENE_PROMPT = """Write the following chapter based on the plan:

**Constitution:**
{constitution}

**World:**
{world}

**Characters:**
{characters}

**Chapter Plan:**
{chapter_plan}

Write {scene_count} scenes totaling {target_words} words. 
Use markdown with:
- ## Scene 1: [title]
- Narrative prose
- Dialogue where appropriate

Maintain consistency with established character voices and world rules.
"""
