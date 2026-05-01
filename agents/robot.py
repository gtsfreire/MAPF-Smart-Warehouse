import heapq
from .a_star import a_star

class Robot:
    def __init__(self, robot_id, start, goal):
        self.robot_id = robot_id
        self.start = start
        self.goal = goal
        self.current_position = start
        self.path = []

    def __repr__(self):
        return (
            f"Robot(id={self.robot_id}, start={self.start}, "
            f"goal={self.goal}, current_position={self.current_position})"
        )
    
    def plan_path(self, grid, max_time=50):
        path = a_star(grid, self.start, self.goal, max_time=max_time)
        self.path = path if path is not None else []
        return self.path
    
    def move_one_step(self): # Convem que se mova passo a passo por causa dos outros robos e osbtaculos. Assim dá para controlar melhor o robo..
    
        if not self.path:
            return None
        
        if len(self.path) > 1: # Remove o primeiro estado do caminho, que é a posição atual.
            self.path.pop(0)

        if self.path:  # Se ainda houver caminho, move para o próximo estado.
            next_state = self.path[0]
            next_position, _ = next_state
            self.current_position = next_position
            return self.current_position # Retorna a nova posição.

        return None
    
    def has_reached_goal(self): # Verifica se atingiu o objetivo.
        return self.current_position == self.goal