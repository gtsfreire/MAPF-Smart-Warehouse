import pytest
from pathlib import Path

from environment.grid import Grid, Cell
from environment.loader import load_map


class TestCell:
    def test_cell_values(self):
        assert Cell.FREE == 0
        assert Cell.OBSTACLE == 1


class TestGrid:
    def test_create_empty_grid(self):
        grid = Grid(10, 8)
        
        assert grid.width == 10
        assert grid.height == 8
        assert len(grid.cells) == 8
        assert len(grid.cells[0]) == 10

    def test_all_cells_start_free(self):
        grid = Grid(5, 5)
        
        for row in grid.cells:
            for cell in row:
                assert cell == Cell.FREE

    def test_in_bounds(self):
        grid = Grid(10, 10)
        
        # Dentro dos limites
        assert grid.in_bounds(0, 0) is True
        assert grid.in_bounds(9, 9) is True
        assert grid.in_bounds(5, 5) is True
        
        # Fora dos limites
        assert grid.in_bounds(-1, 0) is False
        assert grid.in_bounds(0, -1) is False
        assert grid.in_bounds(10, 0) is False
        assert grid.in_bounds(0, 10) is False

    def test_is_walkable_free_cell(self):
        grid = Grid(5, 5)
        
        assert grid.is_walkable(2, 2) is True

    def test_is_walkable_obstacle(self):
        grid = Grid(5, 5)
        grid.cells[2][2] = Cell.OBSTACLE
        
        assert grid.is_walkable(2, 2) is False

    def test_is_walkable_out_of_bounds(self):
        grid = Grid(5, 5)
        
        assert grid.is_walkable(-1, 0) is False
        assert grid.is_walkable(5, 5) is False

    def test_neighbors_center(self):
        grid = Grid(5, 5)
        
        neighbors = list(grid.neighbors(2, 2))
        
        assert len(neighbors) == 4
        assert (3, 2) in neighbors  # direita
        assert (1, 2) in neighbors  # esquerda
        assert (2, 3) in neighbors  # baixo
        assert (2, 1) in neighbors  # cima

    def test_neighbors_corner(self):
        grid = Grid(5, 5)
        
        neighbors = list(grid.neighbors(0, 0))
        
        assert len(neighbors) == 2
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_neighbors_with_obstacle(self):
        grid = Grid(5, 5)
        grid.cells[2][3] = Cell.OBSTACLE  # bloqueia (3, 2)
        
        neighbors = list(grid.neighbors(2, 2))
        
        assert len(neighbors) == 3
        assert (3, 2) not in neighbors


class TestLoader:
    @pytest.fixture
    def sample_map_file(self, tmp_path) -> Path:
        """Cria um ficheiro .map temporário para testes."""
        content = """type octile
height 5
width 5
map
.....
.@@@.
.....
.@.@.
.....
"""
        map_file = tmp_path / "test.map"
        map_file.write_text(content)
        return map_file

    def test_load_map_dimensions(self, sample_map_file):
        grid = load_map(sample_map_file)
        
        assert grid.width == 5
        assert grid.height == 5

    def test_load_map_obstacles(self, sample_map_file):
        grid = load_map(sample_map_file)
        
        # Linha 1: .@@@.
        assert grid.cells[1][0] == Cell.FREE
        assert grid.cells[1][1] == Cell.OBSTACLE
        assert grid.cells[1][2] == Cell.OBSTACLE
        assert grid.cells[1][3] == Cell.OBSTACLE
        assert grid.cells[1][4] == Cell.FREE
        
        # Linha 3: .@.@.
        assert grid.cells[3][1] == Cell.OBSTACLE
        assert grid.cells[3][3] == Cell.OBSTACLE

    def test_load_map_free_cells(self, sample_map_file):
        grid = load_map(sample_map_file)
        
        # Linha 0 toda livre
        for col in range(5):
            assert grid.cells[0][col] == Cell.FREE

    def test_load_map_walkability(self, sample_map_file):
        grid = load_map(sample_map_file)
        
        assert grid.is_walkable(0, 0) is True
        assert grid.is_walkable(1, 1) is False
        assert grid.is_walkable(2, 2) is True


class TestIntegration:
    """Testes de integração grid + loader."""

    @pytest.fixture
    def warehouse_map(self, tmp_path) -> Path:
        """Simula um mini-armazém."""
        content = """type octile
height 8
width 10
map
..........
.@@....@@.
.@@....@@.
..........
..........
.@@....@@.
.@@....@@.
..........
"""
        map_file = tmp_path / "warehouse.map"
        map_file.write_text(content)
        return map_file

    def test_pathfinding_possible(self, warehouse_map):
        """Verifica que existe caminho entre cantos."""
        grid = load_map(warehouse_map)
        
        # Canto superior esquerdo é livre
        assert grid.is_walkable(0, 0) is True
        
        # Canto inferior direito é livre
        assert grid.is_walkable(9, 7) is True
        
        # Corredor central é livre
        assert grid.is_walkable(5, 3) is True

    def test_obstacle_count(self, warehouse_map):
        grid = load_map(warehouse_map)
        
        obstacle_count = sum(
            1 for row in grid.cells 
            for cell in row 
            if cell == Cell.OBSTACLE
        )
        
        # 4 blocos de 2x2 = 16 obstáculos
        assert obstacle_count == 16