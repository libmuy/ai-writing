# Phase 2 Design: Quality Loop + Short-Term Memory

**Goal:** Generate output that is measurably better with a critique-revision cycle. Maintain continuity across ~10 chapters.  
**Builds on:** [design-phase1.md](design-phase1.md) — file layout, agents, state, LLM wrapper.  
**Next phase:** [design-phase3.md](design-phase3.md) — Arc & Novel Scale

---

## 1. What Gets Added

| Component | Purpose |
|---|---|
| **Critique Agent** | Scores each chapter on 3 dimensions; writes `ch_NNN_meta.json` |
| **Editor Agent** | Rewrites flagged sections; feeds back into critique loop |
| **Memory Manager** | Writes `ch_NNN.summary.txt` after each commit; assembles rolling context |
| **Character Manager** | Updates `characters/*.json` after each chapter (simple overwrite) |
| **LangGraph** | Manages the critique-revision cycle graph; `SqliteSaver` for checkpointing |
| **ContractEnforcer** | Pydantic output validation + parse retry for all LLM calls |
| **LangSmith** | Agent trace observability |

---

## 2. New Agents

### 2.1 Critique Agent

Scores the generated chapter across 3 core dimensions (1–10):

| Dimension | Key Signals |
|---|---|
| **Narrative coherence** | Cause-effect chains, scene purpose, chapter plan fulfilment |
| **Consistency** | Facts align with `characters/*.json`, `world.yaml`, and `constitution.md` |
| **Plan Compliance** | Were the planned scene beats executed? Did character focus match the plan? |

**Plan Compliance scoring:**
- 8–10: All major plan elements executed; any deviation improves on the plan
- 5–7: Most plan elements executed; minor omissions
- 3–4: Key plan elements omitted; chapter diverges significantly
- 1–2: Chapter bears no recognizable relationship to its plan

Output contract:
```python
class CritiqueResult(BaseModel):
    chapter_number: int
    scores: dict[str, int]          # {"coherence": 7, "consistency": 8, "plan_compliance": 6}
    overall_score: float            # mean of dimensions
    failures: list[str]             # descriptions of specific failures
    low_dimensions: list[str]       # dimensions scoring below threshold
    passed: bool                    # overall_score >= CRITIQUE_THRESHOLD (default: 6.5)
```

### 2.2 Editor Agent

Receives the original `ChapterPlan` + `CritiqueResult` + draft prose. Rewrites the flagged sections only — not the whole chapter. Returns revised prose.

```python
class EditRequest(BaseModel):
    chapter_plan: ChapterPlan
    critique: CritiqueResult
    draft_prose: str
    revision_number: int            # 1–3; escalates to human queue at 4

class EditResult(BaseModel):
    revised_prose: str
    changes_made: list[str]         # brief description of each change
```

### 2.3 Memory Manager

After each chapter commit, writes a ~200-token summary:

```python
class ChapterSummary(BaseModel):
    chapter_number: int
    summary: str                    # ~200 tokens: events, character state changes, new facts
    key_characters: list[str]       # character IDs present in this chapter
    key_facts: list[str]            # new world/plot facts introduced
```

Saved to `chapters/ch_NNN.summary.txt`. Loaded as rolling context in Phase 2 (last 8 summaries).

### 2.4 Character Manager

After each chapter commit, updates character snapshots based on the committed prose:

```python
class CharacterUpdate(BaseModel):
    character_id: str
    status: str | None
    location: str | None
    emotional_state: str | None
    active_goals: list[str] | None
    relationships: dict[str, str] | None
    last_seen_chapter: int
```

Simple overwrite to `characters/{id}.json` — no changeset protocol yet.

---

## 3. State (LangGraph TypedDict)

