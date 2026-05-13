# Phase 1 Design: Linear Generation

**Goal:** Generate a readable, coherent short story end-to-end.
**Builds on:** nothing - this is the starting point.
**Next phase:** [design-phase2.md](design-phase2.md) - Quality Loop + Short-Term Memory

---

## 1. What Gets Built

Phase 1 has four main concerns with a simple CLI:

1. `init` - create a new novel workspace with config templates.
2. `setup` - interactive setup (synopsis, world, constitution).
3. `plan` - structure the novel into arcs and chapters.
4. `generate` - chapter generation with resume support.

High-level pipeline:

```text
init -> setup -> plan novel -> plan arc -> plan chapter -> generate
```

Interactive setup (once per novel unless reset):

```text
user provides idea -> generate synopsis candidates -> user selects -> generate world candidates -> user selects -> write constitution + world files
```

Planning (one-time, before generation; replan individual components as needed):

```text
plan novel -> novel_plan.json (arc structure)
plan arc N -> arc_plan.json (scene beats)
plan chapter M-N -> chapter plans (detailed beats)
```

Generation (sequential, with resume and range support):

```text
generate -> plan chapter N -> generate_chapter -> write chapter -> next chapter
```

Design constraints in Phase 1:

- Minimal Arc Manager (no pacing curves or tension modeling).
- No graph engine.
- No database.
- No critique loop.
- No async.
- Files are the source of truth.
- CWD-based workflow (no `--output` paths).

---

## 2. User-Facing CLI Contract

### 2.1 Commands

Treat current directory as the novel workspace (like `git` or `npm`).

```bash
cd ./novel
python run.py init
python run.py status
python run.py setup --idea "A detective in a cyberpunk city searches for her missing brother"
python run.py setup constitution --idea "revised idea text"
python run.py setup world --idea "revised idea text"
python run.py plan novel
python run.py plan arc 1
python run.py plan chapter 1-3
python run.py generate
python run.py generate 1-3
```

### 2.2 Behavior

**Setup Phase (world building):**

- `init`:
  - Creates folder structure and starter files in CWD.
  - Must be safe to re-run.
  - Must not overwrite existing user content unless `--force` is provided.

- `status`:
  - Shows current progress: `[✓] init | [✓] setup | [ ] novel plan | [ ] arc plan | [ ] chapter plans | [ ] ch_001 | [ ] ch_002 | ...`
  - Checks for presence of `constitution.md`, `world.yaml`, `novel_plan.json`, arc plans, chapter plans, and chapter files.

- `setup --idea "..."` (full setup):
  - Loads `.env` and `config.yaml` from CWD.
  - Interactive flow: generates synopsis candidates → user selects → generates world candidates → user selects → writes setup artifacts.
  - Outputs: `constitution.md`, `world.yaml` (no `novel_plan.json`).

- `setup constitution --idea "..."` (regenerate constitution only):
  - Regenerates `constitution.md` from the provided idea.
  - Preserves `world.yaml`.
  - Fails if `world.yaml` does not exist.

- `setup world --idea "..."` (regenerate world only):
  - Regenerates `world.yaml` and `worlds_v*.json` from the provided idea.
  - Preserves `constitution.md`.
  - Fails if `constitution.md` does not exist.

**Planning Phase (structure):**

- `plan novel`:
  - Generates `novel_plan.json` from constitution + world + idea (if stored).
  - Defines arc structure, chapter count, and major beats.
  - Fails if setup is incomplete.

- `plan arc N`:
  - Generates `arcs/arc_N/arc_plan.json` from novel plan + constitution + world.
  - Defines scene beats and chapter breakdown for arc N.
  - Fails if `novel_plan.json` does not exist.

- `plan chapter M-N`:
  - Generates detailed chapter plans (`arcs/arc_X/ch_NNN_plan.json`) for chapters M through N.
  - Reads from arc plan; elaborates into scene-by-scene structure.
  - Fails if arc plan for the chapter's arc does not exist.

**Generation Phase:**

- `generate` (auto-resume):
  - Generates remaining chapters from last completed chapter.
  - Fails if planning is incomplete (missing chapter plans).
  - Skips already-written chapters.

- `generate N-M` (range):
  - Generates chapters N through M (inclusive).
  - Overwrites existing chapters in range.
  - Fails if planning is incomplete.

