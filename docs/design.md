# AI-Powered Novel Generation System: Architecture Design

---

## 1. System Overview

```
╔═════════════════════════════════════════════════════════════════╗
║                   Prefect Flow (Run Management)                 ║
║         scheduling · retries · cost tracking · deployment       ║
║                                                                  ║
║  @task: plan_novel → @task: generate_arc × N → @task: assemble  ║
╚══════════════════════════╦══════════════════════════════════════╝
                           ║  invokes per arc
┌──────────────────────────▼──────────────────────────────────────┐
│                        Orchestration Layer                       │
│                     (LangGraph State Machine)                    │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  Novel   │  │  Arc     │  │ Chapter  │  │   Quality    │    │
│  │ Planner  │→ │ Manager  │→ │Generator │→ │  Controller  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
│       ↕              ↕             ↕               ↕             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Agent Bus (shared state)              │    │
│  └─────────────────────────────────────────────────────────┘    │
│       ↕              ↕             ↕               ↕             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │Character │  │  World   │  │  Style   │  │   Memory     │    │
│  │ Manager  │  │ Builder  │  │  Agent   │  │   Manager    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               ↕
         ┌─────────────────────────────────────────┐
         │            Memory Layer                  │
         │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
         │  │  Vector  │  │Structured│  │ Cache │ │
         │  │    DB    │  │   KV     │  │(Redis)│ │
         │  └──────────┘  └──────────┘  └───────┘ │
         └─────────────────────────────────────────┘
```

---

## 2. Architecture Design

### 2.1 Hierarchical Generation Model

The system operates on three nested scopes, each with its own planning and generation loop:

```
Novel (1 document)
  └── Arcs (3–15 story arcs)
        └── Chapters (up to 10,000)
              └── Scenes (3–10 per chapter)
                    └── Paragraphs / Dialogue
```

Each scope has a dedicated planning pass before generation begins, ensuring top-down coherence.

At novel initialization, the system:
1. Loads a **Genre Profile** (§8.1) that provides genre-specific defaults for pacing model, strand ratios, length targets, and forbidden patterns.
2. Generates an **Emotion Curve** — a per-chapter emotion intensity target for the entire novel (§6.1), using a configurable curve model (`three_act`, `wave`, `hero_journey`, or `episodic`).

Both artifacts are stored in `NovelState` and inherited by every downstream planning pass.

```python
class ChapterEmotionTarget(BaseModel):
    chapter_number: int
    emotion_intensity: float      # 0.0–1.0
    narrative_phase: str          # e.g., "rising_action", "climax", "denouement"
    is_peak: bool
    is_valley: bool
    allowed_band: tuple[float, float]  # [min, max] acceptable intensity
```

For multi-volume novels, each volume can have its own curve overlaid on the master curve.

### 2.2 Two-Layer Orchestration Model

The system uses two complementary frameworks at different abstraction levels — they do not conflict:

| Layer | Framework | Owns |
|---|---|---|
| **Outer (run management)** | Prefect | Scheduling, arc-level retries, cost tracking, deployment, observability dashboard |
| **Inner (agent control flow)** | LangGraph | Agent state machine, critique cycles, typed state, scene-level parallelism, mid-arc checkpointing |

```
Prefect Flow
  └── @task plan_novel()
  └── @task generate_arc(arc_id)    ← one Prefect task per arc; retries=3
        └── LangGraph graph.invoke()   ← inner loop: agents, critique, state
  └── @task assemble_manuscript()
  └── @task quality_report()
```

The key rule: **LangGraph checkpoints (`thread_id`) are stable across Prefect retries**, so a crashed arc resumes from its last committed chapter rather than restarting from scratch.

### 2.3 Prefect Flow

Prefect wraps the top-level pipeline as a `@flow` with individual arcs as `@task`s:

```python
from prefect import flow, task
from langgraph.checkpoint.postgres import PostgresSaver

@task(retries=3, retry_delay_seconds=30, name="generate-arc")
def generate_arc(arc_id: int, novel_state: dict) -> dict:
    checkpointer = PostgresSaver.from_conn_string(DB_URL)
    graph = build_novel_graph(checkpointer)
    return graph.invoke(
        {"arc_id": arc_id, **novel_state},
        config={"configurable": {"thread_id": f"arc-{arc_id}"}},
    )

@flow(name="novel-generation", log_prints=True)
def generate_novel(num_arcs: int = 15):
    novel_plan = plan_novel()
    # Independent arcs are dispatched in parallel via .submit().
    # Arc dependencies (e.g., arc N+1 requiring arc N's ending state) are
    # declared in the NovelPlan and resolved by the Arc Manager before submission.
    arc_futures = [
        generate_arc.submit(arc_id, novel_plan) for arc_id in range(num_arcs)
    ]
    arc_results = [f.result() for f in arc_futures]
    assemble_manuscript(novel_plan, arc_results)
```

Prefect provides:
- **Dashboard** — live run status, arc progress, failure alerts.
- **Arc-level retries** — infrastructure failures (OOM, API timeout) retry the arc without re-running prior arcs.
- **Scheduling** — cron or event-triggered runs; pause and resume novel generation across days.
- **Cost tracking** — log LLM token usage per task for budget enforcement.
- **Deployment** — serve the flow on cloud infrastructure with a single `prefect deploy` command.

### 2.4 LangGraph State Machine