```python
class NovelState(TypedDict):
    # Loaded from files at start
    novel_plan: dict
    chapter_plan: dict
    characters: dict[str, dict]
    world: dict
    constitution: str
    # Runtime
    chapter_index: int
    draft_prose: str | None
    critique_result: CritiqueResult | None
    revision_count: int
    recent_summaries: list[str]     # last 8 chapter summaries
```

---

## 4. LangGraph: Critique-Revision Cycle

LangGraph manages the critique-revision loop. Plain functions handle novel/chapter planning outside the graph.

```
[generate_chapter]
        ↓
[critique_chapter]
        ↓
  passed? ──YES──→ [update_characters] → [write_summary] → [commit_chapter]
        │
       NO
        ↓
  revision_count < 3?
        │ YES
        ↓
  [editor_revise] → [generate_chapter] (loop back)
        │
       NO (revision_count == 3)
        ↓
  [human_review_queue]   ← writes to reviews/ch_NNN_review.json and halts
```

LangGraph node definitions:
```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

def build_chapter_graph(checkpointer) -> StateGraph:
    graph = StateGraph(NovelState)
    graph.add_node("generate_chapter", generate_chapter_node)
    graph.add_node("critique_chapter", critique_chapter_node)
    graph.add_node("editor_revise", editor_revise_node)
    graph.add_node("update_characters", update_characters_node)
    graph.add_node("write_summary", write_summary_node)
    graph.add_node("commit_chapter", commit_chapter_node)
    graph.add_node("human_review_queue", human_review_node)

    graph.set_entry_point("generate_chapter")
    graph.add_edge("generate_chapter", "critique_chapter")
    graph.add_conditional_edges("critique_chapter", route_critique, {
        "pass": "update_characters",
        "revise": "editor_revise",
        "escalate": "human_review_queue",
    })
    graph.add_edge("editor_revise", "critique_chapter")
    graph.add_edge("update_characters", "write_summary")
    graph.add_edge("write_summary", "commit_chapter")

    return graph.compile(checkpointer=checkpointer)
```

Checkpointing with `SqliteSaver`:
```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("novel/checkpoints.db")
graph = build_chapter_graph(checkpointer)

# Each chapter gets a stable thread_id; crashes resume from last committed node
result = graph.invoke(
    state,
    config={"configurable": {"thread_id": f"ch-{chapter_index:03d}"}},
)
```

---

## 5. Output Contracts (ContractEnforcer)

All LLM calls use Pydantic validation with retry:

```python
class ContractEnforcer:
    max_retries: int = 3

    def call(self, prompt: list[dict], contract: type[BaseModel]) -> BaseModel:
        for attempt in range(self.max_retries):
            raw = call_llm(prompt, expect_json=False)
            try:
                return contract.model_validate_json(raw)
            except ValidationError as e:
                if attempt < self.max_retries - 1:
                    prompt = prompt + [
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": f"Invalid JSON. Errors: {e}. Reply with only the corrected JSON."},
                    ]
                else:
                    raise ContractFailure(contract=contract.__name__, error=e, raw=raw)
```

Task catalog:
```python
TASK_CATALOG = {
    "plan_chapter":   TaskDef(model="claude-sonnet-4-5",   contract=ChapterPlan,    retries=3),
    "generate_scene": TaskDef(model="claude-haiku-4-5",    contract=Scene,          retries=3),
    "critique":       TaskDef(model="claude-sonnet-4-5",   contract=CritiqueResult, retries=2),
    "edit_chapter":   TaskDef(model="claude-sonnet-4-5",   contract=EditResult,     retries=2),
    "summarize":      TaskDef(model="claude-haiku-4-5",    contract=ChapterSummary, retries=2),
    "update_chars":   TaskDef(model="claude-haiku-4-5",    contract=CharacterUpdate, retries=2),
}
```

---

## 6. Context Assembly

Extended from Phase 1 — adds rolling chapter summaries:

