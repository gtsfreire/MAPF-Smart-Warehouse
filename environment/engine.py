from pathlib import Path
from environment.grid import Grid, Cell
from environment.loader import load_map
from environment.obstacles import ObstacleManager
# gtsfreire


class Engine:
    """
    Ponto central do simulador.

    Responsabilidades:
      - Carregar e deter a grid
      - Gerir o ObstacleManager
      - Registar os robôs
      - Avançar a simulação tick a tick
    """

    def __init__(self, map_path: str | Path):
        self.grid: Grid = load_map(Path(map_path))
        self.obstacle_manager: ObstacleManager = ObstacleManager(self.grid)
        self.robots: list = []
        self.tick_count: int = 0

    # ------------------------------------------------------------------
    # Robots
    # ------------------------------------------------------------------

    def add_robot(self, robot) -> bool:
        """
        Regista um robô no engine.

        Valida que start e goal são células walkable (livres e sem obstáculos).
        Planeia o caminho automaticamente após registo.

        Returns:
            True se registado com sucesso, False caso contrário.
        """
        sx, sy = robot.start
        gx, gy = robot.goal

        if not self.grid.is_walkable(sx, sy):
            print(f"[Engine] Robot {robot.robot_id}: start {robot.start} não é walkable.")
            return False

        if not self.grid.is_walkable(gx, gy):
            print(f"[Engine] Robot {robot.robot_id}: goal {robot.goal} não é walkable.")
            return False

        self.robots.append(robot)
        robot.plan_path(self.grid.cells)
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
        Devolve uma grid 2D de int que combina obstáculos estáticos
        e dinâmicos — pronto a passar ao A*.

        0 = livre, 1 = bloqueado
        """
        rows = self.grid.height
        cols = self.grid.width
        combined = [[int(self.grid.cells[y][x]) for x in range(cols)] for y in range(rows)]

        for (x, y) in self.obstacle_manager.dynamic_obstacles:
            if 0 <= y < rows and 0 <= x < cols:
                combined[y][x] = 1

        return combined

    def find_walkable_position(self) -> tuple[int, int] | None:
        """Devolve a primeira célula livre encontrada na grid."""
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.is_walkable(x, y):
                    return (x, y)
        return None

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def step(self) -> dict:
        """
        Avança a simulação um tick:
          1. Move todos os robôs um passo
          2. Faz tick nos obstáculos dinâmicos
          3. Deteta colisões
          4. Devolve estado do tick

        Returns:
            dict com posições, colisões, robôs concluídos e tick atual.
        """
        self.tick_count += 1

        # Mover robôs
        for robot in self.robots:
            robot.move_one_step()

        # Tick dos obstáculos dinâmicos
        expired = self.obstacle_manager.tick()

        # Detetar colisões (dois ou mais robôs na mesma célula)
        from collections import defaultdict
        positions: dict[tuple, list] = defaultdict(list)
        for robot in self.robots:
            positions[robot.current_position].append(robot.robot_id)

        collisions = {pos: ids for pos, ids in positions.items() if len(ids) > 1}

        completed = [r for r in self.robots if r.has_reached_goal()]

        return {
            "tick": self.tick_count,
            "positions": {r.robot_id: r.current_position for r in self.robots},
            "collisions": collisions,
            "completed": [r.robot_id for r in completed],
            "expired_obstacles": expired,
        }

    # ------------------------------------------------------------------
    # Display / debug
    # ------------------------------------------------------------------

    def display(self):
        """Imprime a grid no terminal com robôs e obstáculos dinâmicos."""
        robot_positions = {r.current_position: str(r.robot_id) for r in self.robots}

        for y in range(self.grid.height):
            row_str = ""
            for x in range(self.grid.width):
                pos = (x, y)
                if pos in robot_positions:
                    row_str += robot_positions[pos]
                elif (x, y) in self.obstacle_manager.dynamic_obstacles:
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
            "obstacles": self.obstacle_manager.get_stats(),
        }
