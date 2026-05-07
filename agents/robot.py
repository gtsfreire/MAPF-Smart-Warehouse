"""
Robô MAPF com navegação A*.

Mantém o caminho planeado como lista de estados ((x, y), t)
e avança um passo por tick de simulação.
"""
# Mitterzz
from __future__ import annotations

from typing import Optional

from .a_star import a_star, State, Position, Grid2D


class Robot:
    def __init__(self, robot_id: int, start: Position, goal: Position):
        self.robot_id: int = robot_id
        self.start: Position = start
        self.goal: Position = goal
        self.current_position: Position = start

        self.path: list[State] = []
        self._path_index: int = 0

        self.steps_taken: int = 0
        self.replan_count: int = 0
        self.reached_goal: bool = False

    def __repr__(self) -> str:
        return (
            f"Robot(id={self.robot_id}, start={self.start}, "
            f"goal={self.goal}, pos={self.current_position}, "
            f"steps={self.steps_taken})"
        )

    # ------------------------------------------------------------------
    # Planeamento
    # ------------------------------------------------------------------
    def plan_path(
        self,
        grid: Grid2D,
        max_time: int = 200,
        vertex_constraints=None,
        edge_constraints=None,
    ) -> list[State]:
        """
        Planeia (ou replaneia) caminho da posição atual até ao goal.

        Returns:
            Lista de estados ((x,y), t). Vazia se não houver caminho.
        """
        path = a_star(
            grid,
            self.current_position,
            self.goal,
            max_time=max_time,
            vertex_constraints=vertex_constraints,
            edge_constraints=edge_constraints,
        )
        self.path = path if path is not None else []
        self._path_index = 0
        return self.path

    def replan(self, grid: Grid2D, **kwargs) -> list[State]:
        """Atalho: replaneia e contabiliza."""
        self.replan_count += 1
        return self.plan_path(grid, **kwargs)

    # ------------------------------------------------------------------
    # Movimento
    # ------------------------------------------------------------------
    def peek_next_position(self) -> Optional[Position]:
        """Devolve a próxima posição planeada sem avançar."""
        if self.reached_goal or not self.path:
            return None
        nxt = self._path_index + 1
        if nxt >= len(self.path):
            return None
        pos, _ = self.path[nxt]
        return pos

    def move_one_step(self) -> Optional[Position]:
        """
        Avança um passo no caminho planeado.

        Returns:
            Nova posição (x, y) ou None se já chegou / sem caminho válido.
        """
        if self.reached_goal or not self.path:
            return None

        nxt = self._path_index + 1
        if nxt >= len(self.path):
            # Fim do path; se não estamos no goal, o caller decide replanear.
            return None

        next_position, _ = self.path[nxt]
        self.current_position = next_position
        self._path_index = nxt
        self.steps_taken += 1

        if self.current_position == self.goal:
            self.reached_goal = True

        return self.current_position

    def stay(self) -> Position:
        """Mantém-se na posição atual (não consome plano)."""
        return self.current_position

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def has_reached_goal(self) -> bool:
        return self.current_position == self.goal

    def has_plan(self) -> bool:
        return bool(self.path) and self._path_index < len(self.path) - 1

    def reset(self) -> None:
        """Repõe o robô ao estado inicial (útil para re-simulações)."""
        self.current_position = self.start
        self.path = []
        self._path_index = 0
        self.steps_taken = 0
        self.replan_count = 0
        self.reached_goal = False
