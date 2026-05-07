"""
A* com dimensão temporal para MAPF.

Estado: ((x, y), t) onde:
  - x = coluna
  - y = linha
  - t = tick lógico (timestep desde o início do plano)

A grid é uma matriz 2D indexada por grid[y][x] com:
  - 0 = livre
  - 1 = bloqueado (estático ou dinâmico)

Suporta constraints temporais opcionais para integração futura
com Prioritized Planning / CBS:
  - vertex_constraints: {((x, y), t)}   -> proibido estar em (x,y) no tick t
  - edge_constraints:   {((x1,y1),(x2,y2),t)} -> proibido transitar (x1,y1)->(x2,y2) entre t e t+1
"""
# Mitterzz
from __future__ import annotations

import heapq
from itertools import count
from typing import Iterable, Optional

State = tuple[tuple[int, int], int]
Position = tuple[int, int]
Grid2D = list[list[int]]


def _heuristic(pos: Position, goal: Position) -> int:
    """Distância de Manhattan (admissível em grid 4-conectada)."""
    return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])


def _neighbors(state: State) -> list[State]:
    """Vizinhos 4-conectados + esperar no lugar."""
    (x, y), t = state
    moves = ((0, 1), (1, 0), (0, -1), (-1, 0), (0, 0))
    return [((x + dx, y + dy), t + 1) for dx, dy in moves]


def _in_bounds(grid: Grid2D, x: int, y: int) -> bool:
    rows = len(grid)
    if rows == 0:
        return False
    cols = len(grid[0])
    return 0 <= y < rows and 0 <= x < cols


def _is_free(grid: Grid2D, x: int, y: int) -> bool:
    """Célula livre na grid combinada (0 == FREE)."""
    return _in_bounds(grid, x, y) and int(grid[y][x]) == 0


def _reconstruct(came_from: dict[State, State], current: State) -> list[State]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def a_star(
    grid: Grid2D,
    start: Position,
    goal: Position,
    max_time: int = 200,
    vertex_constraints: Optional[Iterable[State]] = None,
    edge_constraints: Optional[Iterable[tuple[Position, Position, int]]] = None,
) -> Optional[list[State]]:
    """
    Planeia um caminho de start até goal numa grid (eventualmente combinada).

    Args:
        grid:               matriz 2D (0=livre, 1=bloqueado), indexada [y][x].
        start:              (x, y) posição inicial.
        goal:               (x, y) posição objetivo.
        max_time:           profundidade temporal máxima do plano.
        vertex_constraints: estados ((x,y), t) proibidos.
        edge_constraints:   triplos ((x1,y1),(x2,y2),t) proibidos
                            (transição entre tick t e t+1).

    Returns:
        Lista de estados [((x,y), t), ...] do start até ao goal,
        ou None se não encontrar caminho.
    """
    if not _is_free(grid, *start):
        return None
    if not _in_bounds(grid, *goal):
        return None
    if start == goal:
        return [(start, 0)]

    vset: set[State] = set(vertex_constraints) if vertex_constraints else set()
    eset: set[tuple[Position, Position, int]] = (
        set(edge_constraints) if edge_constraints else set()
    )

    counter = count()
    start_state: State = (start, 0)

    open_heap: list[tuple[int, int, State]] = []
    heapq.heappush(
        open_heap,
        (_heuristic(start, goal), next(counter), start_state),
    )

    g_score: dict[State, int] = {start_state: 0}
    came_from: dict[State, State] = {}

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        current_pos, current_t = current

        if current_pos == goal:
            return _reconstruct(came_from, current)

        if current_t >= max_time:
            continue

        for neighbor in _neighbors(current):
            (nx, ny), nt = neighbor

            if not _is_free(grid, nx, ny):
                continue
            if neighbor in vset:
                continue
            if (current_pos, (nx, ny), current_t) in eset:
                continue

            tentative_g = g_score[current] + 1
            if tentative_g < g_score.get(neighbor, 10**9):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + _heuristic((nx, ny), goal)
                heapq.heappush(open_heap, (f, next(counter), neighbor))

    return None