---

## 3. Agents

### 3.1 Setup Agents

| Agent | Responsibility | Output |
|---|---|---|
| Synopsis Generator | Produce 3-5 story concept candidates | `setup/synopses_vN.json` |
| World Generator | Produce 3 world candidates from selected synopsis | `setup/worlds_vN.json` |
| Setup Writer | Convert selected synopsis + world into core files | `constitution.md`, `world.yaml` |

### 3.2 Planning Agents

| Agent | Responsibility | Output |
|---|---|---|
| Arc Manager | Break novel into arcs; generate structure for each arc | `novel_plan.json`, `arcs/arc_N/arc_plan.json` |
| Chapter Planner | Elaborate arc beats into detailed chapter plans | `arcs/arc_N/ch_NNN_plan.json` |

### 3.3 Generation Agents

| Agent | Responsibility | Output |
|---|---|---|
| Scene Generator | Generate prose for chapter N | `chapters/ch_NNN.md` |

Notes:

- Arc Manager is minimal in Phase 1: simple linear beat expansion (no pacing curves, no tension modeling).
- No Critique or Editor agent in Phase 1.

---

## 4. File Layout

```text
/novel/
  config.yaml
  .env
  .gitignore
  constitution.md
  world.yaml
  novel_plan.json          ← generated by `plan novel`, not setup
  setup/
    synopses_v1.json
    worlds_v1.json
    chosen_synopsis.json
    chosen_world.json
  characters/
    elena.json
    dom.json
  arcs/
    arc_01/
      arc_plan.json        ← generated by `plan arc 1`
      ch_001_plan.json
      ch_002_plan.json
      ch_003_plan.json
  chapters/
    ch_001.md
    ch_002.md
    ch_003.md
  logs/
    latest.log
```

Rules:

- `.env` is never committed.
- `config.yaml` is committed and contains no secrets.
- Setup candidates are versioned for rollback and audit.

---

## 5. Configuration and Secrets

### 5.1 config.yaml (no secrets)

```yaml
providers:
  anthropic:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
  deepseek:
    type: openai
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1

agents:
  synopsis_generator: { provider: anthropic, model: claude-sonnet-4-5 }
  world_generator:    { provider: anthropic, model: claude-sonnet-4-5 }
  setup_writer:       { provider: anthropic, model: claude-sonnet-4-5 }
  chapter_planner:    { provider: anthropic, model: claude-sonnet-4-5 }
  scene_generator:    { provider: anthropic, model: claude-sonnet-4-5 }

defaults:
  max_tokens: 4096
  temperature: 1.0
  json_retry_limit: 1
```

### 5.2 .env format

```dotenv
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
```

Loading contract:

- `run` must call dotenv loading before reading env vars.
- Missing required keys should produce a single clear error naming the missing variable.
- Provider schema:
  - `type`: `anthropic` or `openai` (required).
  - `api_key_env`: environment variable name (required).
  - `base_url`: endpoint URL (required for `type: openai`, optional for `type: anthropic`).

---

## 6. State and Context

Runtime state (minimal):

```python
state = {
    "novel_plan": {},
    "chapter_plan": {},
    "characters": {},
    "world": {},
    "constitution": "",
    "chapter_index": 0,
}
```

Generation context (manual assembly):

- constitution
- novel plan
- world facts
- character snapshots
- current chapter plan

Estimated token budget (Phase 1):

- constitution: ~200
- novel plan: ~500
- world: ~300
- characters: ~400
- chapter plan: ~300
- total: ~1700

---

## 7. Setup, Planning, and Recovery

### 7.1 Setup user flow

1. User provides idea.
2. Generate synopsis candidates.
3. User selects or asks to regenerate with feedback.
4. Generate world candidates.
5. User selects or asks to regenerate with feedback.
6. Setup Writer emits `constitution.md` and `world.yaml` (no plan yet).

### 7.2 Planning user flow

1. Arc Manager reads constitution + world, generates `novel_plan.json` and arc beats.
2. Chapter Planner elaborates arc beats into chapter plans.
3. (Optional) User reviews and asks to replan individual arcs or chapters.
4. Proceed to generation when satisfied with plan.

### 7.3 Resume rules

