"""Planning prompts."""

NOVEL_PLAN_PROMPT = """Based on the constitution and world, create a novel plan:

**Constitution:**
{constitution}

**World:**
{world}

Define:
1. Total chapters (estimate)
2. Number of acts/arcs
3. Major plot points for each arc
4. Character journey arcs

Output as JSON: {{"total_chapters": N, "total_arcs": N, "arc_summaries": [{{"arc": 1, "title": "...", "summary": "..."}}]}}
"""

ARC_PLAN_PROMPT = """Given the novel plan and arc {arc_id}, create a detailed arc plan:

**Novel Plan:** {novel_plan}
**Arc {arc_id} Summary:** {arc_summary}

Define chapter-by-chapter beats for this arc:
- Chapter range within arc
- Beat title and description
- Key events
- Character developments

Output as JSON: {{"arc": {arc_id}, "chapters": [{{"chapter": 1, "beat": "...", "description": "...", "key_events": ["..."]}}]}}
"""

CHAPTER_PLAN_PROMPT = """Given the arc plan, create a detailed chapter plan:

**Arc Plan:** {arc_plan}
**Chapter Beat:** {beat}

Elaborate the chapter into:
- Scene breakdown (3-5 scenes)
- POV character(s)
- Key developments
- Emotional beats
- Dialogue notes

Output as JSON: {{"chapter": {chapter_num}, "scenes": [{{"number": 1, "setting": "...", "pov": "...", "beats": ["..."]}}]}}
"""
