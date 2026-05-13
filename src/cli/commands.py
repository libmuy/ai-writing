"""Command handlers for CLI."""

import logging
from pathlib import Path

from src.workspace.layout import init_workspace
from src.workspace.status import check_status, format_status
from src.core.config import load_config, load_env, validate_provider_keys
from src.core.errors import ConfigError, WorkspaceError

logger = logging.getLogger(__name__)


def init_cmd():
    """Initialize novel workspace."""
    logger.info("[init] Initializing novel workspace...")
    try:
        init_workspace()
        logger.info("[init] ✓ Workspace initialized successfully")
    except Exception as e:
        logger.error(f"[init] Failed: {e}")
        raise


def status_cmd():
    """Show workspace status."""
    logger.info("[status] Checking workspace status...")
    try:
        status = check_status()
        status_str = format_status(status)
        print(status_str)
        
        # Print chapter count if available
        chapters = status.get("chapters", 0)
        if chapters > 0:
            logger.info(f"[status] {chapters} chapter(s) generated")
    except Exception as e:
        logger.error(f"[status] Failed: {e}")
        raise


def setup_cmd(mode: str, idea: str = None):
    """Setup novel world and constitution.
    
    Args:
        mode: 'full', 'constitution', or 'world'
        idea: Novel idea (required for full setup)
    """
    logger.info(f"[setup] Running setup in {mode} mode...")
    
    try:
        # Load config and env
        load_env()
        config = load_config()
        validate_provider_keys(config)
        
        if mode == "full":
            if not idea:
                raise ConfigError("--idea required for full setup")
            _setup_full(idea, config)
        elif mode == "constitution":
            if not idea:
                raise ConfigError("--idea required for constitution regeneration")
            _setup_constitution(idea, config)
        elif mode == "world":
            if not idea:
                raise ConfigError("--idea required for world regeneration")
            _setup_world(idea, config)
        else:
            raise ValueError(f"Unknown setup mode: {mode}")
        
        logger.info(f"[setup] ✓ Setup complete")
    except Exception as e:
        logger.error(f"[setup] Failed: {e}")
        raise


def plan_cmd(target: str, range_str: str = None):
    """Plan novel structure.
    
    Args:
        target: 'novel', 'arc', or 'chapter'
        range_str: Range string (e.g., '1-3')
    """
    logger.info(f"[plan] Planning {target}...")
    
    try:
        load_env()
        config = load_config()
        validate_provider_keys(config)
        
        if target == "novel":
            _plan_novel(config)
        elif target == "arc":
            if not range_str:
                raise ValueError("Arc range required (e.g., 1 or 1-3)")
            _plan_arcs(range_str, config)
        elif target == "chapter":
            if not range_str:
                raise ValueError("Chapter range required (e.g., 1-3)")
            _plan_chapters(range_str, config)
        else:
            raise ValueError(f"Unknown plan target: {target}")
        
        logger.info(f"[plan] ✓ Planning complete")
    except Exception as e:
        logger.error(f"[plan] Failed: {e}")
        raise


def generate_cmd(range_str: str = None):
    """Generate chapter(s).
    
    Args:
        range_str: Chapter range (e.g., '1-3'); auto-resume if None
    """
    logger.info(f"[generate] Starting generation...")
    
    try:
        load_env()
        config = load_config()
        validate_provider_keys(config)
        
        _generate_chapters(range_str, config)
        
        logger.info(f"[generate] ✓ Generation complete")
    except Exception as e:
        logger.error(f"[generate] Failed: {e}")
        raise


# Helper functions

