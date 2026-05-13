"""Custom exceptions."""


class NovelSystemError(Exception):
    """Base exception for novel system."""
    pass


class ConfigError(NovelSystemError):
    """Configuration error."""
    pass


class WorkspaceError(NovelSystemError):
    """Workspace operation error."""
    pass


class ProviderError(NovelSystemError):
    """LLM provider error."""
    pass


class PlanningError(NovelSystemError):
    """Planning error."""
    pass


class GenerationError(NovelSystemError):
    """Generation error."""
    pass
