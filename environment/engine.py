"""
Engine central do simulador MAPF.

Responsabilidades:
  - Carregar e deter a grid
  - Gerir o ObstacleManager
  - Registar robôs e planear-lhes caminhos (A*)
  - Avançar a simulação tick a tick com:
      * replanning reativo (obstáculos dinâmicos / próximo passo bloqueado)
      * resolução simples de conflitos:
          - vertex collisions (dois robôs na mesma célula)
          - swap collisions  (A->B enquanto B->A)
        com prioridade determinística por robot_id (id menor ganha).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from environment.grid import Grid, Cell
from environment.loader import load_map
from environment.obstacles import ObstacleManager


class Engine:
    def __init__(self, map_path: str | Path):
        self.grid: Grid = load_map(Path(map_path))
        self.obstacle_manager: ObstacleManager = ObstacleManager(self.grid)
        self.robots: list = []
        self.tick_count: int = 0
        self.total_collisions: int = 0  # vertex collisions efetivamente detetadas

    # ------------------------------------------------------------------
    # Robots
    # ------------------------------------------------------------------
    def add_robot(self, robot) -> bool:
        """
        Regista um robô. Valida start/goal e planeia caminho com a grid combinada.
        Devolve False se start/goal forem inválidos.
        """
        sx, sy = robot.start
        gx, gy = robot.goal

        if not self.grid.is_walkable(sx, sy):
            print(f"[Engine] Robot {robot.robot_id}: start {robot.start} não é walkable.")
            return False
        if not self.grid.is_walkable(gx, gy):
            print(f"[Engine] Robot {robot.robot_id}: goal {robot.goal} não é walkable.")
            return False
        if self.obstacle_manager.is_dynamic(sx, sy):
            print(f"[Engine] Robot {robot.robot_id}: start {robot.start} ocupado por obstáculo dinâmico.")
            return False
        if self.obstacle_manager.is_dynamic(gx, gy):
            print(f"[Engine] Robot {robot.robot_id}: goal {robot.goal} ocupado por obstáculo dinâmico.")
            return False

        self.robots.append(robot)
        path = robot.plan_path(self.get_combined_grid())
        if not path:
            print(
                f"[Engine] Robot {robot.robot_id}: A* não encontrou caminho "
                f"de {robot.start} para {robot.goal}."
            )
        return True

    def remove_robot(self, robot_id: int) -> bool:
        before = len(self.robots)
        self.robots = [r for r in self.robots if r.robot_id != robot_id]
        return len(self.robots) < before

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------
    def get_combined_grid(self) -> list[list[int]]:
        """
        Grid 2D de int combinando obstáculos estáticos e dinâmicos.
        0 = livre, 1 = bloqueado.
        """
        rows = self.grid.height
        cols = self.grid.width
        combined = [
            [int(self.grid.cells[y][x]) for x in range(cols)]
            for y in range(rows)
        ]
        for (x, y) in self.obstacle_manager.dynamic_obstacles:
            if 0 <= y < rows and 0 <= x < cols:
                combined[y][x] = 1
        return combined

    def find_walkable_position(self) -> Optional[tuple[int, int]]:
        """Devolve a primeira célula livre encontrada na grid."""
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.is_walkable(x, y) and not self.obstacle_manager.is_dynamic(x, y):
                    return (x, y)
        return None

    # ------------------------------------------------------------------
    # Conflict resolution helpers
    # ------------------------------------------------------------------
    def _intended_moves(self) -> dict[int, tuple[tuple[int, int], tuple[int, int]]]:
        """
        Para cada robô ativo, devolve (current, intended_next).
        Se não há próximo passo planeado, intended_next == current (espera).
        """
        intents: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
        for r in self.robots:
            if r.has_reached_goal():
                continue
            cur = r.current_position
            nxt = r.peek_next_position()
            intents[r.robot_id] = (cur, nxt if nxt is not None else cur)
        return intents

    def _resolve_conflicts(
        self,
        intents: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    ) -> set[int]:
        """
        Resolve conflitos por prioridade (robot_id menor ganha).

        Regras:
          - Vertex collision: dois robôs querem ir para a mesma célula -> só o
            de menor id avança; os outros esperam.
          - Swap collision: A->B enquanto B->A -> ambos esperam.
          - Robô que decide esperar passa a ocupar a sua célula atual,
            o que pode forçar outros a esperar também.

        Returns:
            Conjunto de robot_ids que TÊM autorização para avançar.
        """
        # Ordem determinística por id ascendente
        ordered_ids = sorted(intents.keys())

        allowed: set[int] = set()
        # célula -> robot_id que reservou avançar para lá
        claimed_targets: dict[tuple[int, int], int] = {}
        # célula atual -> robot_id que está a libertá-la se avançar
        leaving_from: dict[tuple[int, int], int] = {}

        # Mapas auxiliares
        intended = {rid: intents[rid][1] for rid in ordered_ids}
        current = {rid: intents[rid][0] for rid in ordered_ids}

        def will_advance(rid: int) -> bool:
            return intended[rid] != current[rid]

        # Marca os que decidem esperar como "ocupantes" das suas células
        # (essas células ficam reservadas, evitando que outros entrem lá).
        waiting_cells: set[tuple[int, int]] = {
            current[rid] for rid in ordered_ids if not will_advance(rid)
        }

        for rid in ordered_ids:
            cur = current[rid]
            tgt = intended[rid]

            # Quem fica parado já está resolvido — ocupa a sua própria célula.
            if not will_advance(rid):
                claimed_targets[tgt] = rid  # tgt == cur
                continue

            # Não pode mover-se para uma célula onde outro robô decidiu ficar.
            if tgt in waiting_cells:
                claimed_targets[cur] = rid
                continue

            # Vertex collision: alguém de id menor já reservou tgt.
            if tgt in claimed_targets:
                claimed_targets[cur] = rid
                continue

            # Swap collision: existe outro robô que quer ir de tgt -> cur
            swap = False
            for other in ordered_ids:
                if other == rid:
                    continue
                if current[other] == tgt and intended[other] == cur:
                    swap = True
                    break
            if swap:
                claimed_targets[cur] = rid
                continue

            # OK, este robô avança.
            allowed.add(rid)
            claimed_targets[tgt] = rid
            leaving_from[cur] = rid

        return allowed

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------
    def step(self) -> dict:
        """
        Avança a simulação um tick.

        Sequência:
          1. Atualiza a grid combinada
          2. Replaneia robôs cujo próximo passo está bloqueado
          3. Resolve conflitos (vertex + swap)
          4. Aplica movimentos autorizados (os outros esperam)
          5. Faz tick aos obstáculos dinâmicos
          6. Deteta colisões residuais (sanity check)
        """
        self.tick_count += 1

        combined = self.get_combined_grid()
        replanned: list[int] = []

        # 1+2. Replanning reativo
        for robot in self.robots:
            if robot.has_reached_goal():
                continue

            nxt = robot.peek_next_position()
            needs_replan = False

            if nxt is None and not robot.has_reached_goal():
                # Sem próximo passo planeado mas ainda não chegou: tenta plano novo.
                needs_replan = True
            elif nxt is not None:
                nx, ny = nxt
                if combined[ny][nx] == 1:
                    needs_replan = True

            if needs_replan:
                robot.replan(combined)
                replanned.append(robot.robot_id)

        # 3. Resolver conflitos
        intents = self._intended_moves()
        allowed_ids = self._resolve_conflicts(intents)

        # 4. Aplicar movimentos
        for robot in self.robots:
            if robot.has_reached_goal():
                continue
            if robot.robot_id in allowed_ids:
                robot.move_one_step()
            else:
                robot.stay()

        # 5. Tick aos obstáculos dinâmicos
        expired = self.obstacle_manager.tick()

        # 6. Sanity check de colisões residuais
        positions: dict[tuple[int, int], list[int]] = defaultdict(list)
        for robot in self.robots:
            positions[robot.current_position].append(robot.robot_id)
        collisions = {pos: ids for pos, ids in positions.items() if len(ids) > 1}
        if collisions:
            self.total_collisions += sum(len(ids) - 1 for ids in collisions.values())

        completed = [r for r in self.robots if r.has_reached_goal()]

        return {
            "tick": self.tick_count,
            "positions": {r.robot_id: r.current_position for r in self.robots},
            "collisions": collisions,
            "completed": [r.robot_id for r in completed],
            "expired_obstacles": expired,
            "replanned": replanned,
        }

    # ------------------------------------------------------------------
    # Display / debug
    # ------------------------------------------------------------------
    def display(self) -> None:
        """Imprime a grid no terminal com robôs e obstáculos dinâmicos."""
        robot_positions = {r.current_position: str(r.robot_id) for r in self.robots}

        for y in range(self.grid.height):
            row_str = ""
            for x in range(self.grid.width):
                pos = (x, y)
                if pos in robot_positions:
                    row_str += robot_positions[pos]
                elif pos in self.obstacle_manager.dynamic_obstacles:
                    row_str += "D"
                elif self.grid.cells[y][x] == Cell.OBSTACLE:
                    row_str += "#"
                else:
                    row_str += "."
            print(row_str)
        print(f"Tick: {self.tick_count}")

    def get_stats(self) -> dict:
        return {
            "tick": self.tick_count,
            "robots_total": len(self.robots),
            "robots_completed": sum(1 for r in self.robots if r.has_reached_goal()),
            "total_collisions": self.total_collisions,
            "total_replans": sum(getattr(r, "replan_count", 0) for r in self.robots),
            "obstacles": self.obstacle_manager.get_stats(),
        }
