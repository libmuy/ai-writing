# Phase 5 Design: Production & Frontend

**Goal:** A usable product with a web interface for writers and operators. Harden infrastructure where SQLite/files become bottlenecks.  
**Builds on:** [design-phase4.md](design-phase4.md) — full quality pipeline, FastAPI REST API.

---

## 1. What Gets Added

| Component | Purpose |
|---|---|
| **React + Next.js frontend** | Writer portal + operator dashboard |
| **Human review queue UI** | Review and resolve escalated chapters |
| **Infrastructure upgrade path** | Postgres, Qdrant, Redis — only if SQLite/files are measured to be insufficient |
| **Plugin architecture** | Genre Profile plugins — only when second genre is needed |
| **S3-compatible archive** | Long-term chapter storage and export |

---

## 2. Frontend Architecture

The web application is a **Next.js (App Router)** project written in TypeScript. It communicates exclusively with the FastAPI REST API at `/v1/` and never accesses the database or LLM providers directly.

### Deployment topology

```
Browser
  │
  ├── Next.js Web App  (Docker container; port 3000)
  │     ├── Writer Portal      /app/writer/...
  │     └── Operator Dashboard /app/operator/...
  │
  └── (all data requests) → FastAPI /v1/  (port 8000)
                                  │
                           Novel generation pipeline
                           (LangGraph + agents + SQLite/files)
```

### Route structure

| Route | View |
|---|---|
| `/writer/novels` | Novel list |
| `/writer/novels/[id]` | Novel setup & constitution editor |
| `/writer/novels/[id]/progress` | Generation dashboard (arc progress, chapter statuses) |
| `/writer/novels/[id]/chapters` | Chapter browser + reader |
| `/writer/novels/[id]/review` | Human review queue |
| `/writer/novels/[id]/world` | World & character explorer |
| `/operator` | System overview |
| `/operator/novels/[id]` | Arc monitoring + cost |
| `/operator/quality` | Quality analytics (score trends, AI tell rate, strand balance) |
| `/operator/review` | Review queue management |

### Real-time updates

Short-poll at 5s interval (default). If the backend exposes a WebSocket endpoint, the `useGenerationStatus` hook switches to WebSocket push without page changes.

### Key conventions

- **No direct DB access** — the frontend is a pure REST client.
- **No secrets in the browser** — API keys stay backend-only; `NEXT_PUBLIC_*` env vars contain only non-sensitive config (API base URL).
- **Confirmation gates** — all destructive actions (override, regenerate, retry arc) render a `<ConfirmDialog>` before calling the API.
- **Error boundary** — all pages wrap data fetchers in an error boundary that renders a user-friendly message, never a raw API error.

---

## 3. Infrastructure Upgrade Path

Upgrade only when a specific measured bottleneck requires it. Default: stay on SQLite + files.

| Current (Phase 1–4) | Upgrade to | When to upgrade |
|---|---|---|
| `sqlite-vec` embeddings | Qdrant (self-hosted) or pgvector | `sqlite-vec` query latency >500ms at scale, or multi-host deployment needed |
| SQLite checkpoints + metrics | PostgreSQL | Multi-worker concurrency causes SQLite write contention |
| In-memory dict caching | Redis | Multi-process deployment with shared cache needed |
| File storage | S3-compatible object store | Novel archive files exceed local disk, or multi-host access needed |
| Jina Reranker | Add on top of Qdrant | Recall quality measurably insufficient with embedding-only retrieval |

**Default recommendation:** Do not upgrade until you measure a problem. A single-process novel generation system running locally or on a single VM is unlikely to hit SQLite or file system limits.

---

## 4. Plugin Architecture (Genre Profiles)

Only build when you have a second genre that needs different defaults. Until then, hardcode the genre values in `novel_plan.json`.

When needed, Genre Profile is a YAML file loaded once at novel initialization:

```yaml
genre: webnovel
pacing_model: wave
strand_ratios:
  quest: 0.65
  fire: 0.20
  constellation: 0.15
chapter_length:
  target_words: 3000
  hard_min: 2000
  hard_max: 5000
forbidden_patterns:
  - "protagonist was transported to another world"
style_conventions:
  - "End every 5–10 chapters with a meaningful upgrade or reveal"
```

Genre profile values are merged into `novel_plan.json` at init. The project's `constitution.md` overrides genre profile values for project-specific rules.

### Extension points

Once plugin architecture exists, agents can register hooks:

```
Novel Generation Pipeline
  ├── pre_plan hooks         (e.g., genre constraint injector)
  ├── post_plan hooks        (e.g., sensitivity reviewer)
  ├── post_generate hooks    (e.g., real-time translator)
  ├── on_critique_fail hooks (e.g., alert, human queue)
  └── post_commit hooks      (e.g., epub exporter, TTS synthesizer)
```

---

## 5. State Mutation Protocol (Revisit)

The `StateChangeset` validation protocol (§3.4 in `design.md`) was parked in earlier phases. Revisit in Phase 5 **only if**:
- `state-degraded` failures (character/world overwrites causing data corruption) are observed frequently in Phase 3–4 production runs, and
- The file-overwrite recovery strategy (reload from last committed file + re-run) is insufficient

If needed, the protocol stages entity state changes as structured changesets validated by `StateValidatorAgent` before applying — enabling atomic rollback without re-generation. This adds significant complexity; only build it if you have a demonstrated need.

---

## 6. Technology Stack (Full)

| Component | Choice | Phase |
|---|---|---|
| LLM (planning/critique) | Claude Sonnet | 1 |
| LLM (generation/edit) | Claude Haiku | 2 |
| File storage | `characters/*.json`, `chapters/*.md`, `world.yaml` | 1 |
| Orchestration | LangGraph + `SqliteSaver` + `asyncio` | 2 |
| Output validation | Pydantic v2 + `ContractEnforcer` | 2 |
| API | FastAPI + `uvicorn` | 3 |
| Semantic retrieval | `sqlite-vec` | 3 |
| Observability | LangSmith | 2 |
| **Web frontend** | React + Next.js (App Router), TypeScript | 5 |
| Real-time updates | Polling → WebSocket | 5 |
| Vector store | Qdrant / pgvector | 5 (if sqlite-vec insufficient) |
| Structured store | PostgreSQL | 5 (if SQLite insufficient) |
| Cache | Redis | 5 (if in-memory insufficient) |
| Reranker | Jina Reranker v3 | 5 (if recall insufficient) |
| Archive storage | S3-compatible | 5 |

---

## 7. Success Metric

> Writers can manage novel generation, browse chapters, and resolve review queue items entirely through the web UI without using the CLI.

Phase 5 is done when the system is end-to-end usable as a product.
