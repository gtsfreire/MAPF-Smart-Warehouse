

"""
Viewer pygame para o simulador MAPF Smart Warehouse.

Controlos:
  ESC / fechar janela -> sair
  SPACE               -> pausar / retomar
  R                   -> reset (novo cenário aleatório)
"""
#sebasgim975

from __future__ import annotations

import pygame
from environment.multi_robot import create_robots
from environment.engine import Engine
from environment.grid import Cell
from metrics import SimulationMetrics
import config.settings as config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_engine():
    metrics = SimulationMetrics()
    resolver = None

    if config.PLANNER == "qlearning":
        from agents.conflict_resolution.q_agent import QLearningResolver

        if config.Q_TABLE_PATH.exists():
            resolver = QLearningResolver.load_json(config.Q_TABLE_PATH, training=False)
            print(f"[Viewer] Q-table carregada: {config.Q_TABLE_PATH}")
        else:
            print(f"[Viewer] Q-table não encontrada: {config.Q_TABLE_PATH}. A usar fallback determinístico.")

    engine = Engine(config.MAP_PATH, metrics=metrics, conflict_resolver=resolver)
    engine.obstacle_manager.spawn_random_dynamic(count=config.DYNAMIC_OBSTACLES)
    robots = create_robots(engine, config.NUM_ROBOTS, seed=None, verbose=True)

    print(f"Foram criados {len(robots)} robôs.")
    for robot in robots:
        print(f"Robot {robot.robot_id}: {robot.start} -> {robot.goal}")

    # Marca início da simulação para métricas (idempotente).
    engine.start(num_robots=len(robots))

    return engine, robots, metrics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pygame.init()

    engine, robots, metrics = build_engine()
    if not robots:
        print("Não foi possível colocar robôs no mapa.")
        pygame.quit()
        return

    grid = engine.grid
    cell_size = max(2, min(config.MAX_WIDTH // grid.width, config.MAX_HEIGHT // grid.height))

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
                    engine.end()
                    engine, robots, metrics = build_engine()
                    grid = engine.grid
                    last_move_time = pygame.time.get_ticks()
                    last_state = {"completed": [], "collisions": {}}

        # ---- Passo de simulação ----
        now = pygame.time.get_ticks()
        if not paused and now - last_move_time >= config.MOVE_DELAY:
            last_state = engine.step()
            last_move_time = now

        current_collisions = set(last_state.get("collisions", {}).keys())

        # ---- Render ----
        screen.fill(config.COLOUR_FREE)

        # Grid estática
        for y in range(grid.height):
            for x in range(grid.width):
                rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
                if grid.cells[y][x] == Cell.OBSTACLE:
                    pygame.draw.rect(screen, config.COLOUR_OBSTACLE, rect)
                else:
                    pygame.draw.rect(screen, config.COLOUR_GRID, rect, 1)

        # Obstáculos dinâmicos
        for (x, y) in engine.obstacle_manager.dynamic_obstacles:
            rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, config.COLOUR_DYNAMIC, rect)

        # Paths + start/goal + corpo
        for i, robot in enumerate(robots):
            colour = config.ROBOT_COLOURS[i % len(config.ROBOT_COLOURS)]

            for path_state in robot.path:
                (px, py), _ = path_state
                pygame.draw.rect(
                    screen, colour,
                    (px * cell_size, py * cell_size, cell_size, cell_size),
                    1,
                )

            sx, sy = robot.start
            pygame.draw.rect(
                screen, config.COLOUR_START,
                (sx * cell_size, sy * cell_size, cell_size, cell_size),
            )
            gx, gy = robot.goal
            pygame.draw.rect(
                screen, config.COLOUR_GOAL,
                (gx * cell_size, gy * cell_size, cell_size, cell_size),
            )
            rx, ry = robot.current_position
            body_colour = config.COLOUR_COMPLETED if robot.has_reached_goal() else colour
            pygame.draw.rect(
                screen, body_colour,
                (rx * cell_size, ry * cell_size, cell_size, cell_size),
            )

        # Colisões (overlay)
        for (cx, cy) in current_collisions:
            pygame.draw.rect(
                screen, config.COLOUR_COLLISION,
                (cx * cell_size, cy * cell_size, cell_size, cell_size), 3,
            )

        # HUD — duas colunas: sistema antigo (Engine) + sistema novo (Metrics)
        completed = len(last_state.get("completed", []))
        total = len(robots)
        replans = sum(getattr(r, "replan_count", 0) for r in robots)
        blocked_now = len(last_state.get("blocked_robots", []))
        total_conflicts = getattr(engine, "total_conflicts", 0)
        total_waits = getattr(engine, "total_waits", 0)

        m = metrics.to_dict()

        hud_lines = [
            f"Tick: {engine.tick_count}{' [PAUSED]' if paused else ''}",
            f"Robôs concluídos: {completed}/{total}",
            f"Colisões reais: {engine.total_collisions}  (m={m['collision_count']})",
            f"Conflitos evitados: {total_conflicts}",
            f"Robôs bloqueados agora: {blocked_now}",
            f"Esperas totais: {total_waits}  (m={m['wait_count']})",
            f"Replans: {replans}  (m={m['replan_count']})",
            f"Makespan: {m['makespan']}  | success: {m['success_rate']:.0%}",
            f"Avg completion: {m['average_completion_time']:.1f}",
            f"Algoritmo: {config.PLANNER_LABELS.get(config.PLANNER, config.PLANNER)}",
            "SPACE: pausa | R: reset | ESC: sair",
        ]

        # fundo translúcido para o HUD
        hud_height = 20 * len(hud_lines) + 10
        hud_bg = pygame.Surface((340, hud_height))
        hud_bg.set_alpha(200)
        hud_bg.fill(config.COLOUR_HUD_BG)
        screen.blit(hud_bg, (5, 5))

        for j, line in enumerate(hud_lines):
            surf = font.render(line, True, config.COLOUR_TEXT)
            screen.blit(surf, (10, 10 + j * 20))

        pygame.display.flip()
        clock.tick(30)

    # Encerra a simulação para emitir SIM_END.
    engine.end()
    pygame.quit()


if __name__ == "__main__":
    main()