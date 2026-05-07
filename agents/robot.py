from .a_star import a_star
# Mitterzz


class Robot:
    def __init__(self, robot_id: int, start: tuple[int, int], goal: tuple[int, int]):
        self.robot_id = robot_id
        self.start = start
        self.goal = goal
        self.current_position = start
        self.path: list = []
        self.steps_taken: int = 0
        self.reached_goal: bool = False

    def __repr__(self):
        return (
            f"Robot(id={self.robot_id}, start={self.start}, "
            f"goal={self.goal}, pos={self.current_position})"
        )

    def plan_path(self, grid, max_time: int = 200) -> list:
        """
        Planeia o caminho usando A*.

        Args:
            grid:     lista 2D de int indexada grid[y][x], ou lista 2D de Cell
                      (Cell.FREE=0, Cell.OBSTACLE=1 — compatível com int)
            max_time: profundidade temporal máxima do A*

        Returns:
            Lista de estados [((x,y), t), ...]. Vazia se não encontrar caminho.
        """
        # Converte Cell para int caso necessário (Cell é IntEnum, já é compatível)
        path = a_star(grid, self.start, self.goal, max_time=max_time)
        self.path = path if path is not None else []
        return self.path

    def move_one_step(self) -> tuple[int, int] | None:
        """
        Avança um passo no caminho planeado.

        O primeiro elemento do path é sempre a posição atual, por isso
        removemos esse e avançamos para o seguinte.

        Returns:
            Nova posição (x, y) ou None se já chegou / sem caminho.
        """
        if not self.path or self.reached_goal:
            return None

        # Remove a posição atual (cabeça do path)
        if len(self.path) > 1:
            self.path.pop(0)

        if self.path:
            next_position, _ = self.path[0]
            self.current_position = next_position
            self.steps_taken += 1

            if self.current_position == self.goal:
                self.reached_goal = True

            return self.current_position

        return None

    def has_reached_goal(self) -> bool:
        return self.current_position == self.goal

    def reset(self):
        """Repõe o robô ao estado inicial (útil para re-simulações)."""
        self.current_position = self.start
        self.path = []
        self.steps_taken = 0
        self.reached_goal = False
