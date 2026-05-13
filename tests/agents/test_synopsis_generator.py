"""Test Synopsis Generator."""

import pytest
from src.agents.setup.synopsis_generator import SynopsisGenerator


def test_synopsis_generator_init(sample_config):
    """Test synopsis generator initialization."""
    agent = SynopsisGenerator("synopsis_gen", sample_config["agents"]["synopsis_generator"])
    
    assert agent.name == "synopsis_gen"
    assert agent.config is not None
