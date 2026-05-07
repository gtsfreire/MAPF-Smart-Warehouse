import pygame
import random
from pathlib import Path
from environment.engine import Engine
from environment.grid import Cell
from agents.robot import Robot
from collections import defaultdict
# sebasgim975

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MAP_PATH = Path("scenarios/warehouse-10-20-10-2-1.map")
NUM_ROBOTS = 3
DYNAMIC_OBSTACLES = 5
MOVE_DELAY = 400       # ms entre cada passo dos robôs

MAX_WIDTH = 1000
MAX_HEIGHT = 700

COLOUR_OBSTACLE   = (40,  40,  40)
COLOUR_FREE       = (240, 240, 240)
COLOUR_GRID       = (180, 180, 180)
COLOUR_START      = (0,   200,  80)
COLOUR_GOAL       = (220,  50,  50)
COLOUR_DYNAMIC    = (180, 100,  20)
COLOUR_COLLISION  = (255,   0,   0)
COLOUR_COMPLETED  = (255, 220,   0)
COLOUR_TEXT       = (10,   10,  10)

ROBOT_COLOURS = [
    (0,   100, 255),
    (255, 100,   0),
    (0,   180, 120),
    (180,   0, 200),
    (0,   200, 220),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pick_random_walkable(engine, exclude: set) -> tuple[int, int] | None:
    """Escolhe uma célula walkable aleatória, excluindo posições já usadas."""
    candidates = [
        (x, y)
        for y in range(engine.grid.height)
        for x in range(engine.grid.width)
        if engine.grid.is_walkable(x, y) and (x, y) not in exclude
    ]
    return random.choice(candidates) if candidates else None


def spawn_robots(engine: Engine, count: int) -> list[Robot]:
    """Cria robôs com posições start/goal walkables e não sobrepostas."""
    used: set[tuple[int, int]] = set()
    robots = []

    for i in range(1, count + 1):
        start = pick_random_walkable(engine, used)
        if start is None:
            break
        used.add(start)

        goal = pick_random_walkable(engine, used)
        if goal is None:
            break
        used.add(goal)

        robot = Robot(i, start, goal)
        if engine.add_robot(robot):
            robots.append(robot)

    return robots


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pygame.init()

    engine = Engine(MAP_PATH)
    engine.obstacle_manager.spawn_random_dynamic(count=DYNAMIC_OBSTACLES)

    robots = spawn_robots(engine, NUM_ROBOTS)
    if not robots:
        print("Não foi possível colocar robôs no mapa.")
        return

    grid = engine.grid
    cell_size = min(MAX_WIDTH // grid.width, MAX_HEIGHT // grid.height)
    cell_size = max(cell_size, 2)

    width  = grid.width  * cell_size
    height = grid.height * cell_size

    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("MAPF Smart Warehouse")
    clock  = pygame.time.Clock()
    font   = pygame.font.SysFont("Arial", 16)

    last_move_time   = pygame.time.get_ticks()
    total_collisions = 0
    previous_collisions: set[tuple] = set()

    running = True
    while running:
        # ---- Eventos ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # ---- Passo de simulação ----
        now = pygame.time.get_ticks()
        if now - last_move_time >= MOVE_DELAY:
            state = engine.step()
            last_move_time = now

            current_collisions = set(state["collisions"].keys())
            new_collisions = current_collisions - previous_collisions
            total_collisions += len(new_collisions)
            previous_collisions = current_collisions
        else:
            # Apenas para o HUD
            current_collisions = previous_collisions
            state = {"completed": [r.robot_id for r in robots if r.has_reached_goal()]}

        # ---- Render ----
        screen.fill(COLOUR_FREE)

        # Grid estática
        for y in range(grid.height):
            for x in range(grid.width):
                rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
                if grid.cells[y][x] == Cell.OBSTACLE:
                    pygame.draw.rect(screen, COLOUR_OBSTACLE, rect)
                else:
                    pygame.draw.rect(screen, COLOUR_GRID, rect, 1)

        # Obstáculos dinâmicos
        for (x, y) in engine.obstacle_manager.dynamic_obstacles:
            rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, COLOUR_DYNAMIC, rect)

        # Robôs: path, start, goal, corpo
        for i, robot in enumerate(robots):
            colour = ROBOT_COLOURS[i % len(ROBOT_COLOURS)]

            # Path
            for path_state in robot.path:
                (px, py), _ = path_state
                r = pygame.Rect(px * cell_size, py * cell_size, cell_size, cell_size)
                pygame.draw.rect(screen, colour, r, 1)

            # Start
            sx, sy = robot.start
            pygame.draw.rect(screen, COLOUR_START,
                             (sx * cell_size, sy * cell_size, cell_size, cell_size))

            # Goal
            gx, gy = robot.goal
            pygame.draw.rect(screen, COLOUR_GOAL,
                             (gx * cell_size, gy * cell_size, cell_size, cell_size))

            # Corpo do robô
            rx, ry = robot.current_position
            body_colour = COLOUR_COMPLETED if robot.has_reached_goal() else colour
            pygame.draw.rect(screen, body_colour,
                             (rx * cell_size, ry * cell_size, cell_size, cell_size))

        # Colisões (overlay)
        for (cx, cy) in current_collisions:
            pygame.draw.rect(screen, COLOUR_COLLISION,
                             (cx * cell_size, cy * cell_size, cell_size, cell_size), 3)

        # HUD
        completed  = len(state["completed"])
        total      = len(robots)
        hud_lines  = [
            f"Tick: {engine.tick_count}",
            f"Robôs concluídos: {completed}/{total}",
            f"Colisões totais: {total_collisions}",
        ]
        for j, line in enumerate(hud_lines):
            surf = font.render(line, True, COLOUR_TEXT)
            screen.blit(surf, (10, 10 + j * 20))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()  
