import heapq
from itertools import count
# Mitterzz

def heuristic(state, goal):
    """Distância de Manhattan entre o estado atual e o objetivo."""
    (x, y), _ = state
    return abs(x - goal[0]) + abs(y - goal[1])


def get_neighbors(state):
    """Retorna vizinhos 4-conectados + espera no lugar."""
    (x, y), t = state
    moves = [(0, 1), (1, 0), (0, -1), (-1, 0), (0, 0)]
    return [((x + dx, y + dy), t + 1) for dx, dy in moves]


def is_valid(grid, state):
    """
    Verifica se o estado é válido.
    Convenção: grid[row][col] == grid[y][x]
    state = ((x, y), t)  onde x=coluna, y=linha
    """
    (x, y), t = state
    rows = len(grid)      # número de linhas  → índice y
    cols = len(grid[0])   # número de colunas → índice x
    if not (0 <= y < rows and 0 <= x < cols):
        return False
    return grid[y][x] == 0  # 0 = FREE


def reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def a_star(grid, start, goal, max_time=200):
    """
    Planeia um caminho de start até goal numa grid estática.

    Args:
        grid:     lista 2D de int (0=livre, 1=obstáculo), indexada grid[y][x]
        start:    (x, y) posição inicial
        goal:     (x, y) posição objetivo
        max_time: profundidade temporal máxima

    Returns:
        Lista de estados [((x,y), t), ...] ou None se não encontrar caminho.
    """
    _counter = count()          # desempate determinístico no heapq

    start_state = (start, 0)

    open_list = []
    heapq.heappush(open_list, (heuristic(start_state, goal), next(_counter), start_state))

    g_score = {start_state: 0}
    came_from = {}

    while open_list:
        current_f, _, current = heapq.heappop(open_list)
        current_pos, current_t = current

        if current_pos == goal:
            return reconstruct_path(came_from, current)

        if current_t >= max_time:
            continue

        for neighbor in get_neighbors(current):
            if not is_valid(grid, neighbor):
                continue

            tentative_g = g_score[current] + 1

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_list, (f_score, next(_counter), neighbor))

    return None
