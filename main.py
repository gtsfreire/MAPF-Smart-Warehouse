"""
Entry point CLI simples — útil para sanity check sem o viewer.
Uso: python main.py
"""

from __future__ import annotations

from pathlib import Path

from agents.robot import Robot
from environment.engine import Engine


MAP_PATH = Path("scenarios/warehouse-10-20-10-2-1.map")


def main() -> None:
    engine = Engine(MAP_PATH)
    print(f"Dimensões: {engine.grid.width}x{engine.grid.height}")

    obstacles = engine.obstacle_manager.count_obstacles()
    print(f"Obstáculos estáticos: {obstacles['static']}")

    start = engine.find_walkable_position()
    if start is None:
        print("Mapa sem células livres.")
        return

    # Goal: última célula livre encontrada
    goal = None
    for y in range(engine.grid.height - 1, -1, -1):
        for x in range(engine.grid.width - 1, -1, -1):
            if engine.grid.is_walkable(x, y) and (x, y) != start:
                goal = (x, y)
                break
        if goal:
            break

    if goal is None:
        print("Não foi possível encontrar um goal distinto do start.")
        return

    robot = Robot(1, start, goal)
    if not engine.add_robot(robot): 
        print("Falha ao adicionar o robô ao engine.")
