# Phase 4 Design: Quality Hardening

**Goal:** Output that passes a blind reader test. Eliminate AI-tell patterns, pacing monotony, and unresolved foreshadowing.  
**Builds on:** [design-phase3.md](design-phase3.md) — Arc Manager, 6-dimension critique, 3-tier memory, FastAPI.  
**Next phase:** [design-phase5.md](design-phase5.md) — Production & Frontend

---

## 1. What Gets Added

| Component | Purpose |
|---|---|
| **Foreshadowing Registry** | Tracks foreshadowing items lifecycle: planted → developing → revealed |
| **Strand Weave enforcement** | Arc Manager enforces quest/fire/constellation pacing balance |
| **AI Tell Detection** | Critique Agent detects AI-characteristic structural patterns |
| **Phrase Fingerprinting** | Bloom filter of 3-gram hashes; warns Scene Generator of overused constructions |
| **Sequence Analyzer** | Runs every 10 chapters; detects pacing monotony and structural repetition |
| **Emotion Curve** | Pre-computed per-chapter intensity targets; Critique Agent scores against them |
| **Reader Persona Simulation** | Optional post-critique pass evaluating from 5 reader archetypes |

---

## 2. Foreshadowing Registry

A file-backed registry (`foreshadowing.json`) tracking every foreshadowing item as a first-class entity.

```python
class ForeshadowingRecord(BaseModel):
    id: str                          # stable UUID
    description: str                 # "Elena notices the locked door in Sector 4"
    planted_chapter: int
    target_reveal_chapter: int       # estimated payoff chapter
    urgency: int                     # 1–10; updated by Arc Manager each arc
    status: Literal["planted", "developing", "partial", "revealed", "abandoned"]
    resolution_note: str | None      # filled when revealed or abandoned
```

### Integration points

**Novel Planner / Arc Manager** — declare foreshadowing items when generating arc plans; append to `foreshadowing.json`.

**Chapter Planner** — calls `get_active_foreshadowing(chapter_n)` which returns:
```python
{
  "urgent":    [...],   # urgency >= 8
  "due_soon":  [...],   # target_reveal_chapter within next 10 chapters
  "overdue":   [...],   # past target_reveal_chapter, not yet revealed
  "related":   [...],   # thematically related to current arc theme
}
```
This payload is injected into the Chapter Planner's context (~200 tokens).

**Post-commit** — Memory Manager calls `update_foreshadowing_status(chapter_n, chapter_text)`. The LLM classifies whether each active item was advanced, partially resolved, or ignored.

**Quality report** — includes: open loop count, overdue count, oldest unresolved item.

---

## 3. Strand Weave Pacing

The Arc Manager enforces a balance of content types across chapters:

| Strand | Content | Target Ratio | Red Line |
|---|---|---|---|
| **Quest** | Main conflict, plot progress, action | 60% | >5 consecutive Quest-dominant chapters |
| **Fire** | Character relationships, emotions, interiority | 20% | >10-chapter gap without a Fire chapter |
| **Constellation** | World-building, lore, history, culture | 20% | >15-chapter gap without a Constellation chapter |

**Lifecycle:**
1. Critique Agent assigns a strand label (`quest`, `fire`, `constellation`, `mixed`) to each committed chapter; saved in `ch_NNN_meta.json`.
2. Before each chapter is planned, Arc Manager evaluates the strand balance of the last 20 chapters.
3. If imbalanced, injects a `strand_constraint` into the Chapter Planner context:
   - `advisory` — preference injection ("prefer a Fire-dominant chapter")
   - `required` — strong instruction ("this chapter must include a significant Fire element")
   - `red_line` — blocks chapter plan until constraint satisfied (max 3 retries, then escalate to human review)

```python
class StrandConstraint(BaseModel):
    strand: Literal["quest", "fire", "constellation"]
    level: Literal["advisory", "required", "red_line"]
    reason: str    # e.g., "No Fire chapter in last 11 chapters"
```

