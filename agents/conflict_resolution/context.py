"""
Snapshot imutável do estado relevante para tomar uma decisão de conflito.

Pensado para ser fácil de serializar (útil para treino offline de Q-learning)
e para servir de "observação" ao futuro QAgent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple


Position = Tuple[int, int]


@dataclass(frozen=True)
class ConflictContext:
    """
    Informação mínima passada ao resolver quando há conflito.

    Campos:
        tick:             tick em que o conflito ocorre.
        robot_id:         id do robô a decidir.
        current_position: posição atual do robô.
        intended_position: célula para onde queria avançar.
        goal:             goal do robô.
        blocked_ticks:    quantos ticks consecutivos está bloqueado.
        others:           mapa robot_id -> (current, intended) dos restantes.
        extra:            campo livre para extensões sem partir compatibilidade.
    """
    tick: int
    robot_id: int
    current_position: Position
    intended_position: Position
    goal: Position
    blocked_ticks: int = 0
    others: Mapping[int, Tuple[Position, Position]] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)