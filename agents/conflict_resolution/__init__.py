"""Infraestrutura para resolução de conflitos plugável."""

from .actions import ConflictAction
from .base import ConflictResolver
from .context import ConflictContext
from .q_agent import QLearningResolver
from .rewards import default_reward

__all__ = [
    "ConflictAction",
    "ConflictResolver",
    "ConflictContext",
    "QLearningResolver",
    "default_reward",
]
