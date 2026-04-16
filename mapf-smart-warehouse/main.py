from pathlib import Path
from environment.loader import load_map

grid = load_map(Path("scenarios/warehouse-10-20-10-2-1.map"))
print(f"Dimensões: {grid.width}x{grid.height}")

obstacles = sum(1 for row in grid.cells for c in row if c == 1)
print(f"Obstáculos: {obstacles}")