def _setup_full(idea: str, config):
    """Full setup flow: synopsis → world → constitution."""
    from src.agents.setup.synopsis_generator import SynopsisGenerator
    from src.agents.setup.world_generator import WorldGenerator
    from src.agents.setup.setup_writer import SetupWriter
    from src.prompts.setup import SYNOPSIS_PROMPT, WORLD_PROMPT, CONSTITUTION_PROMPT, WORLD_YAML_PROMPT
    from src.core.file_io import write_json
    from pathlib import Path
    
    root = Path.cwd()
    
    # Step 1: Generate synopsis candidates
    logger.info("[setup] Step 1: Generate synopsis candidates")
    syn_gen = SynopsisGenerator("synopsis_generator", config.get("agents", {}).get("synopsis_generator", {}))
    synopses = syn_gen.run({"idea": idea}, SYNOPSIS_PROMPT, config)
    
    # Save candidates
    write_json(root / "setup" / "synopses_v1.json", {"candidates": synopses})
    
    # Display for user selection
    print("\n" + "="*60)
    print("SYNOPSIS CANDIDATES:")
    print("="*60)
    for idx, s in enumerate(synopses, 1):
        print(f"\n{idx}. {s.get('title', 'Untitled')}")
        print(f"   {s.get('description', 'No description')}")
    
    # Simple selection (for now, pick first)
    selected_synopsis = synopses[0]
    logger.info(f"[setup] Selected synopsis: {selected_synopsis.get('title')}")
    write_json(root / "setup" / "chosen_synopsis.json", selected_synopsis)
    
    # Step 2: Generate world candidates
    logger.info("[setup] Step 2: Generate world candidates")
    world_gen = WorldGenerator("world_generator", config.get("agents", {}).get("world_generator", {}))
    worlds = world_gen.run({"synopsis": selected_synopsis.get("description", "")}, WORLD_PROMPT, config)
    
    # Save candidates
    write_json(root / "setup" / "worlds_v1.json", {"candidates": worlds})
    
    # Display for user selection
    print("\n" + "="*60)
    print("WORLD CANDIDATES:")
    print("="*60)
    for idx, w in enumerate(worlds, 1):
        print(f"\n{idx}. {w.get('name', 'Unnamed')}")
        print(f"   Setting: {w.get('setting', 'Unknown')}")
        print(f"   Time: {w.get('time_period', 'Unknown')}")
    
    # Simple selection (for now, pick first)
    selected_world = worlds[0]
    logger.info(f"[setup] Selected world: {selected_world.get('name')}")
    write_json(root / "setup" / "chosen_world.json", selected_world)
    
    # Step 3: Generate constitution and world YAML
    logger.info("[setup] Step 3: Write constitution and world YAML")
    writer = SetupWriter("setup_writer", config.get("agents", {}).get("setup_writer", {}))
    writer.run(
        {
            "synopsis": selected_synopsis.get("description", ""),
            "world": selected_world.get("name", "") + ": " + selected_world.get("setting", ""),
            "idea": idea,
        },
        {
            "constitution": CONSTITUTION_PROMPT,
            "world_yaml": WORLD_YAML_PROMPT,
        },
        config
    )
    
    logger.info("[setup] ✓ Full setup complete")


def _setup_constitution(idea: str, config):
    """Regenerate constitution only."""
    from src.agents.setup.setup_writer import SetupWriter
    from src.prompts.setup import CONSTITUTION_PROMPT
    from src.core.file_io import read_file
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check world.yaml exists
    if not (root / "world.yaml").exists():
        raise ConfigError("world.yaml not found. Run full setup first.")
    
    world_content = read_file(root / "world.yaml")
    
    writer = SetupWriter("setup_writer", config.get("agents", {}).get("setup_writer", {}))
    writer.run(
        {
            "synopsis": idea,
            "world": world_content,
            "idea": idea,
        },
        {
            "constitution": CONSTITUTION_PROMPT,
            "world_yaml": "",
        },
        config
    )
    
    logger.info("[setup] ✓ Constitution regenerated")


def _setup_world(idea: str, config):
    """Regenerate world only."""
    from src.agents.setup.world_generator import WorldGenerator
    from src.agents.setup.setup_writer import SetupWriter
    from src.prompts.setup import WORLD_PROMPT, WORLD_YAML_PROMPT
    from src.core.file_io import read_file, write_json
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check constitution.md exists
    if not (root / "constitution.md").exists():
        raise ConfigError("constitution.md not found. Run full setup first.")
    
    # Generate new world
    world_gen = WorldGenerator("world_generator", config.get("agents", {}).get("world_generator", {}))
    worlds = world_gen.run({"synopsis": idea}, WORLD_PROMPT, config)
    
    selected_world = worlds[0]
    
    writer = SetupWriter("setup_writer", config.get("agents", {}).get("setup_writer", {}))
    writer.run(
        {
            "synopsis": "",
            "world": selected_world.get("name", "") + ": " + selected_world.get("setting", ""),
            "idea": "",
        },
        {
            "constitution": "",
            "world_yaml": WORLD_YAML_PROMPT,
        },
        config
    )
    
    logger.info("[setup] ✓ World regenerated")


def _plan_novel(config):
    """Plan novel structure."""
    from src.agents.planning.arc_manager import ArcManager
    from src.prompts.planning import NOVEL_PLAN_PROMPT
    from src.core.file_io import read_file
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check setup is complete
    if not (root / "constitution.md").exists() or not (root / "world.yaml").exists():
        raise WorkspaceError("Setup incomplete. Run 'setup' first.")
    
    constitution = read_file(root / "constitution.md")
    world = read_file(root / "world.yaml")
    
    arc_mgr = ArcManager("arc_manager", config.get("agents", {}).get("arc_manager", {}))
    arc_mgr.run(
        {
            "constitution": constitution,
            "world": world,
            "idea": "",
        },
        NOVEL_PLAN_PROMPT,
        config
    )
    
    logger.info("[plan] ✓ Novel plan generated")


