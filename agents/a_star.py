import heapq

def heuristic(state, goal): # Calcula a distância de Manhattan entre o estado atual e o objetivo.
    (x, y), _ = state
    return abs(x - goal[0]) + abs(y - goal[1])

def get_neighbors(state): # Retorna vizinhos á volta.
    (x, y), t = state
    moves = [(0, 1), (1, 0), (0, -1), (-1, 0), (0, 0)]
    return [((x + dx, y + dy), t + 1) for dx, dy in moves]

def is_valid(grid, state): # Verifica se a posicao é valida.
    (x, y), t = state
    rows = len(grid) # Linhas
    cols = len(grid[0]) # Colunas
    return 0 <= x < rows and 0 <= y < cols and grid[x][y] == 0

def reconstruct_path(came_from, current):
    path = [current]

    while current in came_from:
        current = came_from[current]
        path.append(current)

    path.reverse()
    return path

def a_star(grid, start, goal, max_time =50):
    start_state = (start, 0)
    open_list = []
    heapq.heappush(open_list, (0, start))

    g_score = {start: 0} # Custo do caminho do início até o nó atual.
    came_from = {} # Para reconstruir o caminho depois de chegar ao objetivo.

    open_list = []
    heapq.heappush(open_list, (heuristic(start_state, goal), start_state))

    g_score = {start_state: 0}
    came_from = {}

    while open_list:
        current_f, current = heapq.heappop(open_list)
        current_pos, current_t = current

        if current_pos == goal:
            return reconstruct_path(came_from, current)

        if current_t >= max_time:
            continue

        for neighbor in get_neighbors(current):
            neighbor_pos = neighbor

            if not is_valid(grid, neighbor):
                continue

            tentative_g = g_score[current] + 1

            if neighbor not in g_score or tentative_g < g_score[neighbor]: # Verifica se o caminho vizinho é melhor que o caminho conhecido.
                came_from[neighbor] = current

                g_score[neighbor] = tentative_g    
                f_score = tentative_g + heuristic(neighbor, goal)
                
                heapq.heappush(open_list, (f_score, neighbor))

    return None
