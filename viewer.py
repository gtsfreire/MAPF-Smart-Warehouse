import pygame
from pathlib import Path
from environment.engine import Engine
from environment.grid import Cell

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
FREE_COLOR = (240, 240, 240)
GRID_COLOR = (180, 180, 180)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MAPF Smart Warehouse")

clock = pygame.time.Clock()
MOVE_DELAY = 600
last_move_time = pygame.time.get_ticks()

agents = [
    {"path": [(5,5), (6,5), (7,5), (8,5)], "step": 0, "colour": (0, 100, 255)},
    {"path": [(10,10), (10,11), (10,12), (10,13)], "step": 0, "colour": (255, 100, 0)},
    {"path": [(15,5), (15,6), (15,7), (15,8)], "step": 0, "colour": (0, 200, 100)},
    {"path": [(20,10), (21,10), (22,10), (23,10)], "step": 0, "colour": (200, 0, 200)}
]

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    currentTime = pygame.time.get_ticks()

    if currentTime - last_move_time > MOVE_DELAY:
        for agent in agents:
            agent["step"] = (agent["step"] + 1)%len(agent["path"])

    screen.fill(FREE_COLOR)

    for y in range(grid.height):
        for x in range(grid.width):
            rect = pygame.Rect(x * CELL_SIZE,
                               y * CELL_SIZE,
                               CELL_SIZE,
                               CELL_SIZE)

            if grid.cells[y][x] == Cell.OBSTACLE:
                pygame.draw.rect(screen, OBSTACLE_COLOR, rect)
            else:
                pygame.draw.rect(screen, FREE_COLOR, rect)

            pygame.draw.rect(screen, GRID_COLOR, rect, 1)

    for agent in agents:
        x, y = agent["path"][agent["step"]]
        rect = pygame.Rect(x * CELL_SIZE,
                           y * CELL_SIZE,
                           CELL_SIZE,
                           CELL_SIZE)
        pygame.draw.rect(screen, agent["colour"], rect)

    pygame.display.flip()

    clock.tick(20)

pygame.quit()