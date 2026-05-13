# Phase 1 Design: Linear Generation

**Goal:** Generate a readable, coherent short story end-to-end.  
**Builds on:** nothing — this is the starting point.  
**Next phase:** [design-phase2.md](design-phase2.md) — Quality Loop + Short-Term Memory

---

## 1. What Gets Built

Three agents wired together with plain Python functions. No graph, no database, no critique loop. Output goes to files you read directly.

```
plan_novel() → plan_chapter() → generate_scenes() → commit_chapter()
```

---

## 2. Agents

| Agent | What it does |
|---|---|
| **Novel Planner** | One LLM call. Reads the seed prompt + `constitution.md`. Writes `novel_plan.json`: themes, chapter count, major turns, ending direction. |
| **Chapter Planner** | One LLM call per chapter. Reads `novel_plan.json` + character/world files. Writes `ch_NNN_plan.json`: scene beats, character focus, emotional target. |
| **Scene Generator** | One LLM call per scene. Reads chapter plan + context. Writes prose to `chapters/ch_NNN.md`. |

No Arc Manager yet — the Novel Planner owns pacing directly. No Critique Agent, no Editor Agent.

---

## 3. File Layout

```
/novel/
  constitution.md          ← hand-written: invariant rules for tone, world, characters
  novel_plan.json          ← written by Novel Planner
  world.yaml               ← hand-written: setting, rules, lore
  characters/
    elena.json             ← hand-written: status, goals, relationships, voice notes
    dom.json
  arcs/
    arc_01/
      ch_001_plan.json     ← written by Chapter Planner
      ch_002_plan.json
  chapters/
    ch_001.md              ← written by Scene Generator
    ch_002.md
```

All files are human-readable. `git` is your version control and rollback.

---

## 4. State

No shared state object. Functions pass a plain dict:

```python
state = {
    "novel_plan": novel_plan,       # dict loaded from novel_plan.json
    "chapter_plan": chapter_plan,   # dict loaded from ch_NNN_plan.json
    "characters": characters,       # dict loaded from characters/*.json
    "world": world,                 # dict loaded from world.yaml
    "constitution": constitution,   # str loaded from constitution.md
    "chapter_index": 0,
}
```

---

## 5. Context Assembly

Manual. Each generation call loads its own context from files:

```python
def build_context(chapter_id: int, state: dict) -> list[dict]:
    return [
        {"role": "system", "content": state["constitution"]},
        {"role": "system", "content": json.dumps(state["novel_plan"])},
        {"role": "system", "content": yaml.dump(state["world"])},
        {"role": "system", "content": json.dumps(state["characters"])},
        {"role": "user",   "content": json.dumps(state["chapter_plan"])},
    ]
```

Context window budget (Phase 1):
```
constitution.md         ~200 tokens  (always present)
novel_plan.json         ~500 tokens  (always present)
world.yaml              ~300 tokens  (always present)
characters/*.json       ~400 tokens  (always present)
chapter plan            ~300 tokens  (current chapter)
──────────────────────────────────────
Total                  ~1,700 tokens
```

The novel is short (≤10 chapters) so everything fits without retrieval.

---

## 6. Data Schemas

### novel_plan.json
```json
{
  "title": "Project Ember",
  "seed": "A detective in a cyberpunk city searches for her missing brother",
  "chapter_count": 5,
  "themes": ["loyalty", "systemic corruption", "identity"],
  "major_turns": [
    {"chapter": 2, "event": "Elena discovers the Council's involvement"},
    {"chapter": 4, "event": "Dom betrays Elena to protect her"}
  ],
  "ending_direction": "Elena exposes the Council but loses Dom"
}
```

### characters/elena.json
```json
{
  "id": "char_elena",
  "name": "Elena Voss",
  "role": "protagonist",
  "status": "alive",
  "location": "New Meridian, Sector 4",
  "emotional_state": "grieving",
  "active_goals": ["find brother", "expose Council"],
  "relationships": {"char_dom": "uneasy_ally"},
  "voice_notes": "Terse. Uses technical jargon. Deflects emotion with sarcasm.",
  "last_seen_chapter": 0
}
```

### ch_NNN_plan.json
```json
{
  "chapter_number": 1,
  "title": "Cold Case",
  "emotional_target": "dread",
  "character_focus": ["char_elena"],
  "scene_beats": [
    "Elena reviews her brother's last known location",
    "She finds an encrypted message in his apartment",
    "Cut to: the Council receiving a report about Elena's inquiry"
  ],
  "word_count_target": 2000
}
```

---

## 7. Orchestration

Plain sequential Python — no graph, no retry logic, no async:

```python
def run(seed: str, chapter_count: int, output_dir: str):
    state = load_state(output_dir)

    # Step 1: plan the novel (once)
    if not exists(f"{output_dir}/novel_plan.json"):
        novel_plan = plan_novel(seed, state["constitution"], state["world"])
        write_json(f"{output_dir}/novel_plan.json", novel_plan)
        state["novel_plan"] = novel_plan

    # Step 2: plan + generate each chapter in sequence
    for i in range(chapter_count):
        if exists(f"{output_dir}/chapters/ch_{i:03d}.md"):
            continue   # resume: skip already-written chapters

        chapter_plan = plan_chapter(i, state)
        write_json(f"{output_dir}/arcs/arc_01/ch_{i:03d}_plan.json", chapter_plan)
        state["chapter_plan"] = chapter_plan

        prose = generate_chapter(state)
        write_text(f"{output_dir}/chapters/ch_{i:03d}.md", prose)

        state["chapter_index"] = i + 1
        print(f"  chapter {i+1}/{chapter_count} written")
```

Crash recovery: the `if exists(...)` check means re-running the script skips already-written chapters automatically.

---

## 8. LLM Calls

Simple wrapper — no Pydantic contract yet, just `json.loads` with one retry:

```python
def call_llm(prompt: list[dict], expect_json: bool = True) -> str | dict:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=prompt,
    )
    raw = response.content[0].text
    if expect_json:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # one retry with explicit instruction
            prompt.append({"role": "assistant", "content": raw})
            prompt.append({"role": "user", "content": "Your response was not valid JSON. Reply with only the JSON object."})
            raw = client.messages.create(model="claude-sonnet-4-5", max_tokens=4096, messages=prompt).content[0].text
            return json.loads(raw)
    return raw
```

---

## 9. How to Test

```bash
python run.py --seed "A detective in a cyberpunk city" --chapters 3 --output ./novel
```

Open `novel/chapters/ch_001.md`. Read it. Does it make sense? Does it follow the chapter plan?

No automated scoring yet — evaluation is human reading.

---

## 10. Technology Stack

| Component | Choice |
|---|---|
| LLM | Claude Sonnet (planning + generation) |
| Storage | Files (`*.json`, `*.md`, `*.yaml`) |
| Version control | `git` |
| Orchestration | Plain Python functions |
| Dependencies | `anthropic`, `pyyaml` |

No LangGraph, no database, no vector store, no Redis.

---

## 11. Success Metric

> Can you generate a 3-chapter story that a human finds readable and internally consistent?

Phase 1 is done when you can answer yes without manual editing of the output.

---

## 12. What Phase 2 Adds

- Critique Agent + Editor Agent (revision loop)
- Character Manager (dynamic state updates after each chapter)
- Memory Manager (rolling chapter summaries)
- LangGraph (for the critique-revision cycle graph)
- `ContractEnforcer` (Pydantic output validation)
