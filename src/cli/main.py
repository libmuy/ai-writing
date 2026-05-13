#!/usr/bin/env python3
"""CLI entry point for novel generation system."""

import argparse
import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging import setup_logging
from src.cli.commands import init_cmd, setup_cmd, plan_cmd, generate_cmd, status_cmd


def main():
    """Main CLI dispatcher."""
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Novel generation system")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init command
    subparsers.add_parser("init", help="Initialize novel workspace")

    # status command
    subparsers.add_parser("status", help="Show workspace status")

    # setup command
    setup_parser = subparsers.add_parser("setup", help="Setup novel world and constitution")
    setup_parser.add_argument("--idea", required=False, help="Novel idea")
    setup_subparsers = setup_parser.add_subparsers(dest="setup_subcommand", help="Setup subcommand")
    setup_subparsers.add_parser("constitution", help="Regenerate constitution only")
    setup_subparsers.add_parser("world", help="Regenerate world only")

    # plan command
    plan_parser = subparsers.add_parser("plan", help="Plan novel structure")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_target", help="Plan target")
    plan_subparsers.add_parser("novel", help="Plan novel arcs")
    arc_parser = plan_subparsers.add_parser("arc", help="Plan arc(s)")
    arc_parser.add_argument("range", help="Arc range (e.g., 1 or 1-3)")
    chapter_parser = plan_subparsers.add_parser("chapter", help="Plan chapter(s)")
    chapter_parser.add_argument("range", help="Chapter range (e.g., 1-3)")

    # generate command
    generate_parser = subparsers.add_parser("generate", help="Generate chapter(s)")
    generate_parser.add_argument("range", nargs="?", help="Chapter range (e.g., 1-3); defaults to auto-resume")

    args = parser.parse_args()

    try:
        if args.command == "init":
            init_cmd()
        elif args.command == "status":
            status_cmd()
        elif args.command == "setup":
            idea = args.idea
            if args.setup_subcommand == "constitution":
                setup_cmd(mode="constitution", idea=idea)
            elif args.setup_subcommand == "world":
                setup_cmd(mode="world", idea=idea)
            else:
                setup_cmd(mode="full", idea=idea)
        elif args.command == "plan":
            if args.plan_target == "novel":
                plan_cmd(target="novel")
            elif args.plan_target == "arc":
                plan_cmd(target="arc", range_str=args.range)
            elif args.plan_target == "chapter":
                plan_cmd(target="chapter", range_str=args.range)
        elif args.command == "generate":
            range_str = args.range if args.range else None
            generate_cmd(range_str=range_str)
        else:
            parser.print_help()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
