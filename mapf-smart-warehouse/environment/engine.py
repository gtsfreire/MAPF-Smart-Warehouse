from grid import Grid
from loader import load_map
class Engine:
    def __init__(self, map_path: str):
        self.grid = load_map(map_path)
    def display(self):
        for row in self.grid.cells:
            print(''.join('#' if cell == 1 else '.' for cell in row))