LangGraph is chosen because:
- Its **graph-based control flow** maps directly to the conditional, cyclical nature of narrative revision.
- **Persistent checkpointing** allows resuming generation after failures at any chapter.
- **Typed state schemas** enforce consistency across agent handoffs.
- Native support for **human-in-the-loop** breakpoints for editorial review.

Core graph nodes per chapter cycle:

```
[plan_chapter] → [assign_scene_beats] → [generate_scenes]
      ↑                                        ↓
[revise_plan]  ← [consistency_check]  ← [critique_scenes]
                        ↓ (pass)
                  [style_polish] → [length_check] → [validate_state] → [commit_chapter]
                                     ↓ (hard fail)       ↓ (invalid)
                                   [re-generate]      [await_repair]
```

- `length_check` — enforces word-count governance (§6.2); hard violations trigger re-generation.
- `validate_state` — runs the StateValidatorAgent (§3.4) against the proposed state changeset; invalid deltas block commit and enter a bounded repair flow (§5.3).

---

## 3. Agent System

### 3.1 Agent Roster

| Agent | Responsibility |
|---|---|
| **Novel Planner** | One-time high-level outline: themes, arcs, ending, major turns; generates emotion curve (§6.1) |
| **Arc Manager** | Manages tension curve, pacing, strand tracking (§6.3), and beats across chapters in an arc |
| **Chapter Planner** | Translates arc beats into scene-level plans for a single chapter |
| **Scene Generator** | Writes prose for individual scenes using retrieved context |
| **Character Manager** | Tracks character state, voice, relationships, and arcs; emits state changesets (§3.4) |
| **World Builder** | Maintains world rules, geography, lore, and timeline; emits state changesets (§3.4) |
| **Style Agent** | Enforces tone, POV consistency, varied sentence rhythm |
| **Critique Agent** | Evaluates output against quality rubrics; flags failures; assigns strand labels (§6.3) |
| **Editor Agent** | Rewrites flagged passages; resolves contradiction and repetition |
| **Memory Manager** | Handles retrieval, summarization, and context compression |
| **Continuity Guard** | Cross-checks facts (names, dates, locations) against the knowledge store |
| **StateValidatorAgent** | Validates proposed state changesets against chapter content before persistence (§3.4) |
| **LengthNormalizerAgent** | Expands or compresses prose to reach target word-count range without altering plot (§6.2) |
| ***ForeshadowingTracker*** *(service)* | DB-backed registry tracking foreshadowing lifecycle — planted → developing → revealed (§4.5) |

### 3.2 Agent Collaboration & Context Sharing

Agents communicate through a **shared LangGraph state object**:

```python
class NovelState(TypedDict):
    novel_plan: NovelPlan
    arc_plan: ArcPlan
    chapter_plan: ChapterPlan
    active_scenes: list[Scene]
    character_snapshots: dict[str, CharacterState]
    world_snapshot: WorldState
    style_profile: StyleProfile
    critique_results: list[CritiqueResult]
    memory_context: RetrievedContext
    chapter_index: int
    revision_count: int
    # --- added by feature adoption plan ---
    strand_history: list[StrandLabel]              # per-chapter strand labels (§6.3)
    emotion_curve: list[ChapterEmotionTarget]      # pre-computed intensity targets (§6.1)
    constitution_version: str                       # active constitution doc version (§4.6)
    pending_changesets: list[StateChangeset]        # staged, unapplied state deltas (§3.4)
```

Agents read from and write to specific fields only — enforced by schema typing. No agent mutates another agent's primary domain without going through a **conflict resolution protocol**.

### 3.3 Conflict Resolution

When two agents produce contradictory outputs (e.g., Character Manager says a character is dead, Scene Generator writes them alive):

1. **Continuity Guard** detects the contradiction via knowledge store lookup.
2. A **resolution prompt** is sent to the Editor Agent with both conflicting facts and the authoritative source.
3. Editor Agent rewrites the offending passage; the correction is written back to the knowledge store.
4. Revision is logged to prevent oscillation (max 3 revision cycles per scene).

### 3.4 State Mutation Protocol (Changeset-Based)

Agents that modify entity state (Character Manager, World Builder) **declare** changes as explicit structured changesets rather than writing to the KV store directly. This makes validation possible and rollback atomic.

```python
class StateChangeset(BaseModel):
    chapter: int
    agent_id: str
    changes: list[FieldChange]
    generation_id: str           # links to the chapter generation run

class FieldChange(BaseModel):
    entity_type: Literal["character", "world", "relationship", "timeline"]
    entity_id: str
    field: str
    old_value: Any               # snapshot before generation; used for rollback
    new_value: Any               # declared by agent after generation
    reason: str                  # brief LLM-generated explanation
    confidence: float            # 0.0–1.0; low-confidence changes trigger review
```

**Lifecycle:** changeset is staged → validated by StateValidatorAgent against chapter content → applied atomically on pass → discarded on failure (state remains frozen at previous snapshot).

### 3.5 Output Contracts & Parse Retry

Every agent call declares an **OutputContract** (Pydantic schema). A cross-cutting `ContractEnforcer` wraps all LLM calls:

```python
class ContractEnforcer:
    max_retries: int = 3

    def call(self, agent, state, contract: type[BaseModel]) -> BaseModel:
        for attempt in range(self.max_retries):
            raw = agent.llm.invoke(agent.build_prompt(state))
            try:
                return contract.model_validate_json(raw.content)
            except ValidationError as e:
                if attempt < self.max_retries - 1:
                    state = state | {"parse_error": str(e), "raw_response": raw.content}
                else:
                    raise ContractFailure(agent=agent.name, error=e, raw=raw.content)
```

