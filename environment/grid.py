from enum import IntEnum
from pathlib import Path

class Cell(IntEnum):
    FREE = 0
    OBSTACLE = 1

class Grid:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # matriz de células, inicialmente todas livres
        self.cells: list[list[Cell]] = [
            [Cell.FREE] * width for _ in range(height)
        ]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.cells[y][x] == Cell.FREE

    def neighbors(self, x: int, y: int):
        """Vizinhos 4-conectados."""
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                yield (nx, ny)
    
    def set_obstacle(self, x: int, y: int):
        if self.in_bounds(x, y):
            self.cells[y][x] = Cell.OBSTACLE

    def load_from_file(self, filepath: Path):
        with open(filepath, 'r') as f:
            lines = f.readlines()
            self.height = len(lines)
            self.width = max(len(line.strip()) for line in lines)
            self.cells = [[Cell.FREE] * self.width for _ in range(self.height)]
            for y, line in enumerate(lines):
                for x, char in enumerate(line.strip()):
                    if char == '#':
                        self.set_obstacle(x, y)