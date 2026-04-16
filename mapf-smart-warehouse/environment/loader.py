from pathlib import Path
from environment.grid import Cell, Grid

def load_map(path: Path) -> Grid:
    lines = path.read_text().splitlines()
    height = int(lines[1].split()[1])
    width  = int(lines[2].split()[1])
    grid = Grid(width, height)

    for row, line in enumerate(lines[4:4+height]):
        for col, ch in enumerate(line):
            if ch in ('@', 'T', 'O'):
                grid.cells[row][col] = Cell.OBSTACLE
    return grid
