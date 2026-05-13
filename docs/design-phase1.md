# Phase 1 Design: Linear Generation

**Goal:** Generate a readable, coherent short story end-to-end.  
**Builds on:** nothing — this is the starting point.  
**Next phase:** [design-phase2.md](design-phase2.md) — Quality Loop + Short-Term Memory

---

## 1. What Gets Built

Two stages wired together with plain Python functions. No graph, no database, no critique loop. Output goes to files you read directly.

**Stage A — Interactive Setup** (runs once, interactive):
```
setup_synopses() → [user selects] → setup_worlds() → [user selects + refines] → setup_write()
```

**Stage B — Generation** (runs after setup, non-interactive):
```
plan_novel() → plan_chapter() → generate_scenes() → commit_chapter()
```

Both stages use the same `call_llm()` wrapper. Stage A produces `constitution.md`, `world.yaml`, and `novel_plan.json` — the inputs Stage B reads.

---

## 2. Agents

### Stage A — Setup Agents

| Agent | What it does |
|---|---|
| **Synopsis Generator** | Takes the user's raw idea. Returns 3–5 story concept candidates (`setup/synopses_vN.json`). Can be called repeatedly with feedback. |
| **World Generator** | Takes the chosen synopsis. Returns 3 world-setting candidates (`setup/worlds_vN.json`). Can be called repeatedly with feedback. |
| **Setup Writer** | Takes the chosen synopsis + chosen world + any user notes. Writes `constitution.md`, `world.yaml`, and `novel_plan.json` in one LLM call. |

### Stage B — Generation Agents

| Agent | What it does |
|---|---|
| **Novel Planner** | One LLM call. Reads the seed prompt + `constitution.md`. Writes `novel_plan.json`: themes, chapter count, major turns, ending direction. |
| **Chapter Planner** | One LLM call per chapter. Reads `novel_plan.json` + character/world files. Writes `ch_NNN_plan.json`: scene beats, character focus, emotional target. |
| **Scene Generator** | One LLM call per scene. Reads chapter plan + context. Writes prose to `chapters/ch_NNN.md`. |

No Arc Manager yet — the Novel Planner owns pacing directly. No Critique Agent, no Editor Agent.

---

## 3. File Layout

```text
/novel/
  config.yaml                  ← provider + per-agent model config (written by init)
  .env                         ← API keys template (written by init; user fills values)
  .gitignore                   ← includes .env
  setup/
    synopses_v1.json         ← written by Synopsis Generator (each regeneration = new version)
    synopses_v2.json         ← written on regeneration
    worlds_v1.json           ← written by World Generator
    worlds_v2.json           ← written on regeneration
    chosen_synopsis.json     ← user's final selection
    chosen_world.json        ← user's final selection
  constitution.md            ← written by Setup Writer (from chosen synopsis + world)
  novel_plan.json            ← written by Novel Planner
  world.yaml                 ← written by Setup Writer
  characters/
    elena.json               ← hand-written: status, goals, relationships, voice notes
    dom.json
  arcs/
    arc_01/
      ch_001_plan.json       ← written by Chapter Planner
      ch_002_plan.json
  chapters/
    ch_001.md                ← written by Scene Generator
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

## 7. Interactive Setup Flow

Runs once before generation. Fully interactive — the user drives each step. All intermediate results are saved to `setup/` so the session can be resumed.

### 7.1 Flow

```
用戶輸入想法
    ↓
[Synopsis Generator] → 生成 3–5 個故事概要
    ↓
用戶：選擇 / 輸入調整意見重新生成 / 要求全部重來
    ↓
[World Generator] → 生成 3 個世界設定候選
    ↓
用戶：選擇 / 輸入調整意見重新生成 / 要求全部重來
    ↓
用戶確認
    ↓