```python
def build_context(state: NovelState) -> list[dict]:
    summaries_text = "\n\n---\n\n".join(state["recent_summaries"][-8:])
    return [
        {"role": "system", "content": state["constitution"]},
        {"role": "system", "content": json.dumps(state["novel_plan"])},
        {"role": "system", "content": yaml.dump(state["world"])},
        {"role": "system", "content": json.dumps(state["characters"])},
        {"role": "system", "content": f"Recent chapter summaries:\n{summaries_text}"},
        {"role": "user",   "content": json.dumps(state["chapter_plan"])},
    ]
```

Context window budget (Phase 2):
```
constitution.md              ~200 tokens
novel_plan.json              ~500 tokens
world.yaml                   ~300 tokens
characters/*.json            ~400 tokens
last 8 chapter summaries     ~1,600 tokens  (200 tokens × 8)
current chapter plan         ~300 tokens
──────────────────────────────────────────
Total                        ~3,300 tokens
```

---

## 7. File Layout (additions)

```
/novel/
  checkpoints.db             ← LangGraph SqliteSaver (new)
  chapters/
    ch_001.md
    ch_001.summary.txt       ← written by Memory Manager (new)
    ch_001_meta.json         ← written by Critique Agent (new)
  reviews/
    ch_003_review.json       ← written when escalated to human queue (new)
```

### ch_NNN_meta.json
```json
{
  "chapter_number": 1,
  "scores": {"coherence": 7, "consistency": 8, "plan_compliance": 9},
  "overall_score": 8.0,
  "revision_count": 1,
  "passed": true,
  "word_count": 2043
}
```

---

## 8. Orchestration

The outer loop stays in plain Python. LangGraph only runs inside each chapter:

```python
def run(output_dir: str):
    state = load_state(output_dir)
    checkpointer = SqliteSaver.from_conn_string(f"{output_dir}/checkpoints.db")
    graph = build_chapter_graph(checkpointer)

    for i in range(state["novel_plan"]["chapter_count"]):
        if exists(f"{output_dir}/chapters/ch_{i:03d}.md"):
            continue  # already committed

        chapter_plan = plan_chapter(i, state)
        state["chapter_plan"] = chapter_plan
        state["chapter_index"] = i
        state["revision_count"] = 0
        state["recent_summaries"] = load_recent_summaries(output_dir, n=8)

        graph.invoke(state, config={"configurable": {"thread_id": f"ch-{i:03d}"}})

        # reload characters after Character Manager updated them
        state["characters"] = load_characters(output_dir)
```

---

## 9. How to Test

```bash
python run.py --chapters 10 --output ./novel
```

Evaluate quality programmatically:
```bash
python eval.py --novel-dir ./novel --report eval_report.json
```

`eval_report.json` contains per-chapter scores, revision counts, word counts. Open in Jupyter to plot score trends and validate that the critique loop measurably improves output.

---

## 10. Technology Stack

| Component | Choice |
|---|---|
| LLM (planning/critique/edit) | Claude Sonnet |
| LLM (generation/summarization) | Claude Haiku |
| Storage | Files + `checkpoints.db` (SQLite) |
| Orchestration | LangGraph + `SqliteSaver` |
| Output validation | Pydantic v2 + `ContractEnforcer` |
| Observability | LangSmith (agent traces) |
| Dependencies | `anthropic`, `langgraph`, `pydantic`, `pyyaml`, `langsmith` |

---

## 11. Success Metric

> Do critique scores improve with the revision loop? Does character state remain consistent across 10 chapters without manual correction?

Phase 2 is done when you can answer yes to both.

---

## 12. What Phase 3 Adds

- Arc Manager (arc-level planning and pacing)
- Style Agent, Continuity Guard, World Builder, LengthNormalizerAgent
- Hierarchical memory (3-tier: recent full / mid compressed / keyword index)
- `sqlite-vec` semantic retrieval
- FastAPI REST API (test via `/docs` Swagger UI)
- Arc-level parallelism
- Full 6-dimension critique scoring
