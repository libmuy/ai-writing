"""Test state management."""

from src.core.state import RuntimeState


def test_state_serialization():
    """Test state to/from dict."""
    state = RuntimeState()
    state.constitution = "Test constitution"
    state.chapter_index = 5
    
    data = state.to_dict()
    
    assert data["constitution"] == "Test constitution"
    assert data["chapter_index"] == 5
    
    state2 = RuntimeState.from_dict(data)
    assert state2.constitution == "Test constitution"
    assert state2.chapter_index == 5