[Setup Writer] → 寫出 constitution.md + world.yaml + novel_plan.json
```

### 7.2 Regeneration with History

Each generator carries previous results and user feedback into the next call, so regenerated options are meaningfully different:

```python
def generate_synopses(
    idea: str,
    feedback: str | None = None,
    previous: list | None = None,
) -> list[dict]:
    prompt = [{"role": "user", "content": idea}]
    if previous:
        prompt.append({"role": "assistant", "content": json.dumps(previous)})
        if feedback:
            prompt.append({"role": "user", "content": f"不滿意以上結果。調整方向：{feedback}。請重新生成。"})
        else:
            prompt.append({"role": "user", "content": "請生成風格完全不同的選項。"})
    return call_llm(prompt, expect_json=True)   # returns list of synopsis dicts
```

Same pattern applies to `generate_worlds()`.

### 7.3 State Persistence

Each generation call saves a versioned file. If the process crashes mid-setup, restarting resumes from the last saved state:

```python
def next_version(pattern: str, output_dir: str) -> tuple[int, str]:
    """Returns (version_number, filepath) for the next version of a file pattern."""
    v = 1
    while exists(f"{output_dir}/setup/{pattern}_v{v}.json"):
        v += 1
    return v, f"{output_dir}/setup/{pattern}_v{v}.json"

# Usage:
v, path = next_version("synopses", output_dir)
write_json(path, synopses)          # e.g. setup/synopses_v3.json
```

`git` tracks all versions automatically — the user can revert to a previous generation at any time.

### 7.4 Setup Writer Output

Takes the confirmed synopsis + world and writes three files in a single LLM call:

```python
def run_setup_writer(synopsis: dict, world: dict, notes: str, output_dir: str):
    result = call_llm([{
        "role": "user",
        "content": (
            f"Synopsis:\n{json.dumps(synopsis)}\n\n"
            f"World:\n{json.dumps(world)}\n\n"
            f"User notes:\n{notes}\n\n"
            "Write: (1) constitution rules as markdown, "
            "(2) world facts as YAML, "
            "(3) novel_plan as JSON."
        )
    }], expect_json=False)
    # parse sections from result and write to files
    write_text(f"{output_dir}/constitution.md", result["constitution"])
    write_yaml(f"{output_dir}/world.yaml",      result["world"])
    write_json(f"{output_dir}/novel_plan.json",  result["novel_plan"])
