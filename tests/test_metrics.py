"""
Testes de paridade entre o sistema antigo de métricas (Engine) e o novo
(SimulationMetrics).

Objetivo: garantir que a integração não introduziu divergência semântica
e que SIM_START / makespan / success_rate funcionam.

Convenções:
  - Os contadores antigos e novos DEVEM coincidir após a alteração de
    semântica do ROBOT_WAIT e COLLISION feita no Engine.
  - makespan > 0 após pelo menos um TICK.
  - success_rate em [0, 1].
"""
from __future__ import annotations

from pathlib import Path

import pytest

from environment.engine import Engine
from environment.multi_robot import create_robots
from metrics import SimulationMetrics, EventType


MAP_PATH = Path("scenarios/warehouse-10-20-10-2-1.map")


def _build(num_robots: int = 6, obstacles: int = 10, seed: int = 42):
    metrics = SimulationMetrics()
    engine = Engine(MAP_PATH, metrics=metrics)
    engine.obstacle_manager.spawn_random_dynamic(count=obstacles)
    robots = create_robots(engine, num_robots, seed=seed)
    assert robots, "Não foi possível colocar robôs no mapa de teste."
    engine.start(num_robots=len(robots))
    return engine, robots, metrics


def _run(engine, robots, max_ticks: int = 300) -> int:
    ticks = 0
    for _ in range(max_ticks):
        engine.step()
        ticks += 1
        if all(r.has_reached_goal() for r in robots):
            break
    engine.end()
    return ticks


# ---------------------------------------------------------------------------
# Paridade de contadores
# ---------------------------------------------------------------------------

def test_parity_replans():
    engine, robots, metrics = _build()
    _run(engine, robots)
    engine_replans = sum(getattr(r, "replan_count", 0) for r in robots)
    assert metrics.replan_count == engine_replans, (
        f"replan divergente: engine={engine_replans} metrics={metrics.replan_count}"
    )


def test_parity_waits():
    engine, robots, metrics = _build()
    _run(engine, robots)
    assert metrics.wait_count == engine.total_waits, (
        f"wait divergente: engine={engine.total_waits} "
        f"metrics={metrics.wait_count}"
    )


def test_parity_collisions():
    engine, robots, metrics = _build()
    _run(engine, robots)
    assert metrics.collision_count == engine.total_collisions, (
        f"collision divergente: engine={engine.total_collisions} "
        f"metrics={metrics.collision_count}"
    )


def test_parity_completed():
    engine, robots, metrics = _build()
    _run(engine, robots)
    engine_completed = sum(1 for r in robots if r.has_reached_goal())
    assert metrics.robots_completed == engine_completed


# ---------------------------------------------------------------------------
# Lifecycle: SIM_START / SIM_END / makespan / success_rate
# ---------------------------------------------------------------------------

def test_sim_start_emitted_once_and_idempotent():
    engine, robots, metrics = _build()
    engine.start(num_robots=len(robots))  # segunda chamada deve ser no-op
    starts = [e for e in metrics.events if e.type is EventType.SIM_START]
    assert len(starts) == 1
    assert starts[0].payload.get("num_robots") == len(robots)


def test_sim_end_emitted_once_and_idempotent():
    engine, robots, metrics = _build()
    _run(engine, robots)
    engine.end()  # segunda chamada deve ser no-op
    ends = [e for e in metrics.events if e.type is EventType.SIM_END]
    assert len(ends) == 1


def test_makespan_positive_after_run():
    engine, robots, metrics = _build()
    ticks = _run(engine, robots)
    assert ticks > 0
    assert metrics.makespan > 0, "makespan deve ser > 0 após pelo menos um TICK"


def test_success_rate_in_range():
    engine, robots, metrics = _build()
    _run(engine, robots)
    sr = metrics.success_rate
    assert 0.0 <= sr <= 1.0
    # Sanidade: success_rate é coerente com a contagem de completos.
    assert abs(sr - (metrics.robots_completed / len(robots))) < 1e-9


def test_average_completion_time_non_negative():
    engine, robots, metrics = _build()
    _run(engine, robots)
    assert metrics.average_completion_time >= 0.0


# ---------------------------------------------------------------------------
# Robustez: engine sem métricas continua a funcionar
# ---------------------------------------------------------------------------

def test_engine_works_without_metrics():
    engine = Engine(MAP_PATH)  # sem metrics
    engine.obstacle_manager.spawn_random_dynamic(count=5)
    robots = create_robots(engine, 4, seed=1)
    assert robots
    # start/end devem ser no-op silenciosos sem metrics
    engine.start(num_robots=len(robots))