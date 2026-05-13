# Novel Generation System

AI-powered novel generation system with support for:
- Multi-phase setup (world + constitution)
- Structured planning (novel → arc → chapter)
- Interactive generation with resume support
- Multiple LLM providers (Anthropic, OpenAI, DeepSeek)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create novel workspace
mkdir my-novel
cd my-novel

# 3. Copy .env template and add keys
cp ../examples/.env.example .env
# Edit .env with your API keys

# 4. Initialize workspace
python -m src.cli.main init

# 5. Run full setup
python -m src.cli.main setup --idea "Your novel idea here"

# 6. Plan the novel
python -m src.cli.main plan novel
python -m src.cli.main plan arc 1-2
python -m src.cli.main plan chapter 1-3

# 7. Generate chapters
python -m src.cli.main generate
```

## Commands

- `init` - Initialize novel workspace
- `status` - Show progress
- `setup [--idea "..."]` - Interactive setup
- `setup constitution [--idea "..."]` - Regenerate constitution only
- `setup world [--idea "..."]` - Regenerate world only
- `plan novel` - Plan novel structure
- `plan arc N` or `plan arc N-M` - Plan arc(s)
- `plan chapter N-M` - Plan chapters
- `generate` - Generate remaining chapters (auto-resume)
- `generate N-M` - Generate specific chapters

## Directory Structure

```
/novel/
  config.yaml              (provider config)
  .env                     (secrets)
  constitution.md          (story guidelines)
  world.yaml               (world details)
  novel_plan.json          (structure)
  setup/                   (candidates)
  characters/              (character data)
  arcs/                    (arc and chapter plans)
    arc_01/
      arc_plan.json
      ch_001_plan.json
      ...
  chapters/                (generated prose)
    ch_001.md
    ch_002.md
    ...
  logs/                    (execution logs)
```

## Testing

```bash
pytest tests/
pytest tests/ --cov=src
```

## Development

See [design-phase1.md](../docs/design-phase1.md) for architecture details.

Phase 2 features: critique loop, editor agent, Pydantic strict validation, LangGraph orchestration.