All agent calls are registered in a **named task catalog** for prompt versioning, model assignment, and A/B testing:

```python
TASK_CATALOG = {
    "plan_chapter":   TaskDef(prompt=PLAN_CHAPTER_PROMPT, model="claude-3-7", contract=ChapterPlan, retries=3),
    "generate_scene": TaskDef(prompt=GENERATE_SCENE_PROMPT, model="gpt-4o-mini", contract=Scene, retries=3),
    "critique":       TaskDef(prompt=CRITIQUE_PROMPT, model="claude-3-7", contract=CritiqueResult, retries=2),
}
```

`ContractFailure` escalates to the human review queue. At 10,000 chapters even a 0.1% parse failure rate causes ~10 hard crashes; contracts eliminate this class of error.

---

## 4. Memory & Consistency

### 4.1 Memory Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Memory Layer                         │
│                                                           │
│  ┌──────────────────────┐   ┌──────────────────────┐    │
│  │  Vector Store         │   │  Structured KV Store  │    │
│  │  (Qdrant / pgvector)  │   │  (Postgres / Redis)   │    │
│  │                       │   │                       │    │
│  │  - Scene embeddings   │   │  - Character registry │    │
│  │  - Dialogue chunks    │   │  - Timeline events    │    │
│  │  - Thematic passages  │   │  - World facts        │    │
│  │  - Arc summaries      │   │  - Relationship graph │    │
│  └──────────────────────┘   └──────────────────────┘    │
│                                                           │
│  ┌──────────────────────┐   ┌──────────────────────┐    │
│  │  Hierarchical         │   │  Working Cache        │    │
│  │  Summary Store        │   │  (Redis TTL)          │    │
│  │                       │   │                       │    │
│  │  - Chapter summaries  │   │  - Current chapter    │    │
│  │  - Arc summaries      │   │  - Last 5 chapters    │    │
│  │  - Novel summary      │   │  - Active characters  │    │
│  └──────────────────────┘   └──────────────────────┘    │
│                                                           │
│  ┌──────────────────────┐   ┌──────────────────────┐    │
│  │  Long-Term Keyword    │   │  Reranker             │    │
│  │  Index (Postgres)     │   │  (Jina Reranker v3)   │    │
│  │                       │   │                       │    │
│  │  - (chapter, keyword, │   │  - Scores embedding   │    │
│  │    frequency) tuples  │   │    candidates for      │    │
│  │  - Bounded retrieval  │   │    narrative relevance  │    │
│  │  - No embedding cost  │   │  - Configurable top-K  │    │
│  └──────────────────────┘   └──────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Context Retrieval Strategy

Context is assembled via a **three-tier fractal memory** with a two-stage retrieval pipeline:

**Fractal tiers (configurable per project):**
```
recent_window:   last 10 chapters  (full summaries, highest detail)
mid_window:      chapters 11–50 back  (compressed summaries, medium detail)
long_term_index: chapters 50+ back   (keyword-frequency index, bounded retrieval, no embedding cost)
```

**Two-stage retrieval (embedding + reranking):**
```
Query (chapter plan + scene beat)
    ↓
Embedding search (Qdrant / pgvector)
    → top-50 candidate passages by cosine similarity
    ↓
Reranker (Jina Reranker v3 or compatible)
    → scores each candidate for narrative relevance
    → returns top-K (configurable per task type, default 8)
    ↓
Injected into context window
```

**Per-task retrieval configuration:**
```python
RETRIEVAL_CONFIG = {
    "scene_generation":   RetrievalSpec(candidates=50, top_k=8, rerank=True),
    "consistency_check":  RetrievalSpec(candidates=100, top_k=15, rerank=True),
    "character_snapshot": RetrievalSpec(candidates=20, top_k=5, rerank=False),  # fast, exact
}
```

Dry-run mode: retrieval can be executed standalone (without generation) to debug recall quality.

**Layered context window budget:**

```
[System Prompt]
  + [Novel Constitution]             (~200 tokens, always present)        ← §4.6
  + [Novel Plan Summary]             (~500 tokens, always present)
  + [Current Arc Summary]            (~300 tokens, always present)
  + [Recent Window: last 10 ch]      (~1,500 tokens, rolling)
  + [Mid Window: ch 11–50 back]      (~600 tokens, compressed)
  + [Long-Term Index hits]           (~400 tokens, keyword-retrieved)
  + [Active Character Snapshots]     (~400 tokens, dynamic)
  + [World State Relevant Facts]     (reranked, ~300 tokens)
  + [Foreshadowing Active Loops]     (~200 tokens)                       ← §4.5
  + [Current Chapter Plan]           (~300 tokens)
  + [Strand Weave Status]            (~100 tokens)                       ← §6.3
  + [Current Scene Beat]             (~100 tokens)
───────────────────────────────────────────────────────────
Total budget (configurable):          ~4,900 tokens of context
```

**Context Budget Report:**

Every generation call produces a `ContextBudgetReport` alongside the output:

```python
class ContextBudgetReport(BaseModel):
    chapter: int
    scene: int | None
    total_tokens_used: int
    total_tokens_budget: int
    tiers: dict[str, TierUsage]   # one entry per context section
    drop_reasons: list[DropReason]

class TierUsage(BaseModel):
    name: str
    tokens_allocated: int
    tokens_used: int
    items_included: int
    items_dropped: int

class DropReason(BaseModel):
    tier: str
    reason: str      # "recent_window_budget" | "prompt_token_budget" | "long_retrieval_budget"
    items_dropped: int
```

