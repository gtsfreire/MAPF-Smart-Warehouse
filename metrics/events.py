"""Modelo de eventos de simulação. Imutável e serializável."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Tuple


class EventType(str, Enum):
    SIM_START    = "sim_start"
    SIM_END      = "sim_end"
    TICK         = "tick"
    ROBOT_SPAWN  = "robot_spawn"
    ROBOT_WAIT   = "robot_wait"
    ROBOT_REPLAN = "robot_replan"
    ROBOT_GOAL   = "robot_goal_reached"
    COLLISION    = "collision"
    # Item lifecycle
    ITEM_CREATED   = "item_created"
    ITEM_PICKED    = "item_picked"
    ITEM_DELIVERED = "item_delivered"


@dataclass(frozen=True)
class Event:
    """
    Evento atómico emitido pela Engine.

    A Engine é a única fonte de eventos e de tempo. Robots e o conflict
    resolver não devem criar eventos diretamente — devolvem factos/intents
    e a Engine traduz isso em Event com o tick correto.
    """
    type: EventType
    tick: int
    robot_id: Optional[Any] = None
    robot_ids: Optional[Tuple[Any, ...]] = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "tick": self.tick,
            "robot_id": self.robot_id,
            "robot_ids": list(self.robot_ids) if self.robot_ids else None,
            "payload": dict(self.payload),
        }