def _plan_arcs(range_str: str, config):
    """Plan arc(s)."""
    from src.agents.planning.arc_manager import ArcManager
    from src.prompts.planning import ARC_PLAN_PROMPT
    from src.core.file_io import read_file, read_json
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check novel plan exists
    if not (root / "novel_plan.json").exists():
        raise WorkspaceError("novel_plan.json not found. Run 'plan novel' first.")
    
    novel_plan = read_json(root / "novel_plan.json")
    constitution = read_file(root / "constitution.md")
    world = read_file(root / "world.yaml")
    
    # Parse range
    arc_nums = _parse_range(range_str, novel_plan.get("total_arcs", 1))
    
    arc_mgr = ArcManager("arc_manager", config.get("agents", {}).get("arc_manager", {}))
    
    for arc_id in arc_nums:
        logger.info(f"[plan] Planning arc {arc_id}...")
        
        # Find arc summary
        arc_summary = None
        for arc in novel_plan.get("arc_summaries", []):
            if arc.get("arc") == arc_id:
                arc_summary = arc
                break
        
        if not arc_summary:
            logger.warning(f"[plan] No summary found for arc {arc_id}, skipping")
            continue
        
        # Create arc directory
        arc_dir = root / "arcs" / f"arc_{arc_id:02d}"
        arc_dir.mkdir(parents=True, exist_ok=True)
        
        # TODO: Implement arc planning with detailed beats
        logger.info(f"[plan] Arc {arc_id} planning not yet fully implemented")


def _plan_chapters(range_str: str, config):
    """Plan chapter(s)."""
    from src.agents.planning.chapter_planner import ChapterPlanner
    from src.prompts.planning import CHAPTER_PLAN_PROMPT
    from src.core.file_io import read_file, read_json
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check setup complete
    if not (root / "constitution.md").exists():
        raise WorkspaceError("constitution.md not found. Run 'setup' first.")
    
    # Check novel plan exists
    if not (root / "novel_plan.json").exists():
        raise WorkspaceError("novel_plan.json not found. Run 'plan novel' first.")
    
    novel_plan = read_json(root / "novel_plan.json")
    constitution = read_file(root / "constitution.md")
    
    # Parse range
    chapter_nums = _parse_range(range_str, novel_plan.get("total_chapters", 1))
    
    planner = ChapterPlanner("chapter_planner", config.get("agents", {}).get("chapter_planner", {}))
    
    for chapter_num in chapter_nums:
        logger.info(f"[plan] Planning chapter {chapter_num}...")
        
        # TODO: Find corresponding arc and load arc plan
        # For now, placeholder
        logger.info(f"[plan] Chapter {chapter_num} planning not yet fully implemented")


def _generate_chapters(range_str: str, config):
    """Generate chapter(s)."""
    from src.agents.generation.scene_generator import SceneGenerator
    from src.prompts.generation import SCENE_PROMPT
    from src.core.file_io import read_file, read_json
    from src.workspace.recovery import find_last_generated_chapter, get_total_chapters
    from pathlib import Path
    
    root = Path.cwd()
    
    # Check setup complete
    if not (root / "constitution.md").exists():
        raise WorkspaceError("constitution.md not found. Run 'setup' first.")
    
    if not (root / "novel_plan.json").exists():
        raise WorkspaceError("novel_plan.json not found. Run 'plan novel' first.")
    
    constitution = read_file(root / "constitution.md")
    world = read_file(root / "world.yaml")
    
    # Determine chapters to generate
    if range_str:
        chapter_nums = _parse_range(range_str, get_total_chapters(root))
    else:
        # Auto-resume from last generated
        last_chapter = find_last_generated_chapter(root)
        total_chapters = get_total_chapters(root)
        chapter_nums = list(range(last_chapter + 1, total_chapters + 1))
    
    if not chapter_nums:
        logger.info("[generate] No chapters to generate (all complete)")
        return
    
    generator = SceneGenerator("scene_generator", config.get("agents", {}).get("scene_generator", {}))
    
    for chapter_num in chapter_nums:
        logger.info(f"[generate] Generating chapter {chapter_num}...")
        
        # Find chapter plan
        chapter_plan_path = _find_chapter_plan(root, chapter_num)
        if not chapter_plan_path:
            logger.error(f"[generate] Chapter {chapter_num} plan not found")
            continue
        
        chapter_plan = read_json(chapter_plan_path)
        
        generator.run(
            {
                "chapter_plan": chapter_plan,
                "constitution": constitution,
                "world": world,
                "characters": {},  # TODO: Load character data
            },
            SCENE_PROMPT,
            config,
            chapter_num
        )


def _parse_range(range_str: str, max_val: int) -> list:
    """Parse range string like '1-3' or '5' into list of integers."""
    if "-" in range_str:
        parts = range_str.split("-")
        try:
            start = int(parts[0])
            end = int(parts[1])
            return list(range(start, min(end + 1, max_val + 1)))
        except (ValueError, IndexError):
            raise ValueError(f"Invalid range format: {range_str}")
    else:
        try:
            return [int(range_str)]
        except ValueError:
            raise ValueError(f"Invalid range format: {range_str}")


def _find_chapter_plan(root: Path, chapter_num: int) -> Path:
    """Find chapter plan file for a given chapter number."""
    # Search through all arc directories
    arcs_dir = root / "arcs"
    if not arcs_dir.exists():
        return None
    
    for arc_dir in sorted(arcs_dir.glob("arc_*")):
        plan_path = arc_dir / f"ch_{chapter_num:03d}_plan.json"
        if plan_path.exists():
            return plan_path
    
    return None