---

## 4. Emotion Curve

Pre-computed at novel initialization by Novel Planner. Defines an intensity target for every chapter.

```python
class ChapterEmotionTarget(BaseModel):
    chapter_number: int
    emotion_intensity: float          # 0.0–1.0
    narrative_phase: str              # "rising_action" | "climax" | "denouement" | etc.
    is_peak: bool
    is_valley: bool
    allowed_band: tuple[float, float] # [min, max] acceptable intensity for this chapter
```

Curve models: `three_act`, `wave`, `hero_journey`, `episodic`. Stored in `novel_plan.json` under `emotion_curve`.

**Critique scoring:** The Critique Agent's Emotional Depth dimension checks the committed chapter's tone against the `allowed_band`. Chapters outside the band are flagged (not blocked — reduces to a score penalty unless the chapter is extreme).

---

## 5. AI Tell Detection

Added to the Critique Agent's Stylistic Variation dimension. Detects AI-characteristic structural signatures:

| Pattern | Signal |
|---|---|
| `FormulaicOpening` | >30% of recent chapters open with [Setting + Character + Action] template |
| `CliffhangerUniformity` | Cliffhangers in same grammatical form for N consecutive chapters |
| `ParagraphLengthUniformity` | Paragraph length variance below threshold across the chapter |
| `TransitionPhraseReuse` | High frequency of "Meanwhile…", "Suddenly…", "As if on cue…" |
| `EmotionNaming` | Directly naming emotions rather than showing them ("she felt sad") |
| `ClichéDensity` | Per-genre cliché phrase frequency above threshold |

Detected tells are passed to the Editor Agent as specific rewrite instructions. AI Tell rate tracked per chapter in `ch_NNN_meta.json`; rising trends are caught by the Sequence Analyzer.

---

## 6. Phrase Fingerprinting

A rolling set of 3-gram hashes from the last 20 committed chapters. The top-10 overused phrases are injected into the Scene Generator's prompt as avoidance hints:

```python
class PhraseFingerprint:
    def update(self, chapter_text: str): ...
    def get_overused(self, top_n: int = 10) -> list[str]: ...
```

Stored in `db/phrase_fingerprint.json` (serialized as a list of (phrase, count) pairs). Rebuilt from committed chapter files on startup.

---

## 7. Sequence Analyzer

Runs every 10 chapters (configurable) as a background task after chapter commit. Analyzes a sliding window of recent chapter metadata.

**Defect categories:**

| Defect | Trigger |
|---|---|
| `PacingMonotony` | Emotion intensity variance < threshold for N consecutive chapters |
| `MoodMonotony` | Same dominant emotional register for N chapters |
| `OpeningPatternRepetition` | ≥3 of last 10 chapters share same structural opening |
| `EndingPatternRepetition` | ≥3 of last 10 chapters share same structural ending |
| `TitleCollapse` | Duplicate or near-duplicate chapter titles |
| `StrandImbalance` | Strand ratio violates Strand Weave red lines |
| `NeglectedCharacter` | Major character absent from last N chapters |
| `RisingAITellRate` | Per-chapter AI Tell count trending upward over last 20 chapters |

Detected defects are injected into the next Chapter Planner's context as avoidance instructions. Severe defects (e.g., 20-chapter `PacingMonotony`) write to `reviews/sequence_alert.json` and trigger an operator notification.

```python
class SequenceDefect(BaseModel):
    defect_type: str
    severity: Literal["warning", "error"]
    affected_chapters: list[int]
    avoidance_instruction: str    # injected into Chapter Planner context
```

---

## 8. Reader Persona Simulation

Optional post-critique pass (runs every 5 chapters by default). Evaluates the chapter from 5 reader archetypes.