Reports are written to a `context_budget_log` table (time-series). Prefect dashboard shows a per-arc context budget chart. Alert threshold: any tier at 100% utilization for >20 consecutive chapters triggers operator notification.

### 4.3 Hierarchical Summarization

After each chapter is committed:

1. **Scene → Chapter summary**: Memory Manager summarizes all scenes into a ~200-token chapter abstract.
2. **Chapter → Mid-window compression**: When a chapter exits the recent window (>10 chapters old), it is compressed from full summary to a shorter mid-window abstract (~60 tokens).
3. **Chapter → Arc summary**: Every N chapters, arc summaries are regenerated from chapter abstracts.
4. **Arc → Novel summary**: Updated lazily at arc boundaries.
5. **Keyword extraction**: Top-20 keywords per chapter stored in the long-term keyword index (`chapter_id`, `keyword`, `frequency`); enables bounded retrieval at any novel length.

This creates a **pyramid** of summaries that keeps retrieval cost bounded and predictable regardless of novel length.

### 4.4 Character & World State Tracking

```json
// Character snapshot (structured KV)
{
  "id": "char_elena",
  "name": "Elena Voss",
  "status": "alive",
  "location": "New Meridian, Sector 4",
  "emotional_state": "grieving",
  "active_goals": ["find brother", "expose Council"],
  "relationships": {"char_dom": "uneasy_ally"},
  "last_seen_chapter": 247,
  "voice_sample_ids": ["scene_012", "scene_089"],
  "pending_changeset_id": null
}
```

Character Manager and World Builder emit a `StateChangeset` (§3.4) after each chapter generation. The changeset is validated by the StateValidatorAgent before being applied. The Continuity Guard diffs the new state against the previous for anomalies.

### 4.5 Foreshadowing Registry

A DB-backed `ForeshadowingRegistry` tracks every foreshadowing item as a first-class entity with lifecycle tracking:

```python
class ForeshadowingRecord(BaseModel):
    id: str                         # stable UUID
    description: str                # "Elena mentions the locked door in sector 4"
    planted_chapter: int
    target_reveal_chapter: int      # intended payoff chapter (estimated at plant time)
    urgency: int                    # 1–10, updated by Arc Manager each arc
    status: Literal["planted", "developing", "partial", "revealed", "abandoned"]
    status_history: list[StatusEntry]  # append-only audit log
    resolution_note: str | None     # filled when revealed/abandoned
```

**Integration points:**
1. **Novel Planner / Arc Manager** — declare foreshadowing items when generating arc plans; write to registry.
2. **Chapter Planner** — calls `registry.get_for_chapter(chapter_n)` which returns `urgent`, `due_soon`, `overdue`, and `related` items. This payload is injected into the Chapter Planner’s context.
3. **Post-commit** — Memory Manager calls `registry.update_status(chapter_n, chapter_text)` to classify whether active foreshadowing was advanced or resolved.
4. **Quality report** — the Prefect `@task quality_report()` includes: open loop count, overdue count, oldest unresolved item.

### 4.6 Novel Constitution

A project-level **Constitution** document — a versioned list of invariant writing rules that all agents receive as a shared constraint block:

```markdown
# Novel Constitution: "Project Ember"

## Invariant Rules
1. Tone is hopeful and persevering, never nihilistic or cynical.
2. Violence may be implied but never graphically described.
3. Protagonist Elena’s core character trait (resourcefulness) must be demonstrated at least once per arc.
4. The power system (Resonance) operates by strict rules: amplification only, no creation ex nihilo.
5. No character introduced after chapter 50 may become a primary POV character.
```

- Stored as a versioned document in the structured KV store.
- Injected as a fixed preamble into all agent system prompts.
- Constitution changes are versioned; the chapter number at which each version became active is recorded.
- The Consistency critique dimension (§6.1) explicitly evaluates against these rules.

---

## 5. Scalability

### 5.1 Parallelization

```
Prefect Flow
  ├── generate_arc(0)  ─┐
  ├── generate_arc(1)   ├─ .submit() runs arcs in parallel via Prefect task runner
  └── generate_arc(2)  ─┘
        ├── LangGraph: chapters K, K+1, K+2 in parallel (Send API fan-out)
        │       └── scenes within each chapter in parallel
        └── @task sequence_analyzer()  ← periodic (every 10 chapters), Prefect-scheduled
```

- **Arc-level parallelism**: Prefect `.submit()` dispatches independent arcs concurrently across workers.
- **Scene-level parallelism**: LangGraph `Send` API fans out independent scenes within a chapter concurrently.
- **Arc-level pre-planning**: While Arc N is being written, Arc N+1's plan is computed ahead of time.
- **Read-only memory reads**: All vector retrieval calls are parallel; only writes are serialized.
- **Periodic analysis**: `SequenceAnalyzer` runs as a Prefect `@task` every N chapters (§6.4), outside the LangGraph graph.

### 5.2 Cost & Batching

