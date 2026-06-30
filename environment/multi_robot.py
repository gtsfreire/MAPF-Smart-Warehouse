"""Criação de robôs para cenários multi-agente."""

from __future__ import annotations

import random

from agents.robot import Robot
from environment.engine import Engine


def get_free_positions(engine: Engine) -> list[tuple[int, int]]:
    """Devolve todas as posições livres do mapa base."""
    return [
        (x, y)
        for y in range(engine.grid.height)
        for x in range(engine.grid.width)
        if engine.grid.is_walkable(x, y)
    ]


def create_robots(
    engine: Engine,
    num_robots: int,
    seed: int | None = None,
    max_attempts: int = 5000,
    end_zone_ratio: float = 0.15,
    verbose: bool = True,
) -> list[Robot]:
    """
    Cria robôs em duas extremidades opostas do armazém.

    Metade dos robôs nasce perto da extremidade esquerda e recebe objetivos na
    extremidade direita; a outra metade faz o inverso. Isto força cruzamentos
    no corredor central e gera conflitos úteis para avaliar MAPF.
    """
    rng = random.Random(seed)
    free_positions = get_free_positions(engine)

    width = engine.grid.width
    end_zone_width = max(1, int(width * end_zone_ratio))
    left_end_zone = [pos for pos in free_positions if pos[0] < end_zone_width]
    right_end_zone = [pos for pos in free_positions if pos[0] >= width - end_zone_width]

    if not left_end_zone:
        raise ValueError("Não há posições livres na extremidade esquerda do mapa.")
    if not right_end_zone:
        raise ValueError("Não há posições livres na extremidade direita do mapa.")

    left_to_right = num_robots // 2
    right_to_left = num_robots - left_to_right
    directions = (
        [("L2R", left_end_zone, right_end_zone)] * left_to_right
        + [("R2L", right_end_zone, left_end_zone)] * right_to_left
    )
    rng.shuffle(directions)

    if verbose:
        print(
            f"End zones: esquerda x < {end_zone_width}, "
            f"direita x >= {width - end_zone_width}"
        )

    robots: list[Robot] = []
    used_positions: set[tuple[int, int]] = set()
    robot_id = 1

    for direction, start_pool, goal_pool in directions:
        created = False

        for _ in range(max_attempts):
            start = rng.choice(start_pool)
            goal = rng.choice(goal_pool)

            if start == goal or start in used_positions or goal in used_positions:
                continue

            robot = Robot(robot_id, start, goal)
            if not engine.add_robot(robot):
                continue

            if not robot.path:
                engine.remove_robot(robot_id)
                continue

            robots.append(robot)
            used_positions.update((start, goal))

            if verbose:
                print(
                    f"Robot {robot_id} [{direction}]: "
                    f"{start} -> {goal} | path={len(robot.path)}"
                )

            robot_id += 1
            created = True
            break

        if not created and verbose:
            print(f"[AVISO] Não foi possível criar um robô válido na direção {direction}.")

    if len(robots) < num_robots and verbose:
        print(f"[AVISO] Só foram criados {len(robots)}/{num_robots} robôs com caminho válido.")

    return robots
