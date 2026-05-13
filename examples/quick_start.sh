#!/bin/bash
# Quick start demo script

set -e

NOVEL_DIR="demo-novel"

# Clean up any previous demo
rm -rf "$NOVEL_DIR"

# Create workspace
mkdir "$NOVEL_DIR"
cd "$NOVEL_DIR"

# Copy config and env
cp ../examples/config.example.yaml config.yaml
cp ../examples/.env.example .env

echo "✓ Created workspace: $NOVEL_DIR"
echo "✓ Copied config and .env templates"
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run: python -m src.cli.main init"
echo "3. Run: python -m src.cli.main setup --idea 'Your novel idea'"
echo ""