| Strategy | Implementation |
|---|---|
| **Prompt caching** | Pin the novel plan + arc summary in cache (Anthropic prompt caching / OpenAI seed cache) |
| **Model tiering** | Use a large model (GPT-4o / Claude 3.5) for planning; smaller model (GPT-4o-mini) for scene generation |
| **Batch generation** | Queue 10–20 scene generation tasks and dispatch in parallel via async workers |
| **Incremental writes** | Commit each chapter to storage immediately; no buffering entire arcs in memory |
| **Deferred critique** | Dispatch Critique Agent calls asynchronously in batches of up to 5 for throughput efficiency; each chapter retains an individually attributed score |
| **Token cost tracking** | Prefect tasks log LLM token usage per arc; set budget alerts via Prefect notifications |
| **Context budget monitoring** | Every generation call emits a `ContextBudgetReport` (§4.2); alerts on sustained 100% tier utilization |
| **Length telemetry** | Per-chapter word count logged to `chapter_metrics` table; alert on >20% arc-level drift from target |

### 5.3 Checkpointing & Recovery

Three independent checkpoint layers cooperate for maximum durability:

| Layer | Mechanism | Granularity | Owned by |
|---|---|---|---|
| **Arc-level** | Prefect flow state (SQLite / Postgres) | Per arc task | Prefect |
| **Chapter-level** | LangGraph `PostgresSaver` | Per committed chapter | LangGraph |
| **Changeset log** | Append-only changeset table (Postgres) | Per chapter generation run | StateValidatorAgent |

**Chapter states:** `draft` → `validated` → `committed` | `state-degraded`

- `draft` — prose generated, changeset staged, not yet validated.
- `validated` — StateValidatorAgent has approved the changeset; ready to commit.
- `committed` — prose persisted + changeset applied atomically.
- `state-degraded` — prose committed but changeset rejected; entity state frozen at previous snapshot.

**`state-degraded` handling:**
- Changeset is discarded; entity state remains at `previous_state_snapshot`.
- A `state.degraded` webhook event is dispatched.
- The LangGraph graph enters an `await_repair` branch; Prefect marks the arc task as `PAUSED`.
- Retry/escape policy: maximum 3 repair attempts within 24h; if exceeded, escalate to `MANUAL_BLOCKED` and notify on-call.
- Operator provides a corrected state delta via human-in-the-loop endpoint; arc resumes.

On any crash:
1. Prefect retries the failed arc task (up to `retries=3`).
2. LangGraph resumes from the last committed chapter inside that arc using the stable `thread_id`.
3. No chapter is re-generated unless it was mid-write at crash time (at most one chapter lost).

---

## 6. Quality Control

### 6.1 Evaluation Rubrics

The Critique Agent scores each chapter across six dimensions (1–10):

| Dimension | Key Signals |
|---|---|
| **Emotional depth** | Character motivation clarity, stakes escalation, subtext; scored against the pre-computed emotion curve target band (§2.1) — chapters outside the `allowed_band` are flagged |
| **Narrative coherence** | Cause-effect chains, foreshadowing payoff (cross-referenced with ForeshadowingRegistry §4.5 — overdue items increase severity), scene purpose |
| **Stylistic variation** | Sentence length variance, vocabulary richness, POV stability; includes AI Tell Detection (see §6.3) |
| **Originality** | Semantic similarity vs. prior chapters (embedding cosine distance) |
| **Consistency** | Fact alignment with character/world KV store + Novel Constitution compliance (§4.6) |
| **Plan Compliance** | Does the chapter contain the planned key events? Were planned character arcs advanced? Were planned reveals executed? Did the chapter fulfill its designated Strand Weave role (§6.3)? |

**Plan Compliance scoring:**
- 8–10: All major plan elements executed; any deviation improves on the plan.
- 5–7: Most plan elements executed; minor omissions.
- 3–4: Key plan elements omitted; chapter diverges significantly.
- 1–2: Chapter bears no recognizable relationship to its plan.

**Reader Persona Simulation** *(optional critique mode)*:

After scoring, the Critique Agent can run a `ReaderPersonaSimulation` pass that evaluates the chapter from 5 reader perspectives:

| Persona | Core concern | `abandon_triggers` |
|---|---|---|
| **Casual** | Easy, fast, enjoyable | ">3 chapters with no event", "unfamiliar proper nouns without explanation" |
| **Hardcore** | Logic, world rules, consistency | "world rule violated", "plot hole", "power level inconsistency" |
| **Emotional** | Character depth, relationships | "character acts against established personality", "relationship stagnant >20 ch" |
| **Thrill-seeker** | Action, reveals, escalation | "no meaningful event for 2 chapters", "tension flat for 5 chapters" |
| **Critic** | Prose quality, originality | "formulaic prose", "repeated phrase patterns", "AI-tell detected" |

Persona output: `abandon_risk` per persona (`low` / `medium` / `high` / `critical`). `critical` from any persona blocks commit; `high` from 2+ personas logs a warning and injects into next chapter’s planning context. Rollout default: every 5 chapters; move to every chapter after cost/latency SLOs are met.

### 6.2 Refinement Loop

