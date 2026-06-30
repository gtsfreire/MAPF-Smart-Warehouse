"""
Treino do QLearningResolver em múltiplos episódios de simulação.

Este script treina apenas a camada local de resolução de conflitos. O A* continua
responsável pelo planeamento global; o agente aprende a escolher entre WAIT e
YIELD quando o Engine deteta um robô bloqueado. O REPLAN fica a cargo do
Engine como fallback determinístico de segurança.

Uso recomendado:

    python train_q_learning.py --episodes 900 --robots 10,20,30,40,45,50 \
        --obstacles 10 --ticks 1000 --seed 33 --out results/q_table_safe.json

Depois avaliar com:

    python multiple_runs.py --planner qlearning --q-table results/q_table_safe.json \
        --robots 10,20,30,40,45,50 --obstacles 10 --ticks 1000 \
        --runs 30 --initial-seed 33 --output results/qlearning_eval.csv --overwrite
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from statistics import mean
from typing import Iterable

import config.settings as config
from agents.conflict_resolution.q_agent import QLearningResolver
from environment.engine import Engine
from environment.multi_robot import create_robots
from metrics import SimulationMetrics


def _parse_int_list(value: str) -> list[int]:
    try:
        values = [int(v.strip()) for v in value.split(",") if v.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Usa uma lista do género: 30,40,45,50") from exc
    if not values:
        raise argparse.ArgumentTypeError("A lista não pode estar vazia.")
    if any(v <= 0 for v in values):
        raise argparse.ArgumentTypeError("Todos os valores devem ser positivos.")
    return values


def _episode_row(ep: int, robots_requested: int, seed: int, engine: Engine, metrics: SimulationMetrics, agent: QLearningResolver) -> dict:
    stats = engine.get_stats()
    m = metrics.to_dict()
    total = int(stats.get("robots_total", 0))
    completed = int(stats.get("robots_completed", 0))
    collisions = int(stats.get("total_collisions", 0))
    completion_success = total > 0 and completed == total
    safe_success = completion_success and collisions == 0
    a = agent.stats()
    return {
        "episode": ep,
        "robots_requested": robots_requested,
        "seed": seed,
        "robots_spawned": total,
        "robots_completed": completed,
        "completion_rate": m.get("success_rate", 0.0),
        "safe_success": safe_success,
        "ticks": stats.get("tick", 0),
        "makespan": m.get("makespan", 0),
        "collisions": collisions,
        "waits": stats.get("total_waits", 0),
        "replans": stats.get("total_replans", 0),
        "blocked_intents": stats.get("total_blocked_intents", 0),
        "epsilon": agent.epsilon,
        "q_states": a["q_states"],
        "q_decisions": a["q_decisions"],
        "q_updates": a["q_updates"],
        "q_wait_actions": a["q_wait_actions"],
        "q_yield_actions": a["q_yield_actions"],
        "q_replan_actions": a["q_replan_actions"],
    }


def train(
    map_path: Path,
    episodes: int,
    robot_counts: Iterable[int],
    dynamic_obstacles: int,
    max_ticks: int,
    seed: int,
    out_path: Path,
    alpha: float = 0.12,
    gamma: float = 0.85,
    epsilon: float = 0.20,
    epsilon_min: float = 0.01,
    epsilon_decay: float = 0.997,
    log_path: Path | None = None,
    verbose: bool = True,
) -> Path:
    """Treina e guarda uma Q-table."""
    robot_counts = list(robot_counts)
    if not robot_counts:
        raise ValueError("robot_counts não pode estar vazio.")

    previous_planner = config.PLANNER
    config.PLANNER = "qlearning"

    agent = QLearningResolver(
        alpha=alpha,
        gamma=gamma,
        epsilon=epsilon,
        epsilon_min=epsilon_min,
        epsilon_decay=epsilon_decay,
        seed=seed,
        training=True,
    )

    rng = random.Random(seed)
    rows: list[dict] = []

    try:
        for ep in range(1, episodes + 1):
            # Currículo simples: alterna entre densidades. Isto expõe o agente a
            # cenários fáceis e difíceis sem depender de uma única configuração.
            robots_requested = robot_counts[(ep - 1) % len(robot_counts)]
            ep_seed = rng.randint(0, 10**9)

            metrics = SimulationMetrics(keep_event_log=False)
            metrics.set_run_metadata(planner="qlearning", seed=ep_seed)
            engine = Engine(map_path, metrics=metrics, conflict_resolver=agent)
            engine.obstacle_manager.spawn_random_dynamic(count=dynamic_obstacles)
            robots = create_robots(engine, robots_requested, seed=ep_seed, verbose=False)

            if not robots:
                if verbose:
                    print(f"[ep {ep}] sem robôs colocados, skip")
                continue

            engine.start(num_robots=len(robots))
            for _ in range(max_ticks):
                engine.step()
                if all(r.has_reached_goal() for r in robots):
                    break
            engine.end()

            row = _episode_row(ep, robots_requested, ep_seed, engine, metrics, agent)
            rows.append(row)

            if verbose:
                window = rows[-25:]
                print(
                    f"[ep {ep:4d}/{episodes}] "
                    f"robots={robots_requested:>2} "
                    f"ε={agent.epsilon:.3f} "
                    f"completed={row['robots_completed']}/{row['robots_spawned']} "
                    f"safe={int(row['safe_success'])} "
                    f"ticks={row['ticks']} "
                    f"collisions={row['collisions']} "
                    f"waits={row['waits']} "
                    f"replans={row['replans']} "
                    f"|Q|={row['q_states']} "
                    f"decisions={row['q_decisions']} "
                    f"last25_safe={mean([1.0 if r['safe_success'] else 0.0 for r in window]):.2f}"
                )

        agent.save_json(out_path)

        if log_path is not None and rows:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        if verbose:
            print(f"\nQ-table guardada em: {out_path}")
            print(f"Estados aprendidos: {len(agent.q)}")
            print(f"Decisões observadas: {agent.decision_count}")
            print(f"Updates: {agent.update_count}")
            if log_path is not None:
                print(f"Log de treino: {log_path}")

        return out_path
    finally:
        config.PLANNER = previous_planner


def main() -> None:
    parser = argparse.ArgumentParser(description="Treino Q-learning para resolução de conflitos")
    parser.add_argument("--map", type=Path, default=Path(config.MAP_PATH))
    parser.add_argument("--episodes", type=int, default=config.TRAIN_EPISODES)
    parser.add_argument("--robots", type=_parse_int_list, default=config.TRAIN_ROBOTS)
    parser.add_argument("--obstacles", type=int, default=config.TRAIN_OBSTACLES)
    parser.add_argument("--ticks", type=int, default=config.MAX_TICKS)
    parser.add_argument("--seed", type=int, default=33)
    parser.add_argument("--out", type=Path, default=config.Q_TABLE_PATH)
    parser.add_argument("--log", type=Path, default=Path("results/qlearning_training_log.csv"))
    parser.add_argument("--alpha", type=float, default=0.12)
    parser.add_argument("--gamma", type=float, default=0.85)
    parser.add_argument("--epsilon", type=float, default=0.20)
    parser.add_argument("--epsilon-min", type=float, default=0.01)
    parser.add_argument("--epsilon-decay", type=float, default=0.997)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.episodes <= 0:
        raise SystemExit("--episodes deve ser maior que 0.")
    if args.obstacles < 0:
        raise SystemExit("--obstacles não pode ser negativo.")

    train(
        map_path=args.map,
        episodes=args.episodes,
        robot_counts=args.robots,
        dynamic_obstacles=args.obstacles,
        max_ticks=args.ticks,
        seed=args.seed,
        out_path=args.out,
        alpha=args.alpha,
        gamma=args.gamma,
        epsilon=args.epsilon,
        epsilon_min=args.epsilon_min,
        epsilon_decay=args.epsilon_decay,
        log_path=args.log,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
