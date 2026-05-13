"""Constants and defaults."""

# Default token budgets
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 1.0
DEFAULT_JSON_RETRY_LIMIT = 1

# File paths (relative to novel workspace root)
CONFIG_FILE = "config.yaml"
ENV_FILE = ".env"
CONSTITUTION_FILE = "constitution.md"
WORLD_FILE = "world.yaml"
NOVEL_PLAN_FILE = "novel_plan.json"

# Directory structure
SETUP_DIR = "setup"
CHARACTERS_DIR = "characters"
ARCS_DIR = "arcs"
CHAPTERS_DIR = "chapters"
LOGS_DIR = "logs"

# File versioning
SYNOPSES_TEMPLATE = "synopses_v{}.json"
WORLDS_TEMPLATE = "worlds_v{}.json"
ARC_PLAN_TEMPLATE = "arc_plan.json"
CHAPTER_PLAN_TEMPLATE = "ch_{:03d}_plan.json"
CHAPTER_FILE_TEMPLATE = "ch_{:03d}.md"

# Status checks
STATUS_INIT = "init"
STATUS_SETUP = "setup"
STATUS_NOVEL_PLAN = "novel_plan"
STATUS_ARC_PLAN = "arc_plan"
STATUS_CHAPTER_PLANS = "chapter_plans"
STATUS_CHAPTERS = "chapters"
