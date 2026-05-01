import pygame
from pathlib import Path
from environment.engine import Engine
from environment.grid import Cell
from agents.robot import Robot
from collections import defaultdict

pygame.init()

engine = Engine(Path("scenarios/warehouse-10-20-10-2-1.map"))
grid = engine.grid

MAX_WIDTH = 1000
MAX_HEIGHT = 700

CELL_SIZE = min(MAX_WIDTH // grid.width,
                MAX_HEIGHT // grid.height)

CELL_SIZE = max(CELL_SIZE, 1)

WIDTH = grid.width * CELL_SIZE
HEIGHT = grid.height * CELL_SIZE

OBSTACLE_COLOR = (40, 40, 40)
FREE_COLOUR = (240, 240, 240)
GRID_COLOUR = (180, 180, 180)
START_COLOUR = (0, 255, 0)
GOAL_COLOUR = (255, 0, 0)
COLOURS = [
    (0, 100, 255),
    (255, 100, 0),
    (0, 200, 100),
    (200, 0, 200),
]

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MAPF Smart Warehouse")

clock = pygame.time.Clock()
MOVE_DELAY = 600
last_move_time = pygame.time.get_ticks()

robots = [
    Robot(1, (5, 5), (20, 10)),
    Robot(2, (10, 10), (30, 15)),
    Robot(3, (15, 5), (40, 20)),
]

for r in robots:
    r.plan_path(grid.cells)

font = pygame.font.SysFont("Arial", 18)
total_collisions = 0
previous_collisions = set()

running = True

while running:
# Eventos
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    currentTime = pygame.time.get_ticks()
# Movimento
    if currentTime - last_move_time > MOVE_DELAY:
        for r in robots:
            r.move_one_step()

        last_move_time = currentTime
# Limpar ecrã
    screen.fill(FREE_COLOUR)
# Desenhar grid
    for y in range(grid.height):
        for x in range(grid.width):
            rect = pygame.Rect(x * CELL_SIZE,
                               y * CELL_SIZE,
                               CELL_SIZE,
                               CELL_SIZE)

            if grid.cells[y][x] == Cell.OBSTACLE:
                pygame.draw.rect(screen, OBSTACLE_COLOR, rect)
            else:
                pygame.draw.rect(screen, FREE_COLOUR, rect)

            pygame.draw.rect(screen, GRID_COLOUR, rect, 1)
# Detetar colisões
    positions = defaultdict(list)
    for r in robots:
        positions[r.current_position].append(r)

    collisions = [pos for pos, rs in positions.items() if len(rs) > 1]
    current_collisions = set(collisions)

    new_collisions = current_collisions - previous_collisions
    total_collisions += len(new_collisions)

    previous_collisions=current_collisions

    completed = sum(1 for r in robots if r.has_reached_goal())
    total_robots = len(robots)
    elapsed_time = pygame.time.get_ticks() - last_move_time // 1000

# Desenhar robos + paths + Start/Goal
    for i, r in enumerate(robots):
        colour = COLOURS[i % len(COLOURS)]
        #Start
        sx, sy = r.start
        pygame.draw.rect(screen, START_COLOUR,
                         (sx * CELL_SIZE, sy * CELL_SIZE, CELL_SIZE, CELL_SIZE))
         #Goal
        gx, gy = r.goal
        pygame.draw.rect(screen, GOAL_COLOUR,
                         (gx*CELL_SIZE, gy*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        #Path
        for state in r.path:
            (x, y), _ = state
            rect = pygame.Rect(x * CELL_SIZE,
                               y * CELL_SIZE,
                               CELL_SIZE,
                               CELL_SIZE)

            pygame.draw.rect(screen, colour, rect, 1)

        # Robo
        x, y = r.current_position
        rect = pygame.Rect(x * CELL_SIZE,
                           y * CELL_SIZE,
                           CELL_SIZE,
                           CELL_SIZE)
        pygame.draw.rect(screen, colour, rect)

        # Goal reached
        if r.has_reached_goal():
            pygame.draw.rect(screen, (255, 255, 0),
                             (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE))
    # Desenhar colisões (por cima)
    for (x, y) in collisions:
        rect = pygame.Rect(
            x * CELL_SIZE,
            y * CELL_SIZE,
            CELL_SIZE,
            CELL_SIZE)

        pygame.draw.rect(screen, (255, 0, 0), rect, 3)

    text_lines = [
        f"Tempo: {elapsed_time}s",
        f"Robos concluidos: {completed}/{total_robots}",
        f"Colisões: {total_collisions}"
    ]
    for i, line in enumerate(text_lines):
        text_surface = font.render(line, True, (0, 0, 0))
        screen.blit(text_surface, (10, 10 + i *20))
    # Atualizar ecrã
    pygame.display.flip()



    clock.tick(20)


pygame.quit()