- Every candidate generation writes a new versioned file (setup candidates versioned for audit).
- If interrupted during setup, rerun continues from latest saved artifacts.
- If interrupted during planning, rerun regenerates missing plan files.
- If interrupted during generation, rerun skips existing chapter files.

---

## 8. LLM Call Contract

Single wrapper across providers.

Input:

- `agent` name.
- `prompt` list.
- `config`.
- `expect_json` boolean.

Output:

- string or parsed JSON object.

Error policy:

- On JSON parse failure: exactly one corrective retry.
- If retry fails: raise structured error with raw response saved to logs.

Provider policy:

- Providers with `type: anthropic` use Anthropic SDK.
- Providers with `type: openai` use OpenAI-compatible SDK (OpenAI SDK with custom `base_url`).
- New OpenAI-compatible providers can be added by adding a new entry with `type: openai` and a `base_url`.

---

## 9. Debug and Observability (User-Facing)

Minimum diagnostics required in Phase 1:

- Console step logs:
  - `[init]`, `[setup]`, `[plan]`, `[generate]`, `[write]`, `[resume]`.
- Log file at `logs/latest.log`.
- On failure, print:
  - step name,
  - exception type,
  - actionable fix hint.

Recommended quick checks:

1. `config.yaml` exists and has valid provider/model names.
2. `.env` has required keys.
3. selected provider key is present.
4. output files are being written in expected directories.

---

## 10. How to Test

```bash
# 1) Create workspace
mkdir my-novel
cd my-novel
python run.py init

# 2) Fill keys
# edit .env

# 3) Check initial status
python run.py status
# Output: [✓] init | [ ] setup | [ ] novel plan | [ ] arc plan | [ ] chapter plans | [ ] ch_001 | [ ] ch_002 | [ ] ch_003

# 4) Run full setup
python run.py setup --idea "A detective in a cyberpunk city searches for her missing brother"

# 5) Check status after setup
python run.py status
# Output: [✓] init | [✓] setup | [ ] novel plan | [ ] arc plan | [ ] chapter plans | [ ] ch_001 | [ ] ch_002 | [ ] ch_003

# 6) Plan the novel
python run.py plan novel

# 7) Plan the arc
python run.py plan arc 1

# 8) Plan chapters 1-3
python run.py plan chapter 1-3

# 9) Check status before generation
python run.py status
# Output: [✓] init | [✓] setup | [✓] novel plan | [✓] arc plan | [✓] chapter plans | [ ] ch_001 | [ ] ch_002 | [ ] ch_003

# 10) Generate chapters
python run.py generate

# 11) Regenerate just constitution with new idea
python run.py setup constitution --idea "darker tone, more noir"

# 12) Replan novel with new constitution
python run.py plan novel
python run.py plan chapter 1-3

# 13) Regenerate chapters 1-2
python run.py generate 1-2

# 14) Resume from last chapter
python run.py generate
```

Manual validation:

- `status` accurately reflects progress across all phases.
- Setup options are distinct.
- Planning generates correct file structure (`novel_plan.json`, `arc_plan.json`, `ch_NNN_plan.json`).
- Granular subcommands (`setup constitution`, `setup world`) regenerate only their artifacts.
- `plan novel`, `plan arc`, `plan chapter` regenerate only their scope.
- `generate N-M` overwrites specified chapters.
- `generate` without args skips already-generated chapters.

---

## 11. Technology Stack

| Component | Choice |
|---|---|
| LLM providers | Anthropic (default), OpenAI, DeepSeek |
| Config | `config.yaml` per novel |
| Secrets | `.env` per novel + env vars |
| Storage | Local files |
| Orchestration | Plain Python functions |
| Dependencies | `anthropic`, `openai`, `pyyaml`, `python-dotenv` |

---

## 12. Success Metric

Phase 1 is complete when both are true:

1. A human rates a 3-chapter run as readable and internally consistent.
2. A user can initialize, run, crash, resume, and finish without manual code edits.

---

## 13. Deferred to Phase 2

- Critique loop.
- Editor agent.
- Character state updater.
- Rolling memory summaries.
- LangGraph.
- Structured output contracts with Pydantic.
- Arc Manager enhancements (pacing curves, tension modeling, conflict resolution).