```
generate_chapter (Scene Generator)
      ↓
critique_chapter  →  score ≥ threshold?  →  YES ─┐
      ↓ NO                                       │
  identify_failures (low-score dimensions)        │
      ↓                                           │
  Plan Compliance < 5?                            │
      ↓ YES → Editor Agent revises draft           │
              with original ChapterPlan            │
      ↓                                           │
  editor_agent rewrites flagged sections          │
      ↓                                           │
  re-critique  →  revision_count < 3?  → loop    │
                       ↓ NO                       │
              escalate to human review queue       │
                                                   │
  ───────────────────────────────────────────
  │  Post-critique gates (run sequentially)  │──┘
  │                                           │
  │  1. Reader Persona Simulation (§6.1)       │
  │     critical → block, trigger Editor       │
  │                                           │
  │  2. Length Governance                      │
  │     hard violation → re-generate            │
  │     soft violation → LengthNormalizerAgent  │
  │     within bounds → pass                    │
  │                                           │
  │  3. State Validation (§3.4)                │
  │     valid → apply changeset atomically      │
  │     invalid → retry once, then state-degraded│
  │                                           │
  └───────────────────────────────────────────
      ↓
  commit_chapter
      ↓
  Memory Manager: summarize + index + update foreshadowing registry (§4.5)
```

**Length governance spec:**
```python
class LengthSpec(BaseModel):
    target_words: int         # planning target from Chapter Planner
    soft_min: int             # target * 0.75 — triggers LengthNormalizerAgent
    soft_max: int             # target * 1.25 — triggers LengthNormalizerAgent
    hard_min: int             # target * 0.5 — blocks commit, requires regeneration
    hard_max: int             # target * 1.75 — blocks commit, requires regeneration
```

### 6.3 Anti-Repetition Mechanisms

- **Phrase fingerprinting**: A rolling bloom filter of 3-gram hashes from the last 20 chapters. Scene Generator's prompt is seeded with "avoid these constructions: [top 10 overused phrases]".
- **Structural diversity**: Chapter Planner tracks the distribution of scene types (action / dialogue / introspection / exposition) across the last arc and enforces variety.
- **Strand Weave pacing**: Before each chapter is planned, the Arc Manager evaluates the strand balance of the last 20 chapters and injects constraints into the Chapter Planner:

  | Strand | Content | Target Ratio | Red Line |
  |---|---|---|---|
  | **Quest** | Main conflict, plot progress, action | 60% | >5 consecutive Quest-dominant chapters |
  | **Fire** | Character relationships, emotions, interiority | 20% | >10-chapter gap without a Fire chapter |
  | **Constellation** | World-building, lore, history, culture | 20% | >15-chapter gap without a Constellation chapter |

  Each committed chapter receives a strand label (`quest`, `fire`, `constellation`, or `mixed`) from the Critique Agent. Enforcement levels: `advisory` (preference), `required` (must include), `red_line` (bounded retry budget `max_plan_retries=3`, then escalate to human review).

- **AI Tell Detection**: The Critique Agent's Stylistic Variation dimension specifically targets AI-characteristic structural signatures:

  | Pattern | Signal |
  |---|---|
  | `FormulaicOpening` | >30% of recent chapters open with [Setting + Character + Action] template |
  | `CliffhangerUniformity` | Cliffhangers in same grammatical form for N consecutive chapters |
  | `ParagraphLengthUniformity` | Paragraph length variance < threshold across the chapter |
  | `TransitionPhraseReuse` | High frequency of "Meanwhile...", "Suddenly..." etc. |
  | `EmotionNaming` | Directly naming emotions rather than showing them |
  | `ClichéDensity` | Per-genre cliché phrase frequency above threshold |

  Detected tells are passed to the Editor Agent with specific rewrite instructions. AI Tell rate is tracked per-chapter in `chapter_metrics`; rising trends trigger a `SequenceAnalyzer` alert (§6.4).

### 6.4 Sequence-Level Defect Detection

A `SequenceAnalyzer` agent runs every N chapters (configurable, default 10) as a Prefect `@task` on a sliding window of recent chapter metadata (summaries, opening/closing sentences, emotion scores, strand labels).

**Defect categories:**

| Defect | Trigger |
|---|---|
| `PacingMonotony` | Emotion intensity variance < threshold for N consecutive chapters |
| `MoodMonotony` | Same dominant emotional register for N chapters |
| `OpeningPatternRepetition` | ≥3 chapters in last 10 share same structural opening |
| `EndingPatternRepetition` | ≥3 chapters in last 10 share same structural ending |
| `TitleCollapse` | Duplicate or near-duplicate chapter titles |
| `StrandImbalance` | Strand ratio violates Strand Weave red lines |
| `NeglectedCharacter` | Major character absent from last N chapters |

Detected defects are injected into the Chapter Planner’s context for the next chapter as avoidance instructions. Severe defects (e.g., 20-chapter `PacingMonotony`) trigger a Prefect notification and write to human review queue.

---

## 7. Framework Choice: Prefect + LangGraph

The system uses two complementary frameworks — each the best tool for its layer.

### 7.1 LangGraph (inner agent control flow)

| Requirement | How LangGraph Addresses It |
|---|---|
| Cyclic revision loops | Native support for graph cycles with conditional edges |
| Persistent mid-arc state | Built-in `PostgresSaver` checkpointing per chapter node |
| Agent fan-out (parallel scenes) | `Send` API for dynamic parallel node dispatch |
| Human-in-the-loop editorial | `interrupt_before` / `interrupt_after` breakpoints |
| Streaming output | Token-level streaming from any node |
| Observability (agent traces) | LangSmith integration for full trace visibility |

### 7.2 Prefect (outer run management)

| Requirement | How Prefect Addresses It |
|---|---|
| Multi-arc scheduling | `@flow` with `@task` per arc; cron or event-triggered runs |
| Infrastructure-level retries | `retries=3` per task; arc restarts without replaying prior arcs |
| Live progress dashboard | Prefect UI — arc status, ETA, failure alerts |
| Cost tracking | Log LLM token usage per task; set budget notifications |
| Deployment | `prefect deploy` to cloud workers; no manual server management |
| Arc-level parallelism | `.submit()` + Prefect task runner dispatches arcs concurrently |

### 7.3 Responsibility split

| Concern | Owner |
|---|---|
| Scheduling, cron, deployment | Prefect |
| Infrastructure retries (OOM, timeout) | Prefect |
| LLM cost/duration monitoring | Prefect |
| Agent typed state (StoryBible, snapshots) | LangGraph `TypedDict` |
| Critique-revision cycles | LangGraph graph cycles |
| Scene-level parallelism | LangGraph `Send` API |
| Chapter-level checkpoint/resume | LangGraph `PostgresSaver` |
| Arc-level checkpoint/resume | Both (Prefect flow state + LangGraph `thread_id`) |

**Alternatives considered**: CrewAI lacks native checkpointing at 10,000-chapter scale. AutoGen's conversation model is less suited to structured hierarchical generation. Temporal.io offers stronger durability guarantees but higher ops overhead and a less mature Python SDK. The Prefect + LangGraph combination wins on control-flow expressiveness, operational visibility, and ecosystem maturity.

---

## 8. Extensibility

### 8.1 Plugin Architecture

Agents are registered via a **plugin manifest**:

```python
@register_agent(
    name="translation_agent",
    trigger="post_commit",         # hook point
    input_fields=["committed_chapter"],
    output_fields=["translated_chapter"],
)
class TranslationAgent(BaseNovelAgent):
    def invoke(self, state: NovelState) -> dict: ...
```

New agents declare their hook point (`pre_plan`, `post_generate`, `post_commit`, `on_critique_fail`). The orchestrator injects them into the graph at the declared position without modifying existing nodes.

**Genre Profile** — a pre-installed plugin type loaded once at novel initialization:

```yaml
genre: webnovel
pacing_model: wave          # emotion curve model (§2.1)
strand_ratios:              # override default Strand Weave ratios (§6.3)
  quest: 0.65
  fire: 0.20
  constellation: 0.15
chapter_length:             # default LengthSpec (§6.2)
  target_words: 3000
  hard_min: 2000
  hard_max: 5000
forbidden_patterns:         # injected into AI Tell detection (§6.3)
  - "protagonist was transported to another world"  # only in ch 1
style_conventions:
  - "End every 5–10 chapters with a meaningful upgrade or reveal"
```

Genre profile values override design-level defaults. The project’s Novel Constitution (§4.6) can further override genre profile values for project-specific rules.

### 8.2 Swappable Components

| Component | Interface | Swap Example |
|---|---|---|
| LLM backend | `BaseChatModel` | Swap GPT-4o → Claude 3.7 per agent |
| Vector store | `VectorStoreRetriever` | Qdrant → Weaviate |
| Summary strategy | `SummarizationStrategy` | Extractive → abstractive |
| Critique rubric | `RubricSet` | Add domain-specific rubrics (e.g., hard sci-fi accuracy) |
| Output contract | `OutputContract` (Pydantic schema) | Swap per-agent response schema; configure retry budget (§3.5) |
| Genre profile | `GenreProfile` (YAML) | Swap `webnovel.yaml` → `romance.yaml` at novel init (§8.1) |

### 8.3 Extension Points Summary

```
Novel Generation Pipeline
  ├── pre_plan hooks         (e.g., genre constraint injector, genre profile loader)
  ├── post_plan hooks        (e.g., sensitivity reviewer)
  ├── post_generate hooks    (e.g., real-time translator)
  ├── on_critique_fail hooks (e.g., Slack alert, human queue)
  ├── on_state_degraded hooks (e.g., PagerDuty alert, auto-rollback, repair queue)
  └── post_commit hooks      (e.g., epub exporter, TTS synthesizer)
```

---

## 9. Data Flow Summary

```
User Input (genre, themes, seed)
        ↓
  ╔══════════════════════════════════════╗
  ║  Prefect Flow: generate_novel()      ║
  ║                                      ║
  ║  @task plan_novel()                  ║
  ║    └─ load Genre Profile (§8.1)       ║
  ║    └─ generate Emotion Curve (§2.1)   ║
  ║    └─ load Novel Constitution (§4.6)  ║
  ╠══════════════════════════════════════╣
  ║  @task generate_arc(arc_id)  ×N     ║  ← retries=3; resumes via LangGraph thread_id
  ║                                      ║
  ║  ┌── LangGraph graph.invoke() ────┐  ║
  ║  │                                │  ║
  ║  │  Novel Planner → NovelPlan     │  ║
  ║  │        ↓                       │  ║
  ║  │  Arc Manager (loop per arc)    │  ║
  ║  │    → ArcPlan + strand status   │  ║  ← Strand Weave §6.3
  ║  │        ↓                       │  ║
  ║  │    Chapter Planner             │  ║
  ║  │      + foreshadowing context    │  ║  ← §4.5
  ║  │      + emotion target           │  ║  ← §2.1
  ║  │      → ChapterPlan             │  ║
  ║  │          ↓                     │  ║
  ║  │      Memory Manager             │  ║
  ║  │      → fractal retrieval (§4.2) │  ║  ← 3-tier + reranker
  ║  │      → ContextBudgetReport      │  ║
  ║  │          ↓                     │  ║
  ║  │      Scene Generator × N (∥)   │  ║
  ║  │      → ContractEnforcer (§3.5)  │  ║
  ║  │          ↓                     │  ║
  ║  │      Character Manager +       │  ║
  ║  │      World Builder → changeset  │  ║  ← §3.4
  ║  │          ↓                     │  ║
  ║  │      Style Agent → polish      │  ║
  ║  │          ↓                     │  ║
  ║  │      Continuity Guard          │  ║
  ║  │          ↓                     │  ║
  ║  │      Critique Agent → score    │  ║  ← 6 dimensions + persona sim
  ║  │          ↓ (fail)              │  ║
  ║  │      Editor Agent → revise ────┤  ║  ← LangGraph cycle
  ║  │          ↓ (pass)              │  ║
  ║  │      Length check (§6.2)        │  ║
  ║  │          ↓                     │  ║
  ║  │      StateValidator (§3.4)      │  ║  ← validate changeset
  ║  │          ↓                     │  ║
  ║  │      Memory Manager             │  ║
  ║  │      → summarize + index        │  ║
  ║  │      → update foreshadowing     │  ║  ← §4.5
  ║  │          ↓                     │  ║
  ║  │      Commit chapter             │  ║
  ║  │      → LangGraph checkpoint     │  ║
  ║  └────────────────────────────────┘  ║
  ╠══════════════════════════════════════╣
  ║  @task sequence_analyzer()  periodic ║  ← every 10 chapters §6.4
  ║  @task assemble_manuscript()         ║
  ║  @task quality_report()              ║
  ╚══════════════════════════════════════╝
```

