from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import config.settings as config
from agents.conflict_resolution import ConflictAction, ConflictContext, ConflictResolver
from agents.conflict_resolution.rewards import default_reward
from environment.grid import Grid
from environment.loader import load_map
from environment.obstacles import ObstacleManager
from metrics import Event, EventType, SimulationMetrics


def _safe_sort_key(robot_id):
    try:
        return (0, int(robot_id))
    except (TypeError, ValueError):
        return (1, str(robot_id))


class Engine:
    """Motor central da simulação MAPF.

    O Engine mantém a simulação física, coordena conflitos em modos
    `prioritized`/`qlearning`, emite eventos para métricas e aplica fallback
    determinístico de replanning quando robôs ficam bloqueados.
    """

    def __init__(
        self,
        map_path: str | Path,
        metrics: SimulationMetrics | None = None,
        conflict_resolver: ConflictResolver | None = None,
        reward_fn=default_reward,
        **kwargs,
    ):
        self.grid: Grid = load_map(Path(map_path))
        self.obstacle_manager = ObstacleManager(self.grid)
        self.robots: list = []
        self.tick_count = 0

        self.total_collisions = 0
        self.total_conflicts = 0
        self.total_waits = 0
        self.total_blocked_intents = 0
        self.blocked_ticks: dict[int, int] = defaultdict(int)
        self.deadlock_replan_threshold = 3
        self.last_blocked_robots: list[int] = []

        self._max_time = (self.grid.width + self.grid.height) * 2
        self._metrics = metrics
        self._sim_started = False
        self._sim_ended = False

        self._resolver = conflict_resolver
        self._reward_fn = reward_fn
        self._pending_decisions: dict[int, tuple[ConflictContext, ConflictAction]] = {}

    # ------------------------------------------------------------------
    # Modos / eventos
    # ------------------------------------------------------------------

    def _uses_conflict_resolution(self) -> bool:
        return config.PLANNER in ("prioritized", "qlearning") or self._resolver is not None

    def _uses_cooperative_initial_planning(self) -> bool:
        return config.PLANNER in ("prioritized", "qlearning") or self._resolver is not None

    def _emit(self, event_type: EventType, *, robot_id=None, robot_ids=None, **payload) -> None:
        if self._metrics is None:
            return
        if robot_ids is not None:
            robot_ids = tuple(sorted(robot_ids, key=_safe_sort_key))
        self._metrics.record(
            Event(
                type=event_type,
                tick=self.tick_count,
                robot_id=robot_id,
                robot_ids=robot_ids,
                payload=payload,
            )
        )

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def start(self, num_robots: int | None = None) -> None:
        if self._sim_started:
            return
        self._sim_started = True
        self._emit(EventType.SIM_START, num_robots=int(num_robots or len(self.robots)))

    def end(self) -> None:
        if self._sim_ended or not self._sim_started:
            return
        self._sim_ended = True
        self._emit(EventType.SIM_END)
        if self._resolver is not None:
            self._resolver.reset()

    # ------------------------------------------------------------------
    # Gestão de robôs
    # ------------------------------------------------------------------

    def add_robot(self, robot) -> bool:
        sx, sy = robot.start
        gx, gy = robot.goal

        if not self.grid.is_walkable(sx, sy):
            print(f"[Engine] Robot {robot.robot_id}: start {robot.start} não é walkable.")
            return False
        if not self.grid.is_walkable(gx, gy):
            print(f"[Engine] Robot {robot.robot_id}: goal {robot.goal} não é walkable.")
            return False
        if self.obstacle_manager.is_dynamic(sx, sy):
            print(f"[Engine] Robot {robot.robot_id}: start {robot.start} ocupado por obstáculo dinâmico.")
            return False
        if self.obstacle_manager.is_dynamic(gx, gy):
            print(f"[Engine] Robot {robot.robot_id}: goal {robot.goal} ocupado por obstáculo dinâmico.")
            return False

        self.robots.append(robot)
        path = robot.plan_path(
            self.get_combined_grid(),
            max_time=self._max_time,
            vertex_constraints=self._initial_vertex_constraints(robot.robot_id),
        )

        if not path:
            path = robot.plan_path(self.get_combined_grid(), max_time=self._max_time)
        if not path:
            print(
                f"[Engine] Robot {robot.robot_id}: {config.PLANNER} não encontrou caminho "
                f"de {robot.start} para {robot.goal}."
            )
            self.robots.pop()
            return False

        self._emit(EventType.ROBOT_SPAWN, robot_id=robot.robot_id)
        return True

    def remove_robot(self, robot_id: int) -> bool:
        before = len(self.robots)
        self.robots = [r for r in self.robots if r.robot_id != robot_id]
        return len(self.robots) < before

    def _get_robot_by_id(self, robot_id: int):
        return next((robot for robot in self.robots if robot.robot_id == robot_id), None)

    def _initial_vertex_constraints(self, new_robot_id: int) -> set | None:
        if not self._uses_cooperative_initial_planning():
            return None

        constraints: set = set()
        for other in self.robots:
            if other.robot_id == new_robot_id:
                continue

            constraints.update((pos, t) for pos, t in other.path)

            if other.path:
                final_pos, final_t = other.path[-1]
                constraints.update((final_pos, t) for t in range(final_t, self._max_time + 1))
            else:
                constraints.update(
                    (other.current_position, t) for t in range(self._max_time + 1)
                )

        return constraints or None

    # ------------------------------------------------------------------
    # Grid / planeamento
    # ------------------------------------------------------------------

    def get_combined_grid(self) -> list[list[int]]:
        combined = [
            [int(self.grid.cells[y][x]) for x in range(self.grid.width)]
            for y in range(self.grid.height)
        ]
        for x, y in self.obstacle_manager.dynamic_obstacles:
            if 0 <= y < self.grid.height and 0 <= x < self.grid.width:
                combined[y][x] = 1
        return combined

    def _build_future_constraints(self, exclude_robot_id: int) -> set:
        constraints: set = set()
        for other in self.robots:
            if other.robot_id == exclude_robot_id:
                continue

            constraints.add((other.current_position, 0))

            if other.has_reached_goal():
                constraints.update((other.current_position, t) for t in range(1, 11))
                continue

            for offset in range(1, 11):
                idx = other._path_index + offset
                if idx < len(other.path):
                    pos, _ = other.path[idx]
                    constraints.add((pos, offset))
                elif other.path:
                    pos, _ = other.path[-1]
                    constraints.add((pos, offset))

        return constraints

    def _replan_robot(
        self,
        robot,
        grid=None,
        *,
        vertex_constraints=None,
        edge_constraints=None,
        max_time=None,
        replanned: list[int] | None = None,
        already_replanned: set[int] | None = None,
    ) -> bool:
        ok = robot.replan(
            grid if grid is not None else self.get_combined_grid(),
            vertex_constraints=vertex_constraints,
            edge_constraints=edge_constraints,
            max_time=self._max_time if max_time is None else max_time,
        )
        if replanned is not None:
            replanned.append(robot.robot_id)
        if already_replanned is not None:
            already_replanned.add(robot.robot_id)
        self._emit(EventType.ROBOT_REPLAN, robot_id=robot.robot_id)
        return ok

    # ------------------------------------------------------------------
    # Conflitos
    # ------------------------------------------------------------------

    @staticmethod
    def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _is_narrow_corridor(self, pos: tuple[int, int]) -> bool:
        combined = self.get_combined_grid()
        x, y = pos
        h_blocked = (
            (x - 1 < 0 or combined[y][x - 1] == 1)
            and (x + 1 >= self.grid.width or combined[y][x + 1] == 1)
        )
        v_blocked = (
            (y - 1 < 0 or combined[y - 1][x] == 1)
            and (y + 1 >= self.grid.height or combined[y + 1][x] == 1)
        )
        return h_blocked or v_blocked

    def _intended_moves(self) -> dict[int, tuple[tuple[int, int], tuple[int, int]]]:
        intents = {}
        for robot in self.robots:
            if robot.has_reached_goal():
                continue
            cur = robot.current_position
            nxt = robot.peek_next_position()
            intents[robot.robot_id] = (cur, nxt if nxt is not None else cur)
        return intents

    def _resolve_conflicts(
        self,
        intents: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    ) -> set[int]:
        def priority_key(robot_id):
            return (-self.blocked_ticks.get(robot_id, 0), robot_id)

        ordered_ids = sorted(intents.keys(), key=priority_key)
        intended = {rid: intents[rid][1] for rid in ordered_ids}
        current = {rid: intents[rid][0] for rid in ordered_ids}

        def will_advance(robot_id: int) -> bool:
            return intended[robot_id] != current[robot_id]

        swap_pairs = self._swap_pair_ids(ordered_ids, current, intended, will_advance)
        waiting_cells = {current[rid] for rid in ordered_ids if not will_advance(rid)}
        waiting_cells.update(robot.current_position for robot in self.robots if robot.has_reached_goal())

        allowed: set[int] = set()
        claimed_targets: dict[tuple[int, int], int] = {}

        for rid in ordered_ids:
            cur = current[rid]
            tgt = intended[rid]

            if not will_advance(rid) or rid in swap_pairs or tgt in waiting_cells or tgt in claimed_targets:
                claimed_targets[cur] = rid
                continue

            allowed.add(rid)
            claimed_targets[tgt] = rid

        return allowed

    @staticmethod
    def _swap_pair_ids(ordered_ids, current, intended, will_advance) -> set[int]:
        swap_pairs: set[int] = set()
        for i, rid_a in enumerate(ordered_ids):
            for rid_b in ordered_ids[i + 1:]:
                if (
                    current[rid_a] == intended[rid_b]
                    and current[rid_b] == intended[rid_a]
                    and will_advance(rid_a)
                    and will_advance(rid_b)
                ):
                    swap_pairs.update((rid_a, rid_b))
        return swap_pairs

    def _find_yield_position(
        self,
        robot,
        intents: dict[int, tuple[tuple[int, int], tuple[int, int]]],
        allowed_ids: set[int],
        allow_backward: bool = False,
    ) -> tuple[int, int] | None:
        current = robot.current_position
        intended = intents.get(robot.robot_id, (current, current))[1]
        x, y = current
        combined = self.get_combined_grid()

        blocked_positions = {
            other.current_position for other in self.robots if other.robot_id != robot.robot_id
        }
        reserved_targets = {
            intended_pos
            for other_id, (_, intended_pos) in intents.items()
            if other_id in allowed_ids
        }
        future_occupied = self._future_occupied_positions(robot.robot_id, lookahead=3)

        candidates = [(x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)]
        move_dx, move_dy = self._movement_vector(robot, current, intended)

        def movement_score(pos: tuple[int, int]) -> int:
            dot = (pos[0] - current[0]) * move_dx + (pos[1] - current[1]) * move_dy
            if dot > 0:
                return 1
            if dot == 0:
                return 0
            return 2 if allow_backward else 99

        valid = []
        for cx, cy in candidates:
            if not (0 <= cx < self.grid.width and 0 <= cy < self.grid.height):
                continue
            if combined[cy][cx] == 1:
                continue
            if (cx, cy) in blocked_positions or (cx, cy) in reserved_targets:
                continue
            if (cx, cy) in future_occupied:
                continue
            if movement_score((cx, cy)) == 99:
                continue
            valid.append((cx, cy))

        if not valid:
            return None

        valid.sort(key=lambda pos: (movement_score(pos), self._manhattan(pos, robot.goal)))
        return valid[0]

    def _future_occupied_positions(self, robot_id: int, lookahead: int) -> set[tuple[int, int]]:
        positions: set[tuple[int, int]] = set()
        for other in self.robots:
            if other.robot_id == robot_id:
                continue
            for offset in range(1, lookahead + 1):
                idx = other._path_index + offset
                if idx < len(other.path):
                    pos, _ = other.path[idx]
                    positions.add(pos)
        return positions

    @staticmethod
    def _movement_vector(robot, current, intended) -> tuple[int, int]:
        dx = intended[0] - current[0]
        dy = intended[1] - current[1]
        if dx != 0 or dy != 0:
            return dx, dy

        goal_dx = robot.goal[0] - current[0]
        goal_dy = robot.goal[1] - current[1]
        if abs(goal_dx) >= abs(goal_dy):
            return (1 if goal_dx > 0 else -1 if goal_dx < 0 else 0), 0
        return 0, (1 if goal_dy > 0 else -1 if goal_dy < 0 else 0)

    # ------------------------------------------------------------------
    # Q-learning context / feedback
    # ------------------------------------------------------------------

    def _make_context(
        self,
        robot,
        intents: dict[int, tuple[tuple[int, int], tuple[int, int]]],
    ) -> ConflictContext:
        cur, intended = intents.get(robot.robot_id, (robot.current_position, robot.current_position))
        return ConflictContext(
            tick=self.tick_count,
            robot_id=robot.robot_id,
            current_position=cur,
            intended_position=intended,
            goal=robot.goal,
            blocked_ticks=robot.consecutive_blocked_ticks,
            others={rid: move for rid, move in intents.items() if rid != robot.robot_id},
        )

    def _resolver_decisions(self, blocked_set: set[int], intents) -> dict[int, ConflictAction]:
        actions: dict[int, ConflictAction] = {}
        if self._resolver is None or not blocked_set:
            return actions

        for robot in self.robots:
            if robot.robot_id not in blocked_set or robot.has_reached_goal():
                continue
            ctx = self._make_context(robot, intents)
            action = self._resolver.decide(ctx)
            actions[robot.robot_id] = action
            self._pending_decisions[robot.robot_id] = (ctx, action)
        return actions

    def _give_resolver_feedback(self, collisions) -> None:
        if self._resolver is None or not self._pending_decisions:
            return

        collided_ids = {rid for ids in collisions.values() for rid in ids}
        new_intents = self._intended_moves()
        closed: list[int] = []

        for rid, (prev_ctx, action) in self._pending_decisions.items():
            robot = self._get_robot_by_id(rid)
            if robot is None:
                closed.append(rid)
                continue
            new_ctx = self._make_context(robot, new_intents)
            reward = self._reward_fn(
                prev_ctx,
                action,
                new_ctx,
                collided=rid in collided_ids,
                reached_goal=robot.has_reached_goal(),
            )
            self._resolver.observe(new_ctx, action, reward=reward)
            robot.last_reward = reward
            closed.append(rid)

        for rid in closed:
            self._pending_decisions.pop(rid, None)

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def step(self) -> dict:
        already_completed = {r.robot_id for r in self.robots if r.has_reached_goal()}
        steps_before = {r.robot_id: int(getattr(r, "steps_taken", 0)) for r in self.robots}
        self.tick_count += 1

        replanned = self._reactive_replanning()
        intents = self._intended_moves()
        uses_conflict_resolution = self._uses_conflict_resolution()
        allowed_ids = self._allowed_ids(intents, uses_conflict_resolution)
        blocked_robots = self._register_blocked_robots(intents, allowed_ids, uses_conflict_resolution)
        blocked_set = set(blocked_robots)

        resolver_actions = self._resolver_decisions(blocked_set, intents)
        already_replanned = set(replanned)
        swap_resolved = self._handle_narrow_swaps(
            intents,
            allowed_ids,
            blocked_set,
            replanned,
            already_replanned,
        )

        self._execute_movements(
            intents=intents,
            allowed_ids=allowed_ids,
            blocked_set=blocked_set,
            resolver_actions=resolver_actions,
            replanned=replanned,
            already_replanned=already_replanned,
            swap_resolved=swap_resolved,
            uses_conflict_resolution=uses_conflict_resolution,
        )
        self._secondary_deadlock_recovery(blocked_robots, already_replanned, uses_conflict_resolution, replanned)

        expired = self.obstacle_manager.tick()
        collisions = self._detect_collisions(uses_conflict_resolution)
        completed = self._emit_new_completions(already_completed)
        self._emit(EventType.TICK)
        self._update_metrics(steps_before)
        self._give_resolver_feedback(collisions)

        return self._step_result(
            completed=completed,
            collisions=collisions,
            expired=expired,
            replanned=replanned,
            blocked_robots=blocked_robots,
        )

    def _reactive_replanning(self) -> list[int]:
        combined = self.get_combined_grid()
        replanned: list[int] = []

        for robot in self.robots:
            if robot.has_reached_goal():
                continue
            nxt = robot.peek_next_position()
            needs_replan = nxt is None and not robot.has_reached_goal()
            if nxt is not None:
                nx, ny = nxt
                needs_replan = combined[ny][nx] == 1
            if needs_replan:
                self._replan_robot(robot, self.get_combined_grid(), max_time=self._max_time, replanned=replanned)

        return replanned

    def _allowed_ids(self, intents, uses_conflict_resolution: bool) -> set[int]:
        if uses_conflict_resolution:
            return self._resolve_conflicts(intents)
        return {robot_id for robot_id, (cur, intended) in intents.items() if intended != cur}

    def _register_blocked_robots(self, intents, allowed_ids, uses_conflict_resolution) -> list[int]:
        blocked = []
        if uses_conflict_resolution:
            blocked = [
                robot_id
                for robot_id, (cur, intended) in intents.items()
                if intended != cur and robot_id not in allowed_ids
            ]

        self.last_blocked_robots = blocked
        self.total_blocked_intents += len(blocked)
        if blocked:
            self.total_conflicts += len(blocked)
        return blocked

    def _handle_narrow_swaps(
        self,
        intents,
        allowed_ids,
        blocked_set,
        replanned,
        already_replanned,
    ) -> set[int]:
        swap_resolved: set[int] = set()
        processed: set[int] = set()

        for robot in self.robots:
            if robot.robot_id not in blocked_set or robot.has_reached_goal() or robot.robot_id in processed:
                continue

            cur_pos, intended_pos = intents.get(robot.robot_id, (robot.current_position, robot.current_position))
            partner = self._head_on_partner(robot.robot_id, cur_pos, intended_pos, intents)
            if partner is None or not self._is_narrow_corridor(cur_pos):
                continue

            receding, advancing = self._choose_receding_robot(robot, partner)
            yield_pos = self._find_yield_position(receding, intents, allowed_ids, allow_backward=True)

            if yield_pos is not None:
                self._manual_yield(receding, yield_pos, replanned, already_replanned)
            else:
                self._prepare_swap_deadlock_replan(
                    receding,
                    advancing,
                    intended_pos,
                    replanned,
                    already_replanned,
                )

            processed.update((robot.robot_id, partner.robot_id))
            if yield_pos is not None:
                swap_resolved.update((robot.robot_id, partner.robot_id))

        return swap_resolved

    def _head_on_partner(self, robot_id, cur_pos, intended_pos, intents):
        return next(
            (
                other
                for other in self.robots
                if other.robot_id != robot_id
                and not other.has_reached_goal()
                and intents.get(other.robot_id, (None, None))[0] == intended_pos
                and intents.get(other.robot_id, (None, None))[1] == cur_pos
            ),
            None,
        )

    def _choose_receding_robot(self, robot, partner):
        self_blocked = self.blocked_ticks.get(robot.robot_id, 0)
        partner_blocked = self.blocked_ticks.get(partner.robot_id, 0)
        receding = robot if self_blocked <= partner_blocked else partner
        advancing = partner if self_blocked <= partner_blocked else robot
        return receding, advancing

    def _manual_yield(self, robot, yield_pos, replanned, already_replanned) -> None:
        robot.current_position = yield_pos
        robot.steps_taken += 1
        if robot.current_position == robot.goal:
            robot.reached_goal = True
        self._replan_robot(
            robot,
            self.get_combined_grid(),
            max_time=self._max_time,
            replanned=replanned,
            already_replanned=already_replanned,
        )
        self.blocked_ticks[robot.robot_id] = 0
        robot.consecutive_blocked_ticks = 0
        robot.last_action = "yield"

    def _prepare_swap_deadlock_replan(self, receding, advancing, intended_pos, replanned, already_replanned) -> None:
        constraints = self._build_future_constraints(receding.robot_id)
        for t in range(self._max_time):
            constraints.add((advancing.current_position, t))
            constraints.add((intended_pos, t))

        self._replan_robot(
            receding,
            self.get_combined_grid(),
            vertex_constraints=constraints,
            max_time=self._max_time,
            replanned=replanned,
            already_replanned=already_replanned,
        )
        if not receding.path:
            self._replan_robot(
                receding,
                self.get_combined_grid(),
                max_time=self._max_time,
                replanned=replanned,
                already_replanned=already_replanned,
            )
        receding.last_action = "replan"

    def _execute_movements(
        self,
        *,
        intents,
        allowed_ids,
        blocked_set,
        resolver_actions,
        replanned,
        already_replanned,
        swap_resolved,
        uses_conflict_resolution,
    ) -> None:
        for robot in self.robots:
            if robot.has_reached_goal():
                self._reset_blocked(robot)
                continue

            if robot.robot_id in swap_resolved:
                if robot.robot_id in allowed_ids:
                    self._move_robot(robot)
                continue

            if robot.robot_id in allowed_ids:
                self._move_robot(robot)
                continue

            if robot.peek_next_position() == robot.current_position and robot.has_plan():
                self._move_robot(robot, action="planned_wait")
                continue

            action = resolver_actions.get(robot.robot_id, ConflictAction.WAIT)
            if action is ConflictAction.REPLAN:
                self._replan_and_reset(robot, replanned, already_replanned)
                continue

            if action is ConflictAction.YIELD:
                yield_pos = self._find_yield_position(robot, intents, allowed_ids)
                if yield_pos is not None:
                    self._manual_yield(robot, yield_pos, replanned, already_replanned)
                    continue

            self._wait_or_recover(robot, blocked_set, uses_conflict_resolution, replanned, already_replanned)

    def _move_robot(self, robot, action: str = "move") -> None:
        robot.move_one_step()
        self._reset_blocked(robot)
        robot.last_action = action

    def _reset_blocked(self, robot) -> None:
        self.blocked_ticks[robot.robot_id] = 0
        robot.consecutive_blocked_ticks = 0

    def _replan_and_reset(self, robot, replanned, already_replanned, vertex_constraints=None) -> None:
        self._replan_robot(
            robot,
            self.get_combined_grid(),
            vertex_constraints=vertex_constraints,
            max_time=self._max_time,
            replanned=replanned,
            already_replanned=already_replanned,
        )
        self._reset_blocked(robot)
        robot.last_action = "replan"

    def _wait_or_recover(self, robot, blocked_set, uses_conflict_resolution, replanned, already_replanned) -> None:
        robot.stay()
        robot.last_action = "stay"

        if robot.robot_id not in blocked_set:
            return

        self.total_waits += 1
        self._emit(EventType.ROBOT_WAIT, robot_id=robot.robot_id)
        self.blocked_ticks[robot.robot_id] += 1
        robot.consecutive_blocked_ticks = self.blocked_ticks[robot.robot_id]

        if (
            uses_conflict_resolution
            and self.blocked_ticks[robot.robot_id] >= self.deadlock_replan_threshold
            and robot.robot_id not in already_replanned
        ):
            self._replan_and_reset(
                robot,
                replanned,
                already_replanned,
                vertex_constraints=self._build_future_constraints(robot.robot_id),
            )

    def _secondary_deadlock_recovery(self, blocked_robots, already_replanned, uses_conflict_resolution, replanned) -> None:
        if self._resolver is not None or not uses_conflict_resolution:
            return

        for robot_id in blocked_robots:
            if robot_id in already_replanned or self.blocked_ticks[robot_id] < self.deadlock_replan_threshold:
                continue
            robot = self._get_robot_by_id(robot_id)
            if robot is None or robot.has_reached_goal():
                continue
            self._replan_and_reset(
                robot,
                replanned,
                already_replanned,
                vertex_constraints=self._build_future_constraints(robot_id),
            )

    def _detect_collisions(self, uses_conflict_resolution: bool):
        positions: dict[tuple[int, int], list[int]] = defaultdict(list)
        for robot in self.robots:
            positions[robot.current_position].append(robot.robot_id)

        collisions = {pos: ids for pos, ids in positions.items() if len(ids) > 1}
        if not collisions:
            return collisions

        extra = sum(len(ids) - 1 for ids in collisions.values())
        self.total_collisions += extra
        if not uses_conflict_resolution:
            self.total_conflicts += extra
        for ids in collisions.values():
            for _ in range(len(ids) - 1):
                self._emit(EventType.COLLISION, robot_ids=ids)
        return collisions

    def _emit_new_completions(self, already_completed: set[int]):
        completed = [robot for robot in self.robots if robot.has_reached_goal()]
        for robot in completed:
            if robot.robot_id not in already_completed:
                self._emit(EventType.ROBOT_GOAL, robot_id=robot.robot_id)
        return completed

    def _update_metrics(self, steps_before) -> None:
        if self._metrics is None:
            return
        self._metrics.update_max_consecutive_blocked(
            max((robot.consecutive_blocked_ticks for robot in self.robots), default=0)
        )
        self._metrics.add_steps(
            sum(
                max(0, int(getattr(robot, "steps_taken", 0)) - steps_before.get(robot.robot_id, 0))
                for robot in self.robots
            )
        )

    def _step_result(self, *, completed, collisions, expired, replanned, blocked_robots) -> dict:
        return {
            "tick": self.tick_count,
            "planner": config.PLANNER,
            "positions": {r.robot_id: r.current_position for r in self.robots},
            "collisions": collisions,
            "completed": [r.robot_id for r in completed],
            "expired_obstacles": expired,
            "replanned": replanned,
            "blocked_robots": blocked_robots,
            "blocked_ticks": dict(self.blocked_ticks),
            "total_conflicts": self.total_conflicts,
            "total_waits": self.total_waits,
        }

    # ------------------------------------------------------------------
    # Estatísticas finais
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        total = len(self.robots)
        completed = [robot for robot in self.robots if robot.has_reached_goal()]
        completed_count = len(completed)
        total_steps = sum(int(getattr(robot, "steps_taken", 0)) for robot in self.robots)
        completed_steps = sum(int(getattr(robot, "steps_taken", 0)) for robot in completed)

        return {
            "tick": self.tick_count,
            "planner": config.PLANNER,
            "robots_total": total,
            "robots_completed": completed_count,
            "robots_failed": max(0, total - completed_count),
            "total_collisions": self.total_collisions,
            "total_replans": sum(getattr(robot, "replan_count", 0) for robot in self.robots),
            "total_waits": self.total_waits,
            "total_blocked_intents": self.total_blocked_intents,
            "total_conflicts": self.total_conflicts,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "average_steps_per_robot": (total_steps / total) if total else 0.0,
            "average_steps_per_completed_robot": (
                completed_steps / completed_count if completed_count else 0.0
            ),
            "obstacles": self.obstacle_manager.get_stats(),
            "max_consecutive_blocked": max(
                (robot.consecutive_blocked_ticks for robot in self.robots), default=0
            ),
        }
