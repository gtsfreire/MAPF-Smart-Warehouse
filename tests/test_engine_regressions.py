"""
Regression tests for Engine-level MAPF coordination bugs.

These tests intentionally cover behaviours that are not exercised by the
low-level unit tests: temporal planned waits, qlearning resolver integration,
and completed robots remaining as physical occupancy in the grid.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import config.settings as config
from agents.robot import Robot
from agents.conflict_resolution import ConflictAction, ConflictResolver
from environment.engine import Engine


def _write_map(tmp_path: Path, rows: list[str]) -> Path:
    width = len(rows[0])
    height = len(rows)
    content = "\n".join([
        "type octile",
        f"height {height}",
        f"width {width}",
        "map",
        *rows,
        "",
    ])
    path = tmp_path / "test.map"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def restore_planner():
    old = config.PLANNER
    yield
    config.PLANNER = old


class CountingResolver(ConflictResolver):
    def __init__(self, action: ConflictAction = ConflictAction.WAIT):
        self.action = action
        self.decisions = 0
        self.observations = 0

    def decide(self, ctx):
        self.decisions += 1
        return self.action

    def observe(self, ctx, action, reward: float = 0.0) -> None:
        self.observations += 1


def test_temporal_planned_wait_consumes_path_index(tmp_path):
    """A* may encode waiting as repeated positions in the path.

    The Engine must consume that temporal wait with move_one_step(); otherwise
    the robot stays forever at the first repeated state.
    """
    config.PLANNER = "prioritized"
    engine = Engine(_write_map(tmp_path, ["..."]))

    robot = Robot(1, start=(0, 0), goal=(2, 0))
    robot.path = [((0, 0), 0), ((0, 0), 1), ((1, 0), 2), ((2, 0), 3)]
    robot.current_position = (0, 0)
    engine.robots.append(robot)

    result = engine.step()

    assert result["collisions"] == {}
    assert robot.current_position == (0, 0)
    assert robot.last_action == "planned_wait"
    assert robot._path_index == 1

    engine.step()
    assert robot.current_position == (1, 0)
    assert robot._path_index == 2


def test_qlearning_planner_invokes_conflict_resolver_for_blocked_robot(tmp_path):
    """PLANNER='qlearning' must use the same conflict layer as prioritized."""
    config.PLANNER = "qlearning"
    resolver = CountingResolver(action=ConflictAction.WAIT)
    engine = Engine(_write_map(tmp_path, ["..."]), conflict_resolver=resolver)

    r1 = Robot(1, start=(0, 0), goal=(2, 0))
    r1.path = [((0, 0), 0), ((1, 0), 1), ((2, 0), 2)]
    r1.current_position = (0, 0)

    r2 = Robot(2, start=(2, 0), goal=(0, 0))
    r2.path = [((2, 0), 0), ((1, 0), 1), ((0, 0), 2)]
    r2.current_position = (2, 0)

    engine.robots.extend([r1, r2])
    result = engine.step()

    assert resolver.decisions >= 1
    assert engine.total_blocked_intents >= 1
    assert result["collisions"] == {}


def test_completed_robot_goal_counts_as_occupied_cell(tmp_path):
    """Completed robots remain physically on their goal cell.

    Active robots must not be allowed to move into that cell silently, otherwise
    completion can drop due to hidden blocking/collisions near occupied goals.
    """
    config.PLANNER = "prioritized"
    engine = Engine(_write_map(tmp_path, ["..."]))

    completed = Robot(1, start=(1, 0), goal=(1, 0))
    completed.current_position = (1, 0)
    completed.reached_goal = True
    completed.path = [((1, 0), 0)]

    active = Robot(2, start=(0, 0), goal=(2, 0))
    active.current_position = (0, 0)
    active.path = [((0, 0), 0), ((1, 0), 1), ((2, 0), 2)]

    engine.robots.extend([completed, active])
    result = engine.step()

    assert result["collisions"] == {}
    assert active.current_position == (0, 0)
    assert active.robot_id in result["blocked_robots"]
    assert engine.total_waits == 1