---

## 10. Technology Stack

| Layer | Technology |
|---|---|
| **Run management** | Prefect (scheduling, retries, dashboard, deployment) |
| **Agent orchestration** | LangGraph + LangChain |
| **Contract enforcement** | ContractEnforcer (§3.5) — Pydantic schema validation + parse retry |
| LLM (planning) | Claude 3.7 Sonnet / GPT-4o |
| LLM (generation) | GPT-4o-mini / Gemini Flash |
| Vector store | Qdrant (self-hosted) or pgvector |
| Reranker | Jina Reranker v3 (or compatible) — two-stage RAG (§4.2) |
| Structured store | PostgreSQL |
| Cache | Redis |
| Checkpointing (chapter-level) | LangGraph PostgresSaver |
| Checkpointing (arc-level) | Prefect flow state (Postgres backend) |
| Changeset log | Append-only Postgres table (§3.4, §5.3) |
| Context budget log | Time-series Postgres table (§4.2) |
| Long-term keyword index | Postgres table (chapter_id, keyword, frequency) (§4.3) |
| Agent observability | LangSmith |
| Run observability | Prefect UI |
| Serving | FastAPI + Celery workers |
| **Web frontend** | React + Next.js (App Router), TypeScript |
| Frontend auth | JWT stored in HTTP-only cookie; role-based routing |
| Real-time updates | Polling (default) or WebSocket (opt-in) |
| Storage | S3-compatible object store (chapter archives) |

---

## 11. Frontend Architecture

The web application is a **Next.js (App Router)** project written in TypeScript. It communicates exclusively with the FastAPI REST API at `/v1/` and never accesses the database or LLM providers directly.

### 11.1 Deployment Topology

```
Browser
  │
  ├── Next.js Web App  (Docker container; port 3000)
  │     ├── Writer Portal     /app/writer/...
  │     └── Operator Dashboard /app/operator/...
  │
  └── (all data requests) → FastAPI /v1/   (port 8000)
```

### 11.2 Route Structure

| Route | View | Required Role |
|-------|------|---------------|
| `/login` | Auth page | Public |
| `/writer/novels` | Novel list | `reader`+ |
| `/writer/novels/[id]` | Novel setup & constitution | `reader`+ |
| `/writer/novels/[id]/progress` | Generation dashboard | `reader`+ |
| `/writer/novels/[id]/chapters` | Chapter browser + reader | `reader`+ |
| `/writer/novels/[id]/review` | Human review queue | `reader`+ |
| `/writer/novels/[id]/world` | World & character explorer | `reader`+ |
| `/operator` | System overview | `operator`+ |
| `/operator/novels/[id]` | Arc monitoring + cost | `operator`+ |
| `/operator/quality` | Quality analytics | `operator`+ |
| `/operator/review` | Review queue management | `operator`+ |

### 11.3 Auth Flow

1. User POSTs credentials to `POST /v1/auth/token` → receives JWT.
2. JWT is stored in an HTTP-only cookie (not `localStorage`).
3. Next.js middleware reads the cookie on every server-side render and redirects unauthenticated or under-privileged requests to `/login`.
4. All API calls from client components attach the JWT as a `Bearer` token via a shared `apiClient` wrapper.

### 11.4 Real-Time Updates

Generation progress and review queue changes are surfaced via short-poll (default 5 s interval). If the backend exposes a WebSocket endpoint, the frontend can switch to WebSocket push without page changes — the `useGenerationStatus` hook abstracts the transport.

### 11.5 Key Conventions

- **No direct DB access** — the frontend is a pure REST client.
- **No secrets in the browser** — API keys stay backend-only; `NEXT_PUBLIC_*` env vars contain only non-sensitive config (API base URL).
- **Confirmation gates** — all destructive actions (override, regenerate, retry arc) render a `<ConfirmDialog>` before calling the API.
- **Error boundary** — all pages wrap data fetchers in an error boundary that renders a user-friendly message, never a raw API error.