```

### 7.5 Data Schemas

#### setup/synopses_vN.json
```json
[
  {
    "id": 1,
    "title": "消失的頻道",
    "logline": "一個退休駭客發現女兒失蹤前留下的加密訊息，追查下去才發現她早已捲入她父親以爲自己已經遠離的世界。",
    "tone": "noir, 壓抑",
    "ending_type": "悲劇性勝利"
  },
  { "id": 2, ... },
  { "id": 3, ... }
]
```

#### setup/worlds_vN.json
```json
[
  {
    "id": 1,
    "name": "New Meridian",
    "summary": "被企業議會管治的海岸城市，上層是玻璃塔，下層是永久陰影。",
    "key_rules": ["植入物受議會頻率管制", "Sector 4 以下無執法覆蓋"],
    "tone_notes": "視覺上壓抑，科技感低調"
  }
]
```

---

## 8. Orchestration

Plain sequential Python — no graph, no retry logic, no async:

```python
def init_novel(output_dir: str):
  """Create a novel workspace with starter config files."""
  make_dirs(output_dir, [
    "setup", "characters", "arcs/arc_01", "chapters"
  ])

  # 1) Write provider + model config
  write_yaml(f"{output_dir}/config.yaml", {
    "providers": {
      "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
      "openai": {"api_key_env": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1"},
      "deepseek": {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1"},
    },
    "agents": {
      "synopsis_generator": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
      "world_generator": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
      "setup_writer": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
      "novel_planner": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
      "chapter_planner": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
      "scene_generator": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
    },
    "defaults": {"max_tokens": 4096, "temperature": 1.0},
  })

  # 2) Write env template (no secrets)
  write_text(
    f"{output_dir}/.env",
    "ANTHROPIC_API_KEY=\nOPENAI_API_KEY=\nDEEPSEEK_API_KEY=\n"
  )

  # 3) Ensure .env is not committed
  write_text(f"{output_dir}/.gitignore", ".env\n")


def main(idea: str, output_dir: str):
  load_dotenv(f"{output_dir}/.env")
  config = load_config(f"{output_dir}/config.yaml")

    # Stage A: Interactive Setup (skipped if setup already completed)
    if not exists(f"{output_dir}/novel_plan.json"):
    run_setup(idea, output_dir, config)     # interactive: loops until user confirms

    # Stage B: Generation
    state = load_state(output_dir)
  run_generation(state, output_dir, config)


def run_setup(idea: str, output_dir: str, config: dict):
    previous_synopses = None
    while True:
        feedback = None if previous_synopses is None else input("調整方向（或按 Enter 重來）: ")
        synopses = generate_synopses(idea, feedback=feedback, previous=previous_synopses, config=config)
        _, path = next_version("synopses", output_dir)
        write_json(path, synopses)
        previous_synopses = synopses

        choice = prompt_user_choice(synopses)       # print list, read index
        if choice is not None:
            write_json(f"{output_dir}/setup/chosen_synopsis.json", synopses[choice])
            break

    synopsis = load_json(f"{output_dir}/setup/chosen_synopsis.json")

    previous_worlds = None
    while True:
        feedback = None if previous_worlds is None else input("調整方向（或按 Enter 重來）: ")
        worlds = generate_worlds(synopsis, feedback=feedback, previous=previous_worlds, config=config)
        _, path = next_version("worlds", output_dir)
        write_json(path, worlds)
        previous_worlds = worlds

        choice = prompt_user_choice(worlds)
        if choice is not None:
            write_json(f"{output_dir}/setup/chosen_world.json", worlds[choice])
            break

    world = load_json(f"{output_dir}/setup/chosen_world.json")
    notes = input("其他補充想法（可留空）: ")
    run_setup_writer(synopsis, world, notes, output_dir, config)


def run_generation(state: dict, output_dir: str, config: dict):
    # Step 1: plan the novel (once)
    if not exists(f"{output_dir}/novel_plan.json"):
        novel_plan = plan_novel(state["constitution"], state["world"], config=config)
        write_json(f"{output_dir}/novel_plan.json", novel_plan)
        state["novel_plan"] = novel_plan

    # Step 2: plan + generate each chapter in sequence
    chapter_count = state["novel_plan"]["chapter_count"]
    for i in range(chapter_count):
        if exists(f"{output_dir}/chapters/ch_{i:03d}.md"):
            continue   # resume: skip already-written chapters

        chapter_plan = plan_chapter(i, state, config=config)
        write_json(f"{output_dir}/arcs/arc_01/ch_{i:03d}_plan.json", chapter_plan)
        state["chapter_plan"] = chapter_plan

        prose = generate_chapter(state, config=config)
        write_text(f"{output_dir}/chapters/ch_{i:03d}.md", prose)

        state["chapter_index"] = i + 1
        print(f"  chapter {i+1}/{chapter_count} written")
```

Crash recovery: setup saves a versioned file after each generation call. Generation skips already-written chapters. Re-running the script from any point is safe.

CLI entrypoints:

```python
def cli():
  args = parse_args()
  if args.command == "init":
    init_novel(args.output)
  elif args.command == "run":
    main(args.idea, args.output)
```

---

## 9. Model Configuration

All provider credentials and per-agent model assignments live in `config.yaml`. No API keys in code.

### 9.1 config.yaml

```yaml
# config.yaml — committed to repo (no secrets; keys come from env vars)
providers:
  anthropic:
    api_key_env: ANTHROPIC_API_KEY       # env var name, not the value
    # base_url: https://...             # optional: proxy or private endpoint
  openai:
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1

agents:
  synopsis_generator: {provider: anthropic, model: claude-sonnet-4-5}
  world_generator:    {provider: anthropic, model: claude-sonnet-4-5}
  setup_writer:       {provider: anthropic, model: claude-sonnet-4-5}
  novel_planner:      {provider: anthropic, model: claude-sonnet-4-5}
  chapter_planner:    {provider: anthropic, model: claude-sonnet-4-5}
  scene_generator:    {provider: anthropic, model: claude-sonnet-4-5}

defaults:
  max_tokens: 4096
  temperature: 1.0
```

To switch an agent to DeepSeek, change its entry:
```yaml
agents:
  scene_generator: {provider: deepseek, model: deepseek-chat}
```

### 9.2 Provider Abstraction

All providers except Anthropic are accessed via the OpenAI-compatible API (OpenAI SDK with custom `base_url`). Anthropic uses its own SDK.

```python
import os, yaml
from anthropic import Anthropic
from openai import OpenAI

def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def make_client(provider: str, config: dict):
    p = config["providers"][provider]
    key = os.environ[p["api_key_env"]]
    if provider == "anthropic":
        kwargs = {"api_key": key}
        if "base_url" in p:
            kwargs["base_url"] = p["base_url"]
        return Anthropic(**kwargs)
    else:                               # OpenAI-compatible
        return OpenAI(api_key=key, base_url=p["base_url"])
```

### 9.3 Unified call_llm()

The wrapper selects the right client and normalises the response:

```python
def call_llm(
    agent: str,
    prompt: list[dict],
    config: dict,
    expect_json: bool = True,
) -> str | dict:
    agent_cfg = config["agents"][agent]
    provider  = agent_cfg["provider"]
    model     = agent_cfg["model"]
    client    = make_client(provider, config)
    max_tok   = config["defaults"]["max_tokens"]

    if provider == "anthropic":
        # system messages must be passed as the `system` parameter
        system = " ".join(m["content"] for m in prompt if m["role"] == "system")
        messages = [m for m in prompt if m["role"] != "system"]
        raw = client.messages.create(
            model=model, max_tokens=max_tok, system=system, messages=messages
        ).content[0].text
    else:                               # OpenAI-compatible
        raw = client.chat.completions.create(
            model=model, max_tokens=max_tok, messages=prompt
        ).choices[0].message.content

    if expect_json:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            prompt.append({"role": "assistant", "content": raw})
            prompt.append({"role": "user", "content": "Your response was not valid JSON. Reply with only the JSON object."})
            return call_llm(agent, prompt, config, expect_json=True)  # one retry
    return raw
```

All agent calls pass their agent name:
```python
synopses = call_llm("synopsis_generator", prompt, config)
```

---

## 10. How to Test

```bash
# 1) Create a new novel workspace with config and env template
python run.py init --output ./novel

# 2) Fill API keys in ./novel/.env (or set env vars in shell)

# 3) First run: interactive setup, then generation
python run.py run --idea "A detective in a cyberpunk city searches for her missing brother" --output ./novel

# 4) Resume after crash (setup already done, skip to generation)
python run.py run --output ./novel
```

Check `novel/setup/synopses_v1.json` — do the candidates feel distinct? Check `novel/constitution.md` — does it capture what you intended? Open `novel/chapters/ch_001.md` — does it follow the chapter plan?

No automated scoring yet — evaluation is human reading.

---

## 11. Technology Stack

| Component | Choice |
|---|---|
| LLM providers | Anthropic (default), OpenAI, DeepSeek — configurable per agent |
| Model config | `config.yaml` — provider + model per agent, no secrets |
| Secrets | Environment variables (e.g. `ANTHROPIC_API_KEY`) |
| Storage | Files (`*.json`, `*.md`, `*.yaml`) |
| Version control | `git` |
| Orchestration | Plain Python functions |
| Dependencies | `anthropic`, `openai`, `pyyaml` |

No LangGraph, no database, no vector store, no Redis.

---

## 12. Success Metric

> Can you generate a 3-chapter story that a human finds readable and internally consistent?

Phase 1 is done when you can answer yes without manual editing of the output.

---

## 13. What Phase 2 Adds

- Critique Agent + Editor Agent (revision loop)
- Character Manager (dynamic state updates after each chapter)
- Memory Manager (rolling chapter summaries)
- LangGraph (for the critique-revision cycle graph)
- `ContractEnforcer` (Pydantic output validation)
