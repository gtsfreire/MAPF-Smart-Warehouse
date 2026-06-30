"""
Gestão de obstáculos estáticos e dinâmicos.

Convenção de coordenadas:
  - (x, y) == (coluna, linha)
  - Grid.cells[y][x]

Obstáculos estáticos: alteram Grid.cells diretamente.
Obstáculos dinâmicos: vivem no ObstacleManager e NÃO alteram o mapa base.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from environment.grid import Cell, Grid


class ObstacleType(Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass
class DynamicObstacle:
    """Obstáculo temporário (ou permanente) que não altera o mapa base."""
    x: int
    y: int
    duration: int          # ticks totais (-1 = permanente até remoção manual)
    remaining: int         # ticks restantes (-1 = permanente)
    kind: str = "generic"  # descrição: "caixa", "avaria", "congestionamento"

    @property
    def is_permanent(self) -> bool:
        return self.duration == -1 or self.remaining == -1

    @property
    def is_expired(self) -> bool:
        return (not self.is_permanent) and self.remaining <= 0


@dataclass(frozen=True)
class ObstacleEvent:
    """Evento para histórico/métricas."""
    tick: int
    x: int
    y: int
    event: str   # "added" | "removed" | "expired"
    kind: str    # "static" ou kind descritivo do dinâmico
    otype: ObstacleType


class ObstacleManager:
    def __init__(self, grid: Grid):
        self.grid: Grid = grid
        self.dynamic_obstacles: dict[tuple[int, int], DynamicObstacle] = {}
        self.current_tick: int = 0
        self.event_history: list[ObstacleEvent] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _log(self, x: int, y: int, event: str, kind: str, otype: ObstacleType) -> None:
        self.event_history.append(
            ObstacleEvent(
                tick=self.current_tick, x=x, y=y,
                event=event, kind=kind, otype=otype,
            )
        )

    def _ensure_in_bounds(self, x: int, y: int) -> bool:
        return self.grid.in_bounds(x, y)

    def _is_static_cell_obstacle(self, x: int, y: int) -> bool:
        return self.grid.cells[y][x] == Cell.OBSTACLE

    # ------------------------------------------------------------------
    # Static obstacles
    # ------------------------------------------------------------------
    def add_static(self, x: int, y: int) -> bool:
        if not self._ensure_in_bounds(x, y):
            return False
        if (x, y) in self.dynamic_obstacles:
            return False
        if self._is_static_cell_obstacle(x, y):
            return False

        self.grid.cells[y][x] = Cell.OBSTACLE
        self._log(x, y, "added", "static", ObstacleType.STATIC)
        return True

    def remove_static(self, x: int, y: int) -> bool:
        if not self._ensure_in_bounds(x, y):
            return False
        if (x, y) in self.dynamic_obstacles:
            return False
        if not self._is_static_cell_obstacle(x, y):
            return False

        self.grid.cells[y][x] = Cell.FREE
        self._log(x, y, "removed", "static", ObstacleType.STATIC)
        return True

    # ------------------------------------------------------------------
    # Dynamic obstacles
    # ------------------------------------------------------------------
    def add_dynamic(self, x: int, y: int, duration: int, kind: str = "generic") -> bool:
        """
        duration:
          -1   => permanente
          >=1  => expira após N ticks
          0 ou < -1 => inválido
        """
        if not self._ensure_in_bounds(x, y):
            return False
        if duration == 0 or duration < -1:
            return False
        if self._is_static_cell_obstacle(x, y):
            return False
        if (x, y) in self.dynamic_obstacles:
            return False

        remaining = -1 if duration == -1 else duration
        self.dynamic_obstacles[(x, y)] = DynamicObstacle(
            x=x, y=y, duration=duration, remaining=remaining, kind=kind
        )
        self._log(x, y, "added", kind, ObstacleType.DYNAMIC)
        return True

    def remove_dynamic(self, x: int, y: int) -> bool:
        obs = self.dynamic_obstacles.pop((x, y), None)
        if obs is None:
            return False
        self._log(x, y, "removed", obs.kind, ObstacleType.DYNAMIC)
        return True

    def extend_dynamic(self, x: int, y: int, extra_ticks: int) -> bool:
        if extra_ticks <= 0:
            return False
        obs = self.dynamic_obstacles.get((x, y))
        if obs is None or obs.is_permanent:
            return False
        obs.remaining += extra_ticks
        obs.duration += extra_ticks
        return True

    def get_dynamic(self, x: int, y: int) -> Optional[DynamicObstacle]:
        return self.dynamic_obstacles.get((x, y))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def is_blocked(self, x: int, y: int) -> bool:
        """Bloqueado por: fora da grid, estático, ou dinâmico ativo."""
        if not self._ensure_in_bounds(x, y):
            return True
        if self._is_static_cell_obstacle(x, y):
            return True
        return (x, y) in self.dynamic_obstacles

    def is_static(self, x: int, y: int) -> bool:
        if not self._ensure_in_bounds(x, y):
            return False
        return self._is_static_cell_obstacle(x, y) and (x, y) not in self.dynamic_obstacles

    def is_dynamic(self, x: int, y: int) -> bool:
        return (x, y) in self.dynamic_obstacles

    def get_all_obstacles(self) -> list[tuple[int, int, ObstacleType]]:
        out: list[tuple[int, int, ObstacleType]] = []
        for y, row in enumerate(self.grid.cells):
            for x, cell in enumerate(row):
                if cell == Cell.OBSTACLE:
                    out.append((x, y, ObstacleType.STATIC))
        for (x, y) in self.dynamic_obstacles.keys():
            out.append((x, y, ObstacleType.DYNAMIC))
        return out

    def count_obstacles(self) -> dict[str, int]:
        static_count = sum(
            1 for row in self.grid.cells for c in row if c == Cell.OBSTACLE
        )
        dynamic_count = len(self.dynamic_obstacles)
        return {
            "static": static_count,
            "dynamic": dynamic_count,
            "total": static_count + dynamic_count,
        }

    # ------------------------------------------------------------------
    # Simulation time
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        counts = self.count_obstacles()
        permanents = sum(1 for o in self.dynamic_obstacles.values() if o.is_permanent)
        temporaries = len(self.dynamic_obstacles) - permanents
        durations = [o.duration for o in self.dynamic_obstacles.values() if not o.is_permanent]
        avg_duration = (sum(durations) / len(durations)) if durations else 0.0
        return {
            **counts,
            "dynamic_permanent": permanents,
            "dynamic_temporary": temporaries,
            "avg_dynamic_duration": avg_duration,
            "total_events": len(self.event_history),
            "current_tick": self.current_tick,
        }

    def tick(self) -> list[tuple[int, int]]:
        """Decrementa temporários e remove os expirados. Devolve posições expiradas."""
        self.current_tick += 1
        expired: list[tuple[int, int]] = []

        for pos, obs in list(self.dynamic_obstacles.items()):
            if obs.is_permanent:
                continue
            obs.remaining -= 1
            if obs.is_expired:
                self.dynamic_obstacles.pop(pos, None)
                self._log(obs.x, obs.y, "expired", obs.kind, ObstacleType.DYNAMIC)
                expired.append(pos)

        return expired

    def reset_dynamic(self) -> None:
        self.dynamic_obstacles.clear()
        self.current_tick = 0
        self.event_history.clear()

    # ------------------------------------------------------------------
    # Random generation
    # ------------------------------------------------------------------
    def spawn_random_dynamic(
        self,
        count: int = 1,
        duration_range: tuple[int, int] = (5, 15),
        kind: str = "random",
        avoid_positions: Optional[set[tuple[int, int]]] = None,
    ) -> list[tuple[int, int]]:
        """Spawna obstáculos dinâmicos em células livres (não estáticas)."""
        if avoid_positions is None:
            avoid_positions = set()

        lo, hi = duration_range
        if lo <= 0 or hi <= 0 or lo > hi:
            raise ValueError(f"duration_range inválido: {duration_range}")

        free_cells: list[tuple[int, int]] = []
        for y, row in enumerate(self.grid.cells):
            for x, cell in enumerate(row):
                if cell != Cell.FREE:
                    continue
                if (x, y) in avoid_positions:
                    continue
                if (x, y) in self.dynamic_obstacles:
                    continue
                free_cells.append((x, y))

        if not free_cells or count <= 0:
            return []

        count = min(count, len(free_cells))
        chosen = random.sample(free_cells, count)

        created: list[tuple[int, int]] = []
        for x, y in chosen:
            duration = random.randint(lo, hi)
            if self.add_dynamic(x, y, duration=duration, kind=kind):
                created.append((x, y))

        return created
