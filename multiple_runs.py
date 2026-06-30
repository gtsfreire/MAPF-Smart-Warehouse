"""Campanhas experimentais repetidas para o simulador MAPF.

Este ficheiro deve ser usado para gerar baselines/avaliações oficiais.
Ao contrário das versões antigas, os mesmos seeds são reutilizados para cada
configuração de número de robôs. Assim, a comparação entre 10/20/30/... robôs
não fica contaminada por conjuntos de seeds diferentes.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from statistics import mean

from run_headless import ALLOWED_PLANNERS, run
import config.settings as config


def _parse_int_list(value: str) -> list[int]:
    try:
        values = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Lista inválida. Usa, por exemplo: 10,20,30,40,45,50"
        ) from exc
    if not values:
        raise argparse.ArgumentTypeError("A lista de robôs não pode estar vazia.")
    if any(v <= 0 for v in values):
        raise argparse.ArgumentTypeError("Todos os números de robôs devem ser positivos.")
    return values


def _default_robot_counts() -> str:
    return ",".join(str(v) for v in config.ROBOT_COUNTS)


def _campaign_output_path(planner: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"{planner}_metrics_{stamp}.csv"


def _planner_label(planner: str) -> str:
    return {
        "astar": "A* simples / baseline ingênuo sem coordenação segura",
        "prioritized": "Prioritized A* / baseline determinístico seguro",
        "qlearning": "Prioritized A* + Q-Learning",
    }.get(planner, planner)


def main() -> None:
    parser = argparse.ArgumentParser(description="MAPF repeated experiment runner")
    parser.add_argument("--map", type=Path, default=config.MAP_PATH)
    parser.add_argument("--planner", choices=ALLOWED_PLANNERS, default=config.PLANNER)
    parser.add_argument("--robots", type=_parse_int_list, default=_parse_int_list(_default_robot_counts()))
    parser.add_argument("--obstacles", type=int, default=config.DYNAMIC_OBSTACLES)
    parser.add_argument("--ticks", type=int, default=config.MAX_TICKS)
    parser.add_argument("--runs", type=int, default=config.RUNS_PER_SEED)
    parser.add_argument("--initial-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--q-table", type=Path, default=None, help="Q-table a usar quando --planner qlearning")
    parser.add_argument("--allow-online-qlearning", action="store_true", help="Permite Q-learning online sem Q-table; usar apenas para debug")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-early-stop", action="store_true")
    args = parser.parse_args()

    if args.runs <= 0:
        raise SystemExit("--runs deve ser maior que 0.")
    if args.obstacles < 0:
        raise SystemExit("--obstacles não pode ser negativo.")

    output_path = args.output or _campaign_output_path(args.planner)
    if output_path.exists():
        if not args.overwrite:
            raise SystemExit(
                f"O ficheiro já existe: {output_path}\n"
                "Usa outro --output ou passa --overwrite para substituir."
            )
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    seeds = [args.initial_seed + i for i in range(args.runs)]
    total_runs = len(args.robots) * len(seeds)
    current_run = 1

    print("===================================")
    print(f" {_planner_label(args.planner)}")
    print("===================================")
    print(f"Mapa:                 {args.map}")
    print(f"Robôs:                {args.robots}")
    print(f"Runs por config:      {args.runs}")
    print(f"Seeds por config:     {seeds[0]}–{seeds[-1]}")
    print(f"Obstáculos dinâmicos: {args.obstacles}")
    print(f"Max ticks:            {args.ticks}")
    print(f"Total simulações:     {total_runs}")
    print(f"Output CSV:           {output_path}")

    if args.planner == "qlearning":
        model_path = args.q_table or config.Q_TABLE_PATH
        if model_path.exists():
            print(f"Q-table:              {model_path} (avaliação greedy)")
        elif args.allow_online_qlearning:
            print("Q-table:              não encontrada (treino online/debug; não usar como avaliação final)")
        else:
            raise SystemExit(
                f"Q-table não encontrada: {model_path}. "
                "Treina primeiro com train_q_learning.py ou usa --allow-online-qlearning apenas para debug."
            )

    print()

    per_config_summary: list[dict] = []

    for robots in args.robots:
        print(f"\n===== {robots} ROBÔS =====")
        config_results = []

        # Importante: os mesmos seeds são repetidos para cada valor de robots.
        # Isto evita comparar 10 robôs em seeds diferentes de 50 robôs.
        for run_number, seed in enumerate(seeds, start=1):
            print(
                f"[{current_run}/{total_runs}] "
                f"Run {run_number}/{args.runs} "
                f"| Robots={robots} "
                f"| Seed={seed}"
            )

            result = run(
                map_path=args.map,
                num_robots=robots,
                dynamic_obstacles=args.obstacles,
                max_ticks=args.ticks,
                seed=seed,
                stop_when_all_done=not args.no_early_stop,
                verbose=False,
                output_path=output_path,
                save_csv=True,
                planner=args.planner,
                q_table_path=args.q_table,
                allow_online_qlearning=args.allow_online_qlearning,
            )
            config_results.append(result)
            current_run += 1

        completion_rates = [r["metrics"].get("success_rate", 0.0) for r in config_results]
        safe_rates = [1.0 if r.get("safe_success") else 0.0 for r in config_results]
        makespans = [r["metrics"].get("makespan", 0) for r in config_results]
        waits = [r["engine_stats"].get("total_waits", 0) for r in config_results]
        replans = [r["engine_stats"].get("total_replans", 0) for r in config_results]
        collisions = [r["engine_stats"].get("total_collisions", 0) for r in config_results]

        summary = {
            "robots": robots,
            "avg_completion_rate": mean(completion_rates),
            "safe_success_rate": mean(safe_rates),
            "avg_makespan": mean(makespans),
            "avg_waits": mean(waits),
            "avg_replans": mean(replans),
            "avg_collisions": mean(collisions),
        }
        per_config_summary.append(summary)

        print(
            f"Resumo {robots}: "
            f"completion={summary['avg_completion_rate']:.3f}, "
            f"safe_success={summary['safe_success_rate']:.3f}, "
            f"makespan={summary['avg_makespan']:.1f}, "
            f"waits={summary['avg_waits']:.1f}, "
            f"replans={summary['avg_replans']:.1f}, "
            f"collisions={summary['avg_collisions']:.1f}"
        )

    print("\n===================================")
    print("Simulações concluídas.")
    print(f"Resultados em {output_path}")
    print("===================================")
    print("\nResumo por configuração:")
    for s in per_config_summary:
        print(
            f"  robots={s['robots']:>3} | "
            f"completion={s['avg_completion_rate']:.3f} | "
            f"safe_success={s['safe_success_rate']:.3f} | "
            f"makespan={s['avg_makespan']:.1f} | "
            f"waits={s['avg_waits']:.1f} | "
            f"replans={s['avg_replans']:.1f} | "
            f"collisions={s['avg_collisions']:.1f}"
        )


if __name__ == "__main__":
    main()
