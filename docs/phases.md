# AI Novel Generation System: Development Phases

This document defines the phased development plan. Each phase has a clear scope, success metric, and explicit list of what is deferred. The principle throughout: build the minimum that teaches you something real, then add the next layer.

**Core decisions driving this plan:**
- File-based storage first; databases only when files become a bottleneck
- Structured pipeline (code controls flow, LLM generates content) — not autonomous agent
- Manual context assembly — you assemble what goes into the context window; LangGraph checkpointing for orchestration durability only, added in Phase 3
- Backend-first; frontend is Phase 5
- Test via scripts → CLI → FastAPI `/docs` at each phase

---

## Phase 1 — Linear Generation

**Goal:** Generate a readable, coherent short story end-to-end. Nothing else.

**Duration:** 2–4 weeks

### What you build

| Component | Implementation |
|---|---|
| Novel Planner | LLM call → writes `novel_plan.json` |
| Chapter Planner | LLM call → writes `arcs/arc_01/ch_001_plan.json` |
| Scene Generator | LLM call → writes `chapters/ch_001.md` |
| Context assembly | Manual: always include `constitution.md` + `novel_plan.json` + current chapter plan |
| World & characters | Hand-written `world.yaml` + `characters/*.json` — no agent yet |
| Orchestration | Plain Python functions, sequential, no graph |
| Storage | Files only. `git` is your version control and rollback. |

### File layout
```
/novel/
  constitution.md
  novel_plan.json
  world.yaml
  characters/
    elena.json
  arcs/
    arc_01/
      arc_plan.json
      ch_001_plan.json
      ch_002_plan.json
  chapters/
    ch_001.md
    ch_002.md
```

### How you test
```bash
python run.py --seed "A detective in a cyberpunk city" --chapters 3
# Output: chapters/ch_001.md, ch_002.md, ch_003.md — read them.
```

### Context window strategy
```python
def build_context(chapter_id):
    return [
        load("constitution.md"),          # always present
        load_json("novel_plan.json"),     # always present
        load_json(f"characters/"),        # all character snapshots (small)
        load("world.yaml"),               # always present
        load_json(f"ch_{chapter_id}_plan.json"),  # current chapter plan
    ]
```

No retrieval, no summaries, no vector search — the novel is short enough that everything fits.

### Success metric
> Can you generate a 3-chapter story that a human finds readable and internally consistent?

### Deliberately deferred
- Critique loop, Editor Agent
- Character Manager agent (use static files)
- World Builder agent (use static `world.yaml`)
- LangGraph (plain function calls only)
- Databases
- CLI or API

---

## Phase 2 — Quality Loop + Short-Term Memory

**Goal:** Generate output that is measurably better with the critique-revision cycle. Maintain continuity across ~10 chapters.

**Duration:** 4–6 weeks

### What you add

| Component | Implementation |
|---|---|
| Critique Agent | Scores chapter on 3–4 dimensions; writes `chapters/ch_001_meta.json` |
| Editor Agent | Rewrites flagged sections; revision loop max 3 cycles |
| Chapter summaries | Memory Manager writes `chapters/ch_001.summary.txt` after each commit |
| Character Manager | Updates `characters/*.json` after each chapter (simple overwrite, no changesets) |
| LangGraph | Introduces graph + cycles for the critique-revise loop; `SqliteSaver` for chapter-level checkpointing |
| Context assembly | Extend: inject last 5–8 chapter summaries into each generation call |

### Context window strategy (extended)
```python
def build_context(chapter_id):
    return [
        load("constitution.md"),
        load_json("novel_plan.json"),
        load_json("characters/"),
        load("world.yaml"),
        load_recent_summaries(n=8),       # chapters/ch_XXX.summary.txt — newest first
        load_json(f"ch_{chapter_id}_plan.json"),
    ]
```

### How you test
- Scripts as before; add Jupyter notebooks to plot critique scores across chapters
- Compare with/without critique loop on the same seed to validate quality improvement

```bash
python run.py --chapters 10
python eval.py --novel-dir ./novel --report quality_report.json
# Opens quality_report.json: per-chapter critique scores, revision counts, word counts
```

### Success metric
> Do critique scores improve with the revision loop? Does character state remain consistent across 10 chapters without manual correction?

### Deliberately deferred
- Arc Manager (chapter planner still owns pacing)
- Vector DB / semantic retrieval (rolling summaries are enough at this scale)
- Foreshadowing registry
- Strand Weave
- FastAPI

---

## Phase 3 — Arc & Novel Scale

**Goal:** Generate a 50-chapter novel without world or character drift. Runs are long enough that crashes must be resumable.

**Duration:** 4–6 weeks

### What you add