| Persona | Core concern | Abandon triggers |
|---|---|---|
| **Casual** | Easy, fast, enjoyable | ">3 chapters with no event", "unexplained proper nouns" |
| **Hardcore** | Logic, world rules, consistency | "world rule violated", "plot hole" |
| **Emotional** | Character depth, relationships | "character acts against established personality" |
| **Thrill-seeker** | Action, reveals, escalation | "no meaningful event for 2 chapters" |
| **Critic** | Prose quality, originality | "formulaic prose", "AI-tell detected" |

```python
class PersonaSimResult(BaseModel):
    chapter_number: int
    results: dict[str, Literal["low", "medium", "high", "critical"]]
    # e.g. {"casual": "low", "hardcore": "medium", "emotional": "high", ...}
    blocking_personas: list[str]    # personas with "critical" abandon_risk
```

`critical` from any persona blocks commit and triggers Editor Agent with persona feedback. `high` from 2+ personas logs a warning and injects into the next chapter's planning context.

---

## 9. NovelState (additions)

```python
class NovelState(TypedDict):
    # ... all Phase 3 fields ...
    # Phase 4 additions
    emotion_curve: list[ChapterEmotionTarget]
    strand_history: list[dict]          # per-chapter strand labels, last 20
    strand_constraint: StrandConstraint | None
    active_foreshadowing: dict          # urgent/due_soon/overdue/related
    sequence_defects: list[SequenceDefect]
    phrase_overused: list[str]          # top-10 overused 3-grams
    persona_sim_result: PersonaSimResult | None
```

---

## 10. Updated Refinement Loop

```
[generate_chapter]  ← receives strand_constraint + phrase_overused + active_foreshadowing
        ↓
[style_polish]
        ↓
[continuity_check]
        ↓
[critique_chapter]  ← 6 dimensions + emotion curve band check
    passed? ──YES──→ [reader_persona_sim]  (every 5 chapters)
        │                    │ critical → [editor_revise_persona]
       NO                    │ pass     ↓
        ↓              [length_check]
  [editor_revise]            │
        ↓              [update_state]
  (loop, max 3)              │
                       [commit_chapter]
                             ↓
                    [update_foreshadowing]
                    [update_phrase_fingerprint]
                    [write_summary]
                    [sequence_analyzer]  ← every 10 chapters
```

---

## 11. Context Window Budget (Phase 4)

```
constitution.md              ~200 tokens
novel_plan.json              ~500 tokens
arc_plan.json + emotion band ~350 tokens
world.yaml                   ~400 tokens
characters/*.json            ~400 tokens
Tier 1: last 10 summaries   ~2,000 tokens
Tier 2: mid summaries        ~480 tokens
Tier 3: long-term hits       ~300 tokens
active_foreshadowing         ~200 tokens  ← new
strand_constraint            ~100 tokens  ← new
phrase_overused hints        ~100 tokens  ← new
chapter plan                 ~300 tokens
──────────────────────────────────────────
Total                        ~5,330 tokens
```

---

## 12. Technology Stack

Same as Phase 3 — no new infrastructure required. All Phase 4 features are logic additions to existing agents, stored in existing files and SQLite tables.

New file: `db/phrase_fingerprint.json`  
New field in `ch_NNN_meta.json`: `strand_label`, `emotion_score`, `ai_tell_count`, `persona_sim`  
New file (periodic): `reviews/sequence_alert.json`

---

## 13. Success Metric

> Does a human reader, blind to generation method, rate the output as engaging and consistent?

Run the automated eval harness:
```bash
python eval.py --novel-dir ./novel --chapters 100 --report eval_report.json
```

Outputs: per-chapter scores, AI-tell rate trend, strand balance chart, open foreshadowing loops, persona simulation results.

Phase 4 is done when AI-tell rate is below threshold and the blind reader test passes.

---

## 14. What Phase 5 Adds

- React + Next.js web frontend (writer portal + operator dashboard)
- Human review queue UI
- Upgrade to Postgres + Qdrant if SQLite becomes a bottleneck (measure first)
- Plugin architecture for Genre Profiles (when second genre is needed)
- S3-compatible archive storage
