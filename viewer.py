"""
Viewer pygame para o simulador MAPF Smart Warehouse.

Controlos:
  ESC / fechar janela -> sair
  SPACE               -> pausar / retomar
  R                   -> reset (novo cenário aleatório)
"""

from __future__ import annotations

import random
from pathlib import Path

import pygame

from agents.robot import Robot
from environment.engine import Engine
from environment.grid import Cell


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MAP_PATH = Path("scenarios/warehouse-10-20-10-2-1.map")
NUM_ROBOTS = 10
DYNAMIC_OBSTACLES = 20
MOVE_DELAY = 400       # ms entre passos

MAX_WIDTH = 1500
MAX_HEIGHT = 1000

COLOUR_OBSTACLE  = (40,  40,  40)
COLOUR_FREE      = (240, 240, 240)
COLOUR_GRID      = (180, 180, 180)
COLOUR_START     = (0,   200,  80)
COLOUR_GOAL      = (220,  50,  50)
COLOUR_DYNAMIC   = (180, 100,  20)
COLOUR_COLLISION = (255,   0,   0)
COLOUR_COMPLETED = (255, 220,   0)
COLOUR_TEXT      = (10,   10,  10)
COLOUR_HUD_BG    = (255, 255, 255)

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

def pick_random_walkable(engine: Engine, exclude: set) -> tuple[int, int] | None:
    candidates = [
        (x, y)
        for y in range(engine.grid.height)
        for x in range(engine.grid.width)
        if engine.grid.is_walkable(x, y)
        and (x, y) not in exclude
        and not engine.obstacle_manager.is_dynamic(x, y)
    ]
    return random.choice(candidates) if candidates else None


def spawn_robots(engine: Engine, count: int) -> list[Robot]:
    used: set[tuple[int, int]] = set()
    robots: list[Robot] = []

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


def build_engine() -> tuple[Engine, list[Robot]]:
    engine = Engine(MAP_PATH)
    engine.obstacle_manager.spawn_random_dynamic(count=DYNAMIC_OBSTACLES)
    robots = spawn_robots(engine, NUM_ROBOTS)
    return engine, robots


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pygame.init()

    engine, robots = build_engine()
    if not robots:
        print("Não foi possível colocar robôs no mapa.")
        pygame.quit()
        return

    grid = engine.grid
    cell_size = max(2, min(MAX_WIDTH // grid.width, MAX_HEIGHT // grid.height))

    width = grid.width * cell_size
    height = grid.height * cell_size

    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("MAPF Smart Warehouse")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16)

    last_move_time = pygame.time.get_ticks()
    paused = False
    last_state: dict = {"completed": [], "collisions": {}}

    running = True
    while running:
        # ---- Eventos ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    engine, robots = build_engine()
                    grid = engine.grid
                    last_move_time = pygame.time.get_ticks()
                    last_state = {"completed": [], "collisions": {}}

        # ---- Passo de simulação ----
        now = pygame.time.get_ticks()
        if not paused and now - last_move_time >= MOVE_DELAY:
            last_state = engine.step()
            last_move_time = now

        current_collisions = set(last_state.get("collisions", {}).keys())

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

        # Paths + start/goal + corpo
        for i, robot in enumerate(robots):
            colour = ROBOT_COLOURS[i % len(ROBOT_COLOURS)]

            for path_state in robot.path:
                (px, py), _ = path_state
                pygame.draw.rect(
                    screen, colour,
                    (px * cell_size, py * cell_size, cell_size, cell_size),
                    1,
                )

            sx, sy = robot.start
            pygame.draw.rect(
                screen, COLOUR_START,
                (sx * cell_size, sy * cell_size, cell_size, cell_size),
            )
            gx, gy = robot.goal
            pygame.draw.rect(
                screen, COLOUR_GOAL,
                (gx * cell_size, gy * cell_size, cell_size, cell_size),
            )
            rx, ry = robot.current_position
            body_colour = COLOUR_COMPLETED if robot.has_reached_goal() else colour
            pygame.draw.rect(
                screen, body_colour,
                (rx * cell_size, ry * cell_size, cell_size, cell_size),
            )

        # Colisões (overlay)
        for (cx, cy) in current_collisions:
            pygame.draw.rect(
                screen, COLOUR_COLLISION,
                (cx * cell_size, cy * cell_size, cell_size, cell_size), 3,
            )

        # HUD
        completed = len(last_state.get("completed", []))
        total = len(robots)
        replans = sum(getattr(r, "replan_count", 0) for r in robots)
        hud_lines = [
            f"Tick: {engine.tick_count}{'  [PAUSED]' if paused else ''}",
            f"Robôs concluídos: {completed}/{total}",
            f"Colisões totais: {engine.total_collisions}",
            f"Replans: {replans}",
            "SPACE: pausa  |  R: reset  |  ESC: sair",
        ]

        # fundo translúcido para o HUD
        hud_height = 20 * len(hud_lines) + 10
        hud_bg = pygame.Surface((300, hud_height))
        hud_bg.set_alpha(200)
        hud_bg.fill(COLOUR_HUD_BG)
        screen.blit(hud_bg, (5, 5))

        for j, line in enumerate(hud_lines):
            surf = font.render(line, True, COLOUR_TEXT)
            screen.blit(surf, (10, 10 + j * 20))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
