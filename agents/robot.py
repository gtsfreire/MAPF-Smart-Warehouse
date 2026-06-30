"""
Robô MAPF com navegação configurável.

Mantém o caminho planeado como lista de estados ((x, y), t)
e avança um passo por tick de simulação.

Nota: "qlearning" não é um planner de caminho — é um resolver de conflitos.
Quando PLANNER == "qlearning", o Robot usa prioritized A* para planear
e o QAgent é injetado no Engine como conflict_resolver.
"""
from __future__ import annotations

from typing import Optional

import config.settings as config
from agents.types import State, Position, Grid2D


def _select_planner():
    """Seleciona o planner em tempo de execução.

    Isto é importante porque run_headless.py/multiple_runs.py podem alterar
    config.PLANNER temporariamente por argumento CLI. Se o planner fosse escolhido
    no import do módulo, o Robot podia continuar a usar o planner antigo.
    """
    if config.PLANNER == "astar":
        from agents.a_star import a_star as selected_planner
        return selected_planner
    if config.PLANNER in ("prioritized", "qlearning"):
        from agents.prioritized_a_star import plan as selected_planner
        return selected_planner
    raise ValueError(f"Unknown planner: {config.PLANNER}")


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

        self.consecutive_blocked_ticks: int = 0
        self.last_action: Optional[str] = None
        self.last_reward: Optional[float] = None

    def __repr__(self) -> str:
        return (
            f"Robot(id={self.robot_id}, start={self.start}, "
            f"goal={self.goal}, pos={self.current_position}, "
            f"steps={self.steps_taken}, blocked={self.consecutive_blocked_ticks})"
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
        selected_planner = _select_planner()
        path = selected_planner(
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
        self.replan_count += 1
        return self.plan_path(grid, **kwargs)

    # ------------------------------------------------------------------
    # Movimento
    # ------------------------------------------------------------------

    def peek_next_position(self) -> Optional[Position]:
        if self.reached_goal or not self.path:
            return None
        nxt = self._path_index + 1
        if nxt >= len(self.path):
            return None
        pos, _ = self.path[nxt]
        return pos

    def move_one_step(self) -> Optional[Position]:
        if self.reached_goal or not self.path:
            return None
        nxt = self._path_index + 1
        if nxt >= len(self.path):
            return None
        next_position, _ = self.path[nxt]
        self.current_position = next_position
        self._path_index = nxt
        self.steps_taken += 1
        if self.current_position == self.goal:
            self.reached_goal = True
        return self.current_position

    def stay(self) -> Position:
        return self.current_position

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def has_reached_goal(self) -> bool:
        return self.current_position == self.goal

    def has_plan(self) -> bool:
        return bool(self.path) and self._path_index < len(self.path) - 1

    def get_agent_info(self) -> dict:
        return {
            "robot_id":                  self.robot_id,
            "current_position":          self.current_position,
            "goal":                      self.goal,
            "steps_taken":               self.steps_taken,
            "replan_count":              self.replan_count,
            "consecutive_blocked_ticks": self.consecutive_blocked_ticks,
            "last_action":               self.last_action,
            "last_reward":               self.last_reward,
            "has_plan":                  self.has_plan(),
            "reached_goal":              self.reached_goal,
        }

    def reset(self) -> None:
        self.current_position = self.start
        self.path = []
        self._path_index = 0
        self.steps_taken = 0
        self.replan_count = 0
        self.reached_goal = False
        self.consecutive_blocked_ticks = 0
        self.last_action = None
        self.last_reward = None