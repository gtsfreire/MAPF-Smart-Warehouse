"""
Recolha passiva de métricas a partir de eventos emitidos pela Engine.

Princípios:
  - A Engine é a única fonte de eventos e de tempo.
  - Esta classe não decide nada; apenas observa.
  - Counters são atualizados incrementalmente para que `to_dict()` seja O(1).
  - O event log permite reconstituição/auditoria/replay futuro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import Event, EventType


@dataclass
class SimulationMetrics:
    keep_event_log: bool = True

    # Counters
    collision_count: int = 0
    replan_count: int = 0
    wait_count: int = 0

    # Tempo
    _start_tick: Optional[int] = field(default=None, repr=False)
    _end_tick: Optional[int] = field(default=None, repr=False)
    _num_robots: int = field(default=0, repr=False)

    # Por robô
    _spawn_ticks: Dict[Any, int] = field(default_factory=dict, repr=False)
    _completion_ticks: Dict[Any, int] = field(default_factory=dict, repr=False)

    # Metadados de execução injetados pelo runner
    _planner: str = field(default="unknown", repr=False)
    _seed: Optional[int] = field(default=None, repr=False)

    # Total de ticks em que algum robô ficou bloqueado
    _total_blocked_ticks: int = field(default=0, repr=False)

    # Maior número consecutivo de ticks bloqueado observado num único robô
    _max_consecutive_blocked: int = field(default=0, repr=False)

    # Total de passos dados por todos os robôs (para replan_rate)
    _total_steps: int = field(default=0, repr=False)

    # Log estruturado (opcional)
    events: List[Event] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Injeção de metadados pelo runner
    # ------------------------------------------------------------------

    def set_run_metadata(self, planner: str, seed: Optional[int] = None) -> None:
        """Deve ser chamado pelo runner antes do início da simulação."""
        self._planner = planner
        self._seed = seed

    def update_max_consecutive_blocked(self, value: int) -> None:
        """Atualizado pelo Engine no final de cada tick."""
        if value > self._max_consecutive_blocked:
            self._max_consecutive_blocked = value

    def add_steps(self, n: int) -> None:
        """Regista passos dados por robôs num tick."""
        self._total_steps += n

    # ------------------------------------------------------------------
    # Ingestão de eventos
    # ------------------------------------------------------------------

    def record(self, event: Event) -> None:
        if self.keep_event_log:
            self.events.append(event)

        t = event.type

        if t is EventType.SIM_START:
            self._start_tick = event.tick
            self._num_robots = int(event.payload.get("num_robots", self._num_robots))

        elif t is EventType.SIM_END:
            self._end_tick = event.tick

        elif t is EventType.TICK:
            self._end_tick = event.tick

        elif t is EventType.ROBOT_SPAWN:
            if event.robot_id is not None and event.robot_id not in self._spawn_ticks:
                self._spawn_ticks[event.robot_id] = event.tick

        elif t is EventType.ROBOT_WAIT:
            self.wait_count += 1
            self._total_blocked_ticks += 1

        elif t is EventType.ROBOT_REPLAN:
            self.replan_count += 1

        elif t is EventType.COLLISION:
            self.collision_count += 1

        elif t is EventType.ROBOT_GOAL:
            rid = event.robot_id
            if rid is not None and rid not in self._completion_ticks:
                self._completion_ticks[rid] = event.tick

    # ------------------------------------------------------------------
    # Métricas derivadas
    # ------------------------------------------------------------------

    @property
    def makespan(self) -> int:
        if self._start_tick is None or self._end_tick is None:
            return 0
        return max(0, self._end_tick - self._start_tick)

    @property
    def robots_completed(self) -> int:
        return len(self._completion_ticks)

    @property
    def success_rate(self) -> float:
        if self._num_robots <= 0:
            return 0.0
        return self.robots_completed / self._num_robots

    @property
    def average_completion_time(self) -> float:
        """
        Média de (tick_de_conclusão - tick_de_spawn) por robô concluído.
        Robôs não concluídos não contam.
        """
        if not self._completion_ticks:
            return 0.0
        fallback = self._start_tick if self._start_tick is not None else 0
        deltas = [
            end_t - self._spawn_ticks.get(rid, fallback)
            for rid, end_t in self._completion_ticks.items()
        ]
        return sum(deltas) / len(deltas)

    @property
    def throughput(self) -> float:
        """Robôs concluídos por tick — normaliza pelo tempo total."""
        if self.makespan <= 0:
            return 0.0
        return self.robots_completed / self.makespan

    @property
    def avg_blocked_ticks_per_robot(self) -> float:
        """Média de ticks bloqueado por robô — mede severidade dos bloqueios."""
        if self._num_robots <= 0:
            return 0.0
        return self._total_blocked_ticks / self._num_robots

    @property
    def replan_rate(self) -> float:
        """Replans por passo registado pelo sistema de eventos."""
        if self._total_steps <= 0:
            return 0.0
        return self.replan_count / self._total_steps

    @property
    def total_steps(self) -> int:
        """Passos registados pela Engine via add_steps().

        Nota: para o CSV experimental, o runner usa preferencialmente
        Engine.get_stats()["total_steps"], porque esse valor vem diretamente
        de Robot.steps_taken e inclui também movimentos manuais de yield.
        Este campo é mantido para auditoria e compatibilidade.
        """
        return self._total_steps

    @property
    def average_steps_per_robot(self) -> float:
        if self._num_robots <= 0:
            return 0.0
        return self._total_steps / self._num_robots

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            # Metadados de execução
            "planner":                    self._planner,
            "seed":                       self._seed,
            "num_robots":                 self._num_robots,
            # Tempo / conclusão
            "makespan":                   self.makespan,
            "average_completion_time":    self.average_completion_time,
            "success_rate":               self.success_rate,
            "robots_completed":           self.robots_completed,
            "throughput":                 self.throughput,
            "metrics_total_steps":         self.total_steps,
            "metrics_average_steps_per_robot": self.average_steps_per_robot,
            # Eficiência / conflito
            "collision_count":            self.collision_count,
            "replan_count":               self.replan_count,
            "replan_rate":                self.replan_rate,
            "wait_count":                 self.wait_count,
            "avg_blocked_ticks_per_robot": self.avg_blocked_ticks_per_robot,
            "max_consecutive_blocked":    self._max_consecutive_blocked,
        }