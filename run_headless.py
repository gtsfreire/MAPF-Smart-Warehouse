"""
Runner headless do simulador MAPF.

Responsabilidades:
  - executar uma simulação isolada sem pygame;
  - devolver métricas finais ao multiple_runs.py;
  - opcionalmente escrever uma linha de CSV com cabeçalho estável.

Notas importantes para validade experimental:
  - success_rate mantém o significado clássico: percentagem de robôs que chegaram
    ao objetivo;
  - safe_success é a métrica MAPF estrita: todos chegaram E não houve colisões;
  - A* puro pode ter completion alta, mas safe_success=False se houver colisões;
  - obstáculos pedidos e obstáculos finais são colunas separadas;
  - passos médios vêm de Engine.get_stats()/Robot.steps_taken, não de estimativas
    no runner.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from environment.engine import Engine
from environment.multi_robot import create_robots
from metrics import SimulationMetrics
import config.settings as config

ALLOWED_PLANNERS = ("astar", "prioritized", "qlearning")


def _default_output_path(planner: str | None = None) -> Path:
    selected = planner or config.PLANNER
    return Path("results") / f"{selected}_single_runs.csv"


def _obstacle_stats(engine_stats: dict, engine) -> dict[str, int]:
    """Extrai estatísticas de obstáculos de forma explícita.

    Nunca usar uma coluna única chamada "obstacles" em CSV experimental: ela é
    ambígua entre obstáculos estáticos, dinâmicos pedidos, dinâmicos finais e
    total final.
    """
    obs = engine_stats.get("obstacles")
    if not isinstance(obs, dict):
        obs = {}

    static_obstacles = int(obs.get("static", 0))
    dynamic_final = int(obs.get("dynamic", len(engine.obstacle_manager.dynamic_obstacles)))
    total_final = int(obs.get("total", static_obstacles + dynamic_final))

    return {
        "static_obstacles": static_obstacles,
        "dynamic_obstacles_final": dynamic_final,
        "total_obstacles_final": total_final,
    }


def _build_csv_row(result: dict[str, Any], engine) -> dict[str, Any]:
    engine_stats = result["engine_stats"]
    metrics = result["metrics"]
    obs = _obstacle_stats(engine_stats, engine)

    robots_spawned = int(engine_stats.get("robots_total", 0))
    robots_completed = int(engine_stats.get("robots_completed", 0))
    robots_failed = max(0, robots_spawned - robots_completed)
    total_collisions = int(engine_stats.get("total_collisions", 0))

    completion_success = robots_spawned > 0 and robots_completed == robots_spawned
    collision_free = total_collisions == 0
    safe_success = completion_success and collision_free

    total_steps = int(engine_stats.get("total_steps", 0))
    completed_steps = int(engine_stats.get("completed_steps", 0))

    return {
        # Identificação da execução
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "planner": metrics.get("planner", config.PLANNER),
        "seed": metrics.get("seed"),
        "map": str(result.get("map_path", config.MAP_PATH)),
        "max_ticks": result.get("max_ticks"),
        "ticks_used": int(engine_stats.get("tick", 0)),

        # Configuração experimental
        "robots_requested": int(result.get("robots_requested", robots_spawned)),
        "robots_spawned": robots_spawned,
        "dynamic_obstacles_requested": int(result.get("dynamic_obstacles_requested", 0)),
        "dynamic_obstacles_final": obs["dynamic_obstacles_final"],
        "static_obstacles": obs["static_obstacles"],
        "total_obstacles_final": obs["total_obstacles_final"],

        # Sucesso / segurança
        "robots_completed": robots_completed,
        "robots_failed": robots_failed,
        "completion_rate": metrics.get("success_rate", 0.0),
        "completion_success": completion_success,
        "collision_free": collision_free,
        "safe_success": safe_success,
        "safe_success_rate": 1.0 if safe_success else 0.0,

        # Tempo / produtividade
        "makespan": metrics.get("makespan", 0),
        "average_completion_time": metrics.get("average_completion_time", 0.0),
        "throughput": metrics.get("throughput", 0.0),

        # Passos — métrica explicitamente prometida na ficha do projeto
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "average_steps_per_robot": engine_stats.get("average_steps_per_robot", 0.0),
        "average_steps_per_completed_robot": engine_stats.get(
            "average_steps_per_completed_robot", 0.0
        ),
        "metrics_total_steps": metrics.get("metrics_total_steps", 0),

        # Conflitos / coordenação
        "total_collisions": total_collisions,
        "total_conflicts": int(engine_stats.get("total_conflicts", 0)),
        "blocked_intents": int(engine_stats.get("total_blocked_intents", 0)),
        "actual_waits": int(engine_stats.get("total_waits", 0)),
        "total_replans": int(engine_stats.get("total_replans", 0)),
        "replan_rate": metrics.get("replan_rate", 0.0),
        "avg_blocked_ticks_per_robot": metrics.get("avg_blocked_ticks_per_robot", 0.0),
        "max_consecutive_blocked": metrics.get("max_consecutive_blocked", 0),

        # Q-learning / auditoria do agente
        "q_table_path": result.get("q_table_path", ""),
        "q_states": result.get("q_stats", {}).get("q_states", 0),
        "q_epsilon": result.get("q_stats", {}).get("q_epsilon", 0.0),
        "q_training": result.get("q_stats", {}).get("q_training", False),
        "q_decisions": result.get("q_stats", {}).get("q_decisions", 0),
        "q_updates": result.get("q_stats", {}).get("q_updates", 0),
        "q_wait_actions": result.get("q_stats", {}).get("q_wait_actions", 0),
        "q_yield_actions": result.get("q_stats", {}).get("q_yield_actions", 0),
        "q_replan_actions": result.get("q_stats", {}).get("q_replan_actions", 0),

        # Auditoria de paridade Engine/Metrics
        "metrics_collision_count": metrics.get("collision_count", 0),
        "metrics_wait_count": metrics.get("wait_count", 0),
        "metrics_replan_count": metrics.get("replan_count", 0),
    }


def save_metrics_csv(
    result: dict[str, Any],
    engine,
    output_path: str | Path | None = None,
) -> Path:
    """Guarda uma linha de métricas num CSV.

    Se o ficheiro já existir mas tiver outro cabeçalho, aborta. Isto impede a
    mistura silenciosa de campanhas antigas e novas no mesmo ficheiro.
    """
    planner = result["metrics"].get("planner", config.PLANNER)
    output = Path(output_path) if output_path is not None else _default_output_path(planner)
    output.parent.mkdir(parents=True, exist_ok=True)

    row = _build_csv_row(result, engine)
    fieldnames = list(row.keys())
    file_exists = output.exists() and output.stat().st_size > 0

    if file_exists:
        with output.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            existing_header = next(reader, None)
        if existing_header != fieldnames:
            raise RuntimeError(
                f"CSV existente com cabeçalho incompatível: {output}\n"
                "Apaga o ficheiro, usa outro --output, ou deixa multiple_runs.py "
                "criar um ficheiro novo por campanha."
            )

    with output.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    return output


def _make_conflict_resolver(
    planner: str | None = None,
    q_table_path: str | Path | None = None,
    allow_online_qlearning: bool = False,
    seed: int | None = None,
):
    """Instancia o resolver de conflitos adequado ao planner selecionado.

    Em avaliação, Q-learning deve carregar uma Q-table treinada. Treino online
    durante `multiple_runs.py` mistura treino e avaliação, por isso fica
    desativado por defeito. Usa --allow-online-qlearning apenas para debug.
    """
    selected_planner = planner or config.PLANNER
    if selected_planner != "qlearning":
        return None

    from agents.conflict_resolution.q_agent import QLearningResolver

    model_path = Path(q_table_path) if q_table_path is not None else config.Q_TABLE_PATH

    if model_path.exists():
        print(f"[QAgent] A carregar Q-table de {model_path}")
        return QLearningResolver.load_json(model_path, training=False, seed=seed)

    if allow_online_qlearning:
        print("[QAgent] Q-table não encontrada — agente em modo treino online/debug.")
        return QLearningResolver(training=True, seed=seed)

    raise FileNotFoundError(
        f"Q-table não encontrada: {model_path}. Treina primeiro com train_q_learning.py "
        "ou passa --allow-online-qlearning apenas para debug."
    )


def run(
    map_path: Path,
    num_robots: int,
    dynamic_obstacles: int,
    max_ticks: int,
    seed: int | None,
    stop_when_all_done: bool = True,
    verbose: bool = True,
    output_path: str | Path | None = None,
    save_csv: bool = True,
    planner: str | None = None,
    q_table_path: str | Path | None = None,
    allow_online_qlearning: bool = False,
) -> dict[str, Any]:
    """Executa uma simulação e devolve engine_stats, metrics e parity."""
    selected_planner = planner or config.PLANNER
    if selected_planner not in ALLOWED_PLANNERS:
        raise ValueError(
            f"Planner inválido: {selected_planner!r}. Usa um de {ALLOWED_PLANNERS}."
        )

    previous_planner = config.PLANNER
    config.PLANNER = selected_planner

    try:
        metrics = SimulationMetrics()
        metrics.set_run_metadata(planner=selected_planner, seed=seed)

        conflict_resolver = _make_conflict_resolver(
            selected_planner,
            q_table_path=q_table_path,
            allow_online_qlearning=allow_online_qlearning,
            seed=seed,
        )

        engine = Engine(map_path, metrics=metrics, conflict_resolver=conflict_resolver)
        engine.obstacle_manager.spawn_random_dynamic(count=dynamic_obstacles)

        robots = create_robots(engine, num_robots, seed=seed, verbose=verbose)

        if not robots:
            raise RuntimeError("Não foi possível colocar robôs no mapa.")

        engine.start(num_robots=len(robots))

        for _ in range(max_ticks):
            engine.step()
            if stop_when_all_done and all(r.has_reached_goal() for r in robots):
                break

        engine.end()

        engine_stats = engine.get_stats()
        m = metrics.to_dict()

        robots_total = int(engine_stats.get("robots_total", 0))
        robots_completed = int(engine_stats.get("robots_completed", 0))
        total_collisions = int(engine_stats.get("total_collisions", 0))
        completion_success = robots_total > 0 and robots_completed == robots_total
        collision_free = total_collisions == 0
        safe_success = completion_success and collision_free

        q_stats = conflict_resolver.stats() if hasattr(conflict_resolver, "stats") else {
            "q_states": 0,
            "q_epsilon": 0.0,
            "q_training": False,
            "q_decisions": 0,
            "q_updates": 0,
            "q_wait_actions": 0,
            "q_yield_actions": 0,
            "q_replan_actions": 0,
        }

        parity = {
            "collisions": (engine.total_collisions, m["collision_count"]),
            "waits": (engine_stats["total_waits"], m["wait_count"]),
            "replans": (engine_stats["total_replans"], m["replan_count"]),
            "completed": (engine_stats["robots_completed"], m["robots_completed"]),
        }

        result = {
            "map_path": str(map_path),
            "robots_requested": num_robots,
            "dynamic_obstacles_requested": dynamic_obstacles,
            "max_ticks": max_ticks,
            "engine_stats": engine_stats,
            "metrics": m,
            "parity": parity,
            "completion_success": completion_success,
            "collision_free": collision_free,
            "safe_success": safe_success,
            "q_stats": q_stats,
            "q_table_path": str(q_table_path) if q_table_path is not None else (str(config.Q_TABLE_PATH) if selected_planner == "qlearning" else ""),
        }

        if verbose:
            print("\n=== Métricas Finais ===")
            for k, v in m.items():
                print(f"  {k}: {v}")
            print(f"  completion_success: {completion_success}")
            print(f"  collision_free: {collision_free}")
            print(f"  safe_success: {safe_success}")
            if selected_planner == "qlearning":
                print(f"  q_table_path: {result['q_table_path']}")
                for qk, qv in q_stats.items():
                    print(f"  {qk}: {qv}")

            print("\n=== Estatísticas do Engine ===")
            for k in (
                "tick",
                "planner",
                "robots_total",
                "robots_completed",
                "robots_failed",
                "total_steps",
                "average_steps_per_robot",
                "average_steps_per_completed_robot",
                "total_collisions",
                "total_blocked_intents",
                "total_waits",
                "total_replans",
                "max_consecutive_blocked",
            ):
                if k in engine_stats:
                    print(f"  {k}: {engine_stats[k]}")

            print("\n=== Paridade Engine vs Metrics ===")
            for k, (engine_val, metric_val) in parity.items():
                match = "✓" if engine_val == metric_val else "✗"
                print(f"  {match} {k}: engine={engine_val}, metrics={metric_val}")

        if save_csv:
            csv_path = save_metrics_csv(result, engine, output_path=output_path)
            if verbose:
                print(f"\nCSV: {csv_path}")

        return result
    finally:
        config.PLANNER = previous_planner


def main() -> None:
    parser = argparse.ArgumentParser(description="MAPF headless runner")
    parser.add_argument("--map", type=Path, default=config.MAP_PATH)
    parser.add_argument("--planner", choices=ALLOWED_PLANNERS, default=config.PLANNER)
    parser.add_argument("--robots", type=int, default=config.NUM_ROBOTS)
    parser.add_argument("--obstacles", type=int, default=config.DYNAMIC_OBSTACLES)
    parser.add_argument("--ticks", type=int, default=config.MAX_TICKS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--q-table", type=Path, default=None, help="Q-table a usar quando --planner qlearning")
    parser.add_argument("--allow-online-qlearning", action="store_true", help="Permite Q-learning online sem Q-table; usar apenas para debug, não para avaliação final")
    parser.add_argument("--no-csv", action="store_true")
    parser.add_argument("--no-early-stop", action="store_true")
    args = parser.parse_args()

    run(
        map_path=args.map,
        num_robots=args.robots,
        dynamic_obstacles=args.obstacles,
        max_ticks=args.ticks,
        seed=args.seed,
        stop_when_all_done=not args.no_early_stop,
        output_path=args.output,
        save_csv=not args.no_csv,
        planner=args.planner,
        q_table_path=args.q_table,
        allow_online_qlearning=args.allow_online_qlearning,
    )


if __name__ == "__main__":
    main()
