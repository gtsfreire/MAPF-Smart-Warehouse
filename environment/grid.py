"""
Grid 2D para o simulador MAPF.

Convenção de coordenadas:
  - (x, y) == (coluna, linha)
  - cells[y][x]
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Iterator


class Cell(IntEnum):
    FREE = 0
    OBSTACLE = 1


class Grid:
    def __init__(self, width: int, height: int):
        self.width: int = width
        self.height: int = height
        self.cells: list[list[Cell]] = [
            [Cell.FREE] * width for _ in range(height)
        ]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.cells[y][x] == Cell.FREE

    def neighbors(self, x: int, y: int) -> Iterator[tuple[int, int]]:
        """Vizinhos 4-conectados walkables."""
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                yield (nx, ny)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def set_obstacle(self, x: int, y: int) -> None:
        if self.in_bounds(x, y):
            self.cells[y][x] = Cell.OBSTACLE

    def set_free(self, x: int, y: int) -> None:
        if self.in_bounds(x, y):
            self.cells[y][x] = Cell.FREE

    # ------------------------------------------------------------------
    # IO simples (formato '#' = obstáculo)
    # ------------------------------------------------------------------
    def load_from_file(self, filepath: Path) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.height = len(lines)
        self.width = max(len(line.rstrip("\n")) for line in lines)
        self.cells = [[Cell.FREE] * self.width for _ in range(self.height)]

        for y, line in enumerate(lines):
            for x, char in enumerate(line.rstrip("\n")):
                if char == "#":
                    self.set_obstacle(x, y)

    def __repr__(self) -> str:
        return f"Grid(width={self.width}, height={self.height})"