# Phase 3 Design: Arc & Novel Scale

**Goal:** Generate a 50-chapter novel without world or character drift. Long runs must be resumable after crashes.  
**Builds on:** [design-phase2.md](design-phase2.md) — LangGraph, critique loop, rolling summaries, ContractEnforcer.  
**Next phase:** [design-phase4.md](design-phase4.md) — Quality Hardening

---

## 1. What Gets Added

| Component | Purpose |
|---|---|
| **Arc Manager** | Plans and tracks pacing, tension, and beats across chapters within an arc |
| **Style Agent** | Enforces tone, POV consistency, sentence rhythm variety |
| **Continuity Guard** | Diffs new chapter against character/world state; flags anomalies before commit |
| **World Builder** | Updates `world.yaml` after each chapter (dynamic, replaces hand-writing) |
| **LengthNormalizerAgent** | Expands/compresses prose to hit word-count target without changing plot |
| **Hierarchical memory** | 3-tier context: recent (full) / mid-range (compressed) / long-term (keyword index) |
| **`sqlite-vec` retrieval** | Semantic search over chapter summaries for top-K context selection |
| **Conflict Resolution** | Continuity Guard + Editor Agent handle contradictions between agents |
| **FastAPI REST API** | Trigger runs, poll status, fetch chapters — test via `/docs` Swagger UI |
| **Arc-level parallelism** | Independent arcs run concurrently via `asyncio` |
| **Full 6-dimension critique** | Adds Emotional Depth, Stylistic Variation, Originality to Phase 2's 3 dimensions |
| **Length governance** | Hard/soft word-count enforcement with re-generation or normalization |
| **Context Budget Report** | Tracks token usage per context tier per generation call |

---

## 2. New Agents

### 2.1 Arc Manager

Runs once per arc before chapter generation begins. Reads `novel_plan.json` + previous arc summaries. Writes `arc_plan.json`.

```python
class ArcPlan(BaseModel):
    arc_number: int
    chapter_range: tuple[int, int]    # e.g., (0, 14) = chapters 0–14
    arc_theme: str
    tension_curve: list[float]        # per-chapter tension target, 0.0–1.0
    opening_state: str                # world/character state at arc start
    closing_state: str                # intended state at arc end
    key_events: list[str]             # must-happen events in this arc
    chapter_plans: list[ChapterPlan]  # pre-generated for all chapters in arc
```

### 2.2 Style Agent

Runs after Scene Generator, before Critique Agent. Checks and rewrites for:
- POV consistency (single POV per scene)
- Sentence length variance (flags monotonous rhythm)
- Tone drift (checks against `constitution.md` tone rules)

```python
class StyleResult(BaseModel):
    prose: str              # polished prose (may be unchanged)
    changes_made: list[str]
    issues_found: list[str]
```

### 2.3 Continuity Guard

Runs after Style Agent. Diffs new chapter against `characters/*.json` and `world.yaml`. Flags contradictions before commit.

```python
class ContinuityReport(BaseModel):
    contradictions: list[Contradiction]
    passed: bool

class Contradiction(BaseModel):
    type: str           # "character_state" | "world_fact" | "timeline"
    entity_id: str
    expected: str       # value in knowledge store
    found: str          # value in generated chapter
    severity: str       # "warning" | "error"
```

Contradictions with `severity == "error"` block commit and trigger Editor Agent with the conflict details.

### 2.4 World Builder

After each chapter commit, updates `world.yaml` with new facts introduced in the chapter (locations discovered, events that occurred, world rules exercised):

```python
class WorldUpdate(BaseModel):
    new_locations: list[str]
    new_facts: list[str]
    events_occurred: list[str]
    timeline_entries: list[dict]
```

Simple overwrite to `world.yaml` — no changeset protocol.

### 2.5 LengthNormalizerAgent

Runs as a post-critique gate. Only invoked when chapter word count is in soft violation range:

```python
class LengthSpec(BaseModel):
    target_words: int
    soft_min: int    # target * 0.75 — triggers normalizer
    soft_max: int    # target * 1.25 — triggers normalizer
    hard_min: int    # target * 0.5  — blocks commit, requires regeneration
    hard_max: int    # target * 1.75 — blocks commit, requires regeneration
```

---

## 3. Hierarchical Memory (3-Tier)

Replaces Phase 2's flat rolling summaries. Keeps context cost bounded regardless of novel length.

```
Tier 1 — Recent window:     last 10 chapters     full summaries (~200 tokens each)
Tier 2 — Mid window:        chapters 11–50 back  compressed abstracts (~60 tokens each)
Tier 3 — Long-term index:   chapters 50+ back    keyword-frequency rows (SQLite)
```

**Summarization lifecycle:**

1. After commit: Memory Manager writes `ch_NNN.summary.txt` (~200 tokens)
2. When chapter exits Tier 1 (>10 chapters old): Memory Manager compresses to `ch_NNN.summary.mid.txt` (~60 tokens)
3. Every N chapters: arc summary regenerated from chapter abstracts → `arcs/arc_NN/arc_summary.txt`
4. Top-20 keywords per chapter stored in SQLite `keyword_index` table: `(chapter_id, keyword, frequency)`

### sqlite-vec Retrieval

For chapters in the long-term index, use `sqlite-vec` (in-process, no server) to embed and search summaries:

```python
import sqlite_vec

def retrieve_relevant_summaries(query: str, top_k: int = 5) -> list[str]:
    # query = chapter plan text
    query_embedding = embed(query)
    results = db.execute("""
        SELECT chapter_id, summary_text, distance
        FROM chapter_embeddings
        WHERE chapter_id NOT IN (recent_ids)  -- skip Tier 1, already included
        ORDER BY vec_distance_cosine(embedding, ?) ASC
        LIMIT ?
    """, [query_embedding, top_k]).fetchall()
    return [r["summary_text"] for r in results]
```

---

## 4. Context Assembly (3-Tier)

```python
def build_context(chapter_id: int, state: NovelState) -> list[dict]:
    recent   = load_summaries(last_n=10)                    # Tier 1: full
    mid      = load_mid_summaries(range_back=(11, 50))      # Tier 2: compressed
    long_kw  = retrieve_relevant_summaries(                 # Tier 3: sqlite-vec
        query=json.dumps(state["chapter_plan"]), top_k=5
    )
    return [
        {"role": "system", "content": state["constitution"]},
        {"role": "system", "content": json.dumps(state["novel_plan"])},
        {"role": "system", "content": json.dumps(state["arc_plan"])},
        {"role": "system", "content": yaml.dump(state["world"])},
        {"role": "system", "content": json.dumps(state["characters"])},
        {"role": "system", "content": "\n\n".join(recent)},
        {"role": "system", "content": "\n\n".join(mid)},
        {"role": "system", "content": "\n\n".join(long_kw)},
        {"role": "user",   "content": json.dumps(state["chapter_plan"])},
    ]
```

Context window budget (Phase 3):
```
constitution.md              ~200 tokens
novel_plan.json              ~500 tokens
arc_plan.json                ~300 tokens
world.yaml                   ~400 tokens  (grown from Phase 1)
characters/*.json            ~400 tokens
Tier 1: last 10 summaries   ~2,000 tokens  (200 × 10)
Tier 2: mid summaries (×8)   ~480 tokens   (60 × 8)
Tier 3: long-term hits (×5)  ~300 tokens   (60 × 5)
chapter plan                 ~300 tokens
──────────────────────────────────────────
Total                        ~4,880 tokens
```

### Context Budget Report

Every generation call emits a report saved to `chapter_metrics`:
```python
class ContextBudgetReport(BaseModel):
    chapter: int
    total_tokens_used: int
    total_tokens_budget: int
    tier_usage: dict[str, int]    # {"tier1": 1800, "tier2": 420, "tier3": 280, ...}
    tiers_at_capacity: list[str]  # tiers that hit their token budget
```

Alert: any tier at 100% for >20 consecutive chapters triggers operator notification.

---

## 5. LangGraph: Full Chapter Cycle

Extended from Phase 2 to include Style Agent, Continuity Guard, Length governance:

```
[generate_chapter]
        ↓
[style_polish]
        ↓
[continuity_check]
    contradiction_error? ──YES──→ [editor_revise_contradiction] → [style_polish]
        │
       NO
        ↓
[critique_chapter]    ← now 6 dimensions
    passed? ──YES──→ [length_check]
        │                   │
       NO             soft_violation? → [length_normalize] → [update_state] → [commit]
        ↓                   │
  revision_count < 3?  hard_violation? → [regenerate]   (loop back to generate)
        │ YES                │
        ↓                  pass → [update_state] → [commit]
  [editor_revise] → [style_polish]
        │
       NO (3 revisions)
        ↓
  [human_review_queue]
```

`update_state` node = Character Manager + World Builder updates (sequential, not parallel, to avoid overwrites).

---

## 6. Full 6-Dimension Critique

Phase 2 had 3 dimensions. Phase 3 adds:

| Dimension | Key Signals | Phase added |
|---|---|---|
| **Narrative coherence** | Cause-effect chains, scene purpose, plan fulfilment | 2 |
| **Consistency** | Facts vs. `characters/*.json`, `world.yaml`, `constitution.md` | 2 |
| **Plan Compliance** | Were scene beats executed? Character focus matched? | 2 |
| **Emotional depth** | Character motivation clarity, stakes escalation, subtext | 3 |
| **Stylistic variation** | Sentence length variance, vocabulary richness, POV stability | 3 |
| **Originality** | Semantic similarity vs. prior chapters (embedding cosine distance) | 3 |

---

## 7. Conflict Resolution

When Continuity Guard finds a contradiction:
1. Continuity Guard writes a `Contradiction` record to the state
2. Editor Agent receives: draft prose + contradiction details + authoritative source (from `characters/*.json` or `world.yaml`)
3. Editor rewrites only the offending passage; correction written back to knowledge files
4. Max 3 resolution cycles per chapter (same limit as critique revisions)

---

## 8. State (extended)

```python
class NovelState(TypedDict):
    # From Phase 2
    novel_plan: dict
    arc_plan: dict
    chapter_plan: dict
    characters: dict[str, dict]
    world: dict
    constitution: str
    chapter_index: int
    draft_prose: str | None
    critique_result: CritiqueResult | None
    revision_count: int
    # Phase 3 additions
    recent_summaries: list[str]       # Tier 1: last 10 full summaries
    mid_summaries: list[str]          # Tier 2: compressed
    retrieved_summaries: list[str]    # Tier 3: sqlite-vec hits
    style_result: StyleResult | None
    continuity_report: ContinuityReport | None
    context_budget: ContextBudgetReport | None
    arc_index: int
```

---

## 9. Parallelism

Independent arcs run concurrently. Arc dependencies (arc N+1 needs arc N's ending state) are declared in `novel_plan.json` and resolved before dispatch:

```python
async def run_all_arcs(novel_plan: dict, output_dir: str):
    arcs = novel_plan["arcs"]
    # Build dependency graph; dispatch independent arcs together
    async with asyncio.TaskGroup() as tg:
        for arc in get_independent_arcs(arcs):
            tg.create_task(run_arc(arc, output_dir))
    # Then dependent arcs after their prerequisites finish
```

Each arc gets its own LangGraph `thread_id` for checkpointing:
```python
graph.invoke(state, config={"configurable": {"thread_id": f"arc-{arc_id:02d}-ch-{ch_id:03d}"}})
```

---

## 10. FastAPI REST API

Exposes the generation pipeline as a REST service. Test via `/docs` (Swagger UI) — no frontend needed.

```
GET  /v1/novels                    list novel projects
POST /v1/novels                    create novel + write novel_plan.json
GET  /v1/novels/{id}               novel status + metadata
POST /v1/novels/{id}/generate      start/resume generation run
GET  /v1/novels/{id}/arcs          list arcs + status
GET  /v1/novels/{id}/chapters/{n}  fetch chapter prose + metadata
GET  /v1/novels/{id}/quality       quality report (all chapter scores)
POST /v1/novels/{id}/review/{n}    submit human review decision
```

Status polling (5s interval) is sufficient — no WebSocket yet.

---

## 11. File Layout (additions)

```
/novel/
  db/
    checkpoints.db             ← LangGraph SqliteSaver
    embeddings.db              ← sqlite-vec chapter embeddings (new)
    chapter_metrics.db         ← context budget + word count logs (new)
  arcs/
    arc_01/
      arc_plan.json            ← written by Arc Manager (new)
      arc_summary.txt          ← written by Memory Manager (new)
  chapters/
    ch_001.mid.summary.txt     ← written when chapter exits Tier 1 (new)
```

---

## 12. Technology Stack

| Component | Choice |
|---|---|
| LLM (planning/critique) | Claude Sonnet |
| LLM (generation/style/edit) | Claude Haiku |
| Storage | Files + SQLite (`checkpoints.db`, `embeddings.db`, `chapter_metrics.db`) |
| Semantic retrieval | `sqlite-vec` (in-process, no server) |
| Orchestration | LangGraph + `SqliteSaver` + `asyncio` |
| API | FastAPI + `uvicorn` |
| Output validation | Pydantic v2 + `ContractEnforcer` |
| Observability | LangSmith |
| Dependencies | `anthropic`, `langgraph`, `pydantic`, `fastapi`, `uvicorn`, `sqlite-vec`, `pyyaml`, `langsmith` |

---

## 13. Success Metric

> Does a 50-chapter novel maintain character consistency and world coherence without manual correction?

Phase 3 is done when you can answer yes.

---

## 14. What Phase 4 Adds

- Foreshadowing Registry (`foreshadowing.json`)
- Strand Weave pacing enforcement
- AI Tell Detection
- Sequence Analyzer (runs every 10 chapters)
- Emotion Curve pre-computation + scoring
- Reader Persona Simulation (optional critique mode)
