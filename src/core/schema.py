"""Pydantic schema definitions for Phase 1."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SynopsisCandidate(BaseModel):
    """Synopsis candidate."""
    id: int
    title: str
    description: str
    themes: List[str] = Field(default_factory=list)


class WorldCandidate(BaseModel):
    """World candidate."""
    id: int
    name: str
    setting: str
    time_period: str
    key_features: List[str] = Field(default_factory=list)


class SetupArtifacts(BaseModel):
    """Setup output artifacts."""
    constitution: str
    world: Dict[str, Any]


class ArcBeat(BaseModel):
    """Single beat in arc."""
    chapter: int
    title: str
    description: str
    key_events: List[str] = Field(default_factory=list)


class ArcPlan(BaseModel):
    """Arc plan."""
    arc_id: int
    title: str
    beats: List[ArcBeat]
    chapter_count: int


class NovelPlan(BaseModel):
    """Novel-level plan."""
    title: str
    total_chapters: int
    total_arcs: int
    arc_summaries: List[Dict[str, Any]]


class ChapterPlan(BaseModel):
    """Detailed chapter plan."""
    chapter_id: int
    arc_id: int
    title: str
    scenes: List[Dict[str, Any]]
    key_developments: List[str]