| Component | Implementation |
|---|---|
| Arc Manager | Plans and tracks tension/pacing across chapters within an arc; writes `arcs/arc_01/arc_plan.json` |
| Hierarchical summaries | Recent (last 10 full), mid-range (ch 11–50: compressed), long-term (keyword index in SQLite) |
| Continuity Guard | Diffs new chapter against character/world state; flags anomalies before commit |
| Semantic retrieval | `sqlite-vec` (or in-memory numpy) over chapter summaries for top-K context selection |
| LangGraph checkpointing | `SqliteSaver` — persist arc/chapter state so crashed runs resume from last committed chapter |
| FastAPI REST API | Trigger runs, poll status, fetch chapters; test via `/docs` Swagger UI — no frontend needed |

### Context window strategy (extended)
```python
def build_context(chapter_id, novel_state):
    recent  = load_summaries(last_n=10)          # full summaries
    mid     = load_summaries(range=range(11,50)) # compressed
    long_kw = keyword_search(novel_state.chapter_plan, top_k=5)  # SQLite keyword index
    return [
        load("constitution.md"),
        load_json("novel_plan.json"),
        load_json("arcs/arc_01/arc_plan.json"),
        load_json("characters/"),
        *recent, *mid, *long_kw,
        load_json(f"ch_{chapter_id}_plan.json"),
    ]
```

### How you test
```bash
# Trigger via CLI or Swagger
python cli.py generate --chapters 50 --resume  # resumes from last checkpoint if crashed
python cli.py status --novel-id abc123
curl http://localhost:8000/v1/novels/abc123/chapters/42
```

### Success metric
> Does a 50-chapter novel maintain character consistency and world coherence without manual correction?

### Deliberately deferred
- Foreshadowing registry
- Strand Weave / AI Tell Detection
- Sequence Analyzer
- Two-stage reranker (embedding + Jina) — benchmark whether sqlite-vec alone is sufficient first
- StateChangeset validation protocol — simple file overwrites are sufficient until you see actual rollback needs

---

## Phase 4 — Quality Hardening

**Goal:** Output that passes a blind reader test. Eliminate AI-tell patterns, pacing monotony, and unresolved foreshadowing.

**Duration:** 4–6 weeks

### What you add

| Component | Implementation |
|---|---|
| Foreshadowing Registry | `foreshadowing.json` — lifecycle: planted → developing → revealed |
| Strand Weave enforcement | Arc Manager tracks quest/fire/constellation ratios; injects constraints into Chapter Planner |
| AI Tell Detection | Critique Agent checks structural signatures (formulaic openings, paragraph uniformity, cliché density) |
| Sequence Analyzer | Runs every 10 chapters; detects pacing monotony, repeated opening/ending patterns |
| Emotion Curve scoring | Pre-computed intensity targets; Critique Agent scores chapter against target band |
| Automated eval harness | End-to-end benchmark: generate N chapters, score all dimensions, output trend report |

### How you test
```bash
python eval.py --chapters 100 --report eval_report.json
# Outputs: per-chapter scores, AI-tell rate trend, strand balance chart, open foreshadowing loops
```

### Success metric
> Does a human reader, blind to generation method, rate the output as engaging and consistent?

---

## Phase 5 — Production & Frontend

**Goal:** A usable product with a web interface for writers and operators.

**Duration:** Ongoing

### What you add
- React + Next.js frontend: novel setup, generation dashboard, chapter browser, review queue
- Operator view: arc monitoring, quality analytics
- Human-in-the-loop: review queue for escalated critique failures
- Upgrade storage if needed: Postgres + Qdrant only if SQLite becomes a bottleneck (measure first)

---

## Features Parked Indefinitely

These are in the design doc but should not be built until a specific measured need arises:

| Feature | Why deferred |
|---|---|
| `StateChangeset` validation protocol (§3.4) | Complex; simple file overwrites work until you observe actual state corruption requiring rollback |
| Two-stage reranker (Jina) | Benchmark embedding-only retrieval first; add reranker only if recall quality is measurably hurting generation |
| Genre Profile plugin system | Hardcode one genre; extract abstraction when you have the second genre |
| Redis cache | In-memory dict + files covers all caching needs until multi-process scale |
| Reader Persona Simulation | Optional critique mode; expensive; add only after baseline quality is solid |
| Multi-volume emotion curve overlay | Unnecessary until you are generating multi-volume works |

---

## Infrastructure Evolution

| Phase | Storage | Orchestration | Testing |
|---|---|---|---|
| 1 | Files + git | Python functions | `python run.py` |
| 2 | Files + SQLite (LangGraph) | LangGraph + SqliteSaver | Scripts + Jupyter |
| 3 | Files + SQLite + sqlite-vec | LangGraph + arc runner | CLI + FastAPI `/docs` |
| 4 | As Phase 3 | As Phase 3 | Automated eval harness |
| 5 | Postgres + Qdrant (if needed) | As Phase 3 | Playwright + API tests |
