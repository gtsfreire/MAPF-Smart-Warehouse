from metrics import SimulationMetrics, Event, EventType


def _ev(t, tick, **kw):
    return Event(type=t, tick=tick, **kw)


def test_counters_via_events():
    m = SimulationMetrics()
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 3}))
    m.record(_ev(EventType.ROBOT_SPAWN, 0, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_SPAWN, 0, robot_id="r2"))
    m.record(_ev(EventType.ROBOT_SPAWN, 0, robot_id="r3"))
    m.record(_ev(EventType.ROBOT_WAIT, 1, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_REPLAN, 2, robot_id="r2"))
    m.record(_ev(EventType.COLLISION, 3, robot_ids=("r1", "r2")))
    m.record(_ev(EventType.ROBOT_GOAL, 5, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_GOAL, 7, robot_id="r2"))
    m.record(_ev(EventType.SIM_END, 10))

    d = m.to_dict()
    assert d["wait_count"] == 1
    assert d["replan_count"] == 1
    assert d["collision_count"] == 1
    assert d["makespan"] == 10
    assert d["robots_completed"] == 2
    assert d["success_rate"] == 2 / 3
    assert d["average_completion_time"] == (5 + 7) / 2


def test_goal_reached_is_idempotent_per_robot():
    m = SimulationMetrics()
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 1}))
    m.record(_ev(EventType.ROBOT_GOAL, 4, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_GOAL, 9, robot_id="r1"))  # ignorado
    assert m.robots_completed == 1
    assert m._completion_ticks["r1"] == 4


def test_no_robots_completed():
    m = SimulationMetrics()
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 2}))
    m.record(_ev(EventType.SIM_END, 5))
    d = m.to_dict()
    assert d["success_rate"] == 0.0
    assert d["average_completion_time"] == 0.0


def test_completion_uses_spawn_when_available():
    m = SimulationMetrics()
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 2}))
    m.record(_ev(EventType.ROBOT_SPAWN, 0, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_SPAWN, 5, robot_id="r2"))  # staggered
    m.record(_ev(EventType.ROBOT_GOAL, 10, robot_id="r1"))
    m.record(_ev(EventType.ROBOT_GOAL, 15, robot_id="r2"))
    m.record(_ev(EventType.SIM_END, 15))
    # r1: 10-0=10 ; r2: 15-5=10 -> média 10
    assert m.average_completion_time == 10.0


def test_completion_fallbacks_to_sim_start_without_spawn():
    m = SimulationMetrics()
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 1}))
    m.record(_ev(EventType.ROBOT_GOAL, 8, robot_id="r1"))
    m.record(_ev(EventType.SIM_END, 8))
    assert m.average_completion_time == 8.0


def test_event_log_can_be_disabled():
    m = SimulationMetrics(keep_event_log=False)
    m.record(_ev(EventType.SIM_START, 0, payload={"num_robots": 1}))
    m.record(_ev(EventType.ROBOT_WAIT, 1, robot_id="r1"))
    assert m.wait_count == 1
    assert m.events == []