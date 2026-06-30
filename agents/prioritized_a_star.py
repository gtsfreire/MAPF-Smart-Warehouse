"""
Prioritized A*.

Neste projeto, a parte "prioritized" é coordenada no Engine:
- deteção de conflitos
- waits
- yield/desvio
- replanning

Este módulo mantém a mesma interface dos outros planners.
"""

from __future__ import annotations

from typing import Iterable, Optional
from agents.a_star import a_star
from agents.types import State, Position, Grid2D


def plan(
    grid: Grid2D,
    start: Position,
    goal: Position,
    max_time: int = 200,
    vertex_constraints: Optional[Iterable[State]] = None,
    edge_constraints: Optional[Iterable[tuple[Position, Position, int]]] = None,
) -> Optional[list[State]]:
    return a_star(
        grid,
        start,
        goal,
        max_time=max_time,
        vertex_constraints=vertex_constraints,
        edge_constraints=edge_constraints,
    )