from environment.grid import Grid, Cell
from environment.obstacles import ObstacleManager

def first_free(g: Grid) -> tuple[int,int]:
    for y, row in enumerate(g.cells):
        for x, c in enumerate(row):
            if c == Cell.FREE:
                return x, y
    raise RuntimeError("No free cell")

def count_static(g: Grid) -> int:
    return sum(1 for row in g.cells for c in row if c == Cell.OBSTACLE)

def test_dynamic_does_not_change_static_grid():
    g = Grid(4, 4)
    g.set_obstacle(0, 0)
    om = ObstacleManager(g)

    static_before = count_static(g)
    x, y = first_free(g)

    assert om.add_dynamic(x, y, duration=2, kind="box")
    assert om.is_blocked(x, y)

    om.tick()
    om.tick()  # expira
    assert not om.is_blocked(x, y)

    static_after = count_static(g)
    assert static_after == static_before

def test_dynamic_expires_after_n_ticks():
    g = Grid(3, 3)
    om = ObstacleManager(g)

    assert om.add_dynamic(1, 1, duration=1, kind="tmp")
    expired = om.tick()
    assert (1, 1) in expired
    assert not om.is_blocked(1, 1)

def test_cannot_place_dynamic_on_static():
    g = Grid(3, 3)
    g.set_obstacle(1, 1)
    om = ObstacleManager(g)

    assert om.add_dynamic(1, 1, duration=3) is False
    assert om.is_blocked(1, 1) is True  # por ser estático

def test_duration_validation():
    g = Grid(3, 3)
    om = ObstacleManager(g)

    assert om.add_dynamic(0, 1, duration=0) is False
    assert om.add_dynamic(0, 1, duration=-2) is False
    assert om.add_dynamic(0, 1, duration=1) is True