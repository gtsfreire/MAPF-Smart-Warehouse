"""
Agente tabular de Q-learning para resolução local de conflitos.

Esta versão é deliberadamente conservadora.

O agente NÃO substitui o A*. O A* continua responsável por calcular caminhos.
O Engine continua responsável pelo replanning determinístico de segurança.
O Q-learning aprende apenas a escolher entre duas reações locais quando um robô
fica bloqueado:

    WAIT  - esperar este tick;
    YIELD - ceder passagem para uma célula lateral segura, se existir.

Porque remover REPLAN do espaço de ações?
-----------------------------------------
A versão anterior deixava o agente escolher REPLAN diretamente. Em cenários
com muitos robôs isso gerava "replan storms": milhares de replans, novos
conflitos e degradação forte face ao baseline determinístico. Como o Engine já
possui deadlock recovery seguro, deixar REPLAN como fallback do Engine é mais
estável e mais defensável academicamente: o Q-learning melhora a política local
WAIT/YIELD, sem destruir o planeamento global.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .actions import ConflictAction
from .base import ConflictResolver
from .context import ConflictContext


# Estado discreto compacto:
#   (dx_sign, dy_sign, intended_dx_sign, intended_dy_sign,
#    dist_bucket, blocked_bucket, congestion_bucket, at_goal_axis)
State = Tuple[int, int, int, int, int, int, int, int]

# Política conservadora: o agente só decide WAIT vs YIELD.
# REPLAN permanece no Enum porque o Engine o suporta, mas não é ação aprendida
# por defeito. O fallback determinístico do Engine continua a replanear após
# bloqueio persistente.
ACTIONS = (ConflictAction.WAIT, ConflictAction.YIELD)
ACTION_TO_INDEX = {action: i for i, action in enumerate(ACTIONS)}

# Defaults seguros: estado desconhecido espera primeiro. Isto replica o baseline
# determinístico em vez de arriscar yield/replan em estados fora da distribuição
# de treino. O Engine desbloqueia waits persistentes com replanning próprio.
DEFAULT_Q_VALUES = [0.05, 0.00]


EXPECTED_VERSION = 3
EXPECTED_POLICY = "wait_yield_safe"


def _sign(v: int) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _bucket_distance(d: int) -> int:
    """Discretiza a distância de Manhattan ao goal em poucos níveis."""
    if d <= 1:
        return 0
    if d <= 3:
        return 1
    if d <= 7:
        return 2
    if d <= 15:
        return 3
    return 4


def _bucket_blocked(b: int) -> int:
    if b <= 0:
        return 0
    if b <= 1:
        return 1
    if b <= 3:
        return 2
    return 3


def _bucket_congestion(n: int) -> int:
    """Quantos vizinhos imediatos estão ocupados/intencionados por outros."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    if n == 2:
        return 2
    return 3


def _normalise_values(values: Iterable[float], action_names: Iterable[str] | None = None) -> list[float]:
    """Converte Q-values antigas/novas para a política atual WAIT/YIELD.

    Isto permite carregar uma Q-table antiga com ações [wait, yield, replan]
    sem deixar REPLAN contaminar a avaliação atual. Apenas os valores das ações
    ainda existentes são aproveitados.
    """
    raw = [float(v) for v in values]
    names = list(action_names) if action_names is not None else [a.value for a in ACTIONS]

    mapped = dict(zip(names, raw))
    result = []
    for action in ACTIONS:
        result.append(float(mapped.get(action.value, DEFAULT_Q_VALUES[ACTION_TO_INDEX[action]])))
    return result


def encode_state(ctx: ConflictContext) -> State:
    """
    Mapeia um ConflictContext num estado discreto.

    Variáveis:
      - dx_sign/dy_sign: direção relativa ao goal;
      - intended_dx/intended_dy: direção do passo pretendido;
      - dist_bucket: distância de Manhattan ao goal;
      - blocked_bucket: tempo consecutivo bloqueado;
      - congestion_bucket: ocupação local em vizinhança 4;
      - at_goal_axis: se o robô já está alinhado em x/y com o objetivo.

    O estado continua pequeno, mas distingue melhor casos em que YIELD tira o
    robô do eixo correto versus casos em que esperar é mais seguro.
    """
    cx, cy = ctx.current_position
    ix, iy = ctx.intended_position
    gx, gy = ctx.goal

    dxs = _sign(gx - cx)
    dys = _sign(gy - cy)
    intended_dx = _sign(ix - cx)
    intended_dy = _sign(iy - cy)
    dist = abs(gx - cx) + abs(gy - cy)

    neighbors = {(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)}
    others_positions = set()
    for _, (cur, intended) in ctx.others.items():
        others_positions.add(cur)
        others_positions.add(intended)

    congestion = sum(1 for p in neighbors if p in others_positions)
    at_goal_axis = int(cx == gx) + int(cy == gy)

    return (
        dxs,
        dys,
        intended_dx,
        intended_dy,
        _bucket_distance(dist),
        _bucket_blocked(ctx.blocked_ticks),
        _bucket_congestion(congestion),
        at_goal_axis,
    )


class QLearningResolver(ConflictResolver):
    """
    Q-learning tabular ε-greedy.

    training=True:
        usa exploração ε-greedy e atualiza a Q-table.

    training=False:
        avaliação greedy, sem exploração e sem updates.

    A política é conservadora: WAIT/YIELD. Replanning fica como fallback do
    Engine, ativado quando o bloqueio persiste.
    """

    def __init__(
        self,
        alpha: float = 0.12,
        gamma: float = 0.85,
        epsilon: float = 0.20,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.997,
        seed: Optional[int] = None,
        training: bool = True,
        default_q_values: Optional[Iterable[float]] = None,
        min_yield_advantage: float = 1.0,
    ):
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_min = float(epsilon_min)
        self.epsilon_decay = float(epsilon_decay)
        self.training = bool(training)
        self.min_yield_advantage = float(min_yield_advantage)
        if not self.training:
            self.epsilon = 0.0

        defaults = list(default_q_values) if default_q_values is not None else list(DEFAULT_Q_VALUES)
        defaults = _normalise_values(defaults)
        if len(defaults) != len(ACTIONS):
            raise ValueError("default_q_values deve ter um valor por ação ativa.")
        self.default_q_values = [float(v) for v in defaults]

        self._rng = random.Random(seed)
        self.q: Dict[State, list[float]] = defaultdict(lambda: list(self.default_q_values))

        # Último (estado, ação) por robô para update no observe().
        self._last: Dict[int, Tuple[State, int]] = {}

        # Contadores para auditoria/relatório.
        self.decision_count: int = 0
        self.update_count: int = 0
        self.action_counts: Counter[str] = Counter()

    # ------------------------------------------------------------------
    # API do ConflictResolver
    # ------------------------------------------------------------------
    def decide(self, ctx: ConflictContext) -> ConflictAction:
        state = encode_state(ctx)

        allowed = self._allowed_action_indices(state)

        if self.training and self._rng.random() < self.epsilon:
            action_idx = self._rng.choice(allowed)
        else:
            action_idx = self._select_greedy_action(state, allowed)

        action = ACTIONS[action_idx]
        self._last[ctx.robot_id] = (state, action_idx)
        self.decision_count += 1
        self.action_counts[action.value] += 1
        return action

    def observe(
        self,
        ctx: ConflictContext,
        action: ConflictAction,
        reward: float = 0.0,
    ) -> None:
        """
        Atualização Q-learning standard:
            Q(s,a) <- Q(s,a) + α [ r + γ max_a' Q(s',a') - Q(s,a) ]

        O argumento `action` é mantido para cumprir a interface; a ação usada
        no update vem de `_last`, que corresponde à última decisão do robô.
        """
        if not self.training:
            return

        last = self._last.get(ctx.robot_id)
        if last is None:
            return

        prev_state, prev_action_idx = last
        next_state = encode_state(ctx)

        old_q = self.q[prev_state][prev_action_idx]
        future = max(self.q[next_state])
        new_q = old_q + self.alpha * (reward + self.gamma * future - old_q)
        self.q[prev_state][prev_action_idx] = new_q
        self.update_count += 1

    def reset(self) -> None:
        """Chamar no fim de cada episódio."""
        self._last.clear()
        if self.training and self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    def save_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        serialisable = {
            "version": EXPECTED_VERSION,
            "policy": EXPECTED_POLICY,
            "alpha": self.alpha,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "epsilon_min": self.epsilon_min,
            "epsilon_decay": self.epsilon_decay,
            "training": self.training,
            "min_yield_advantage": self.min_yield_advantage,
            "actions": [a.value for a in ACTIONS],
            "default_q_values": self.default_q_values,
            "decision_count": self.decision_count,
            "update_count": self.update_count,
            "action_counts": dict(self.action_counts),
            "q": {
                ",".join(str(x) for x in state): values
                for state, values in self.q.items()
            },
        }

        path.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load_json(
        cls,
        path: str | Path,
        training: bool = False,
        *,
        epsilon: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> "QLearningResolver":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))

        saved_actions = data.get("actions", [a.value for a in ACTIONS])
        is_current_policy = (
            data.get("version") == EXPECTED_VERSION
            and data.get("policy") == EXPECTED_POLICY
            and list(saved_actions) == [a.value for a in ACTIONS]
        )

        # Nunca herdar defaults de uma política antiga. A v2 tinha preferência
        # inicial por YIELD; com o estado v3 isso tornava estados desconhecidos
        # perigosamente agressivos. Para tabelas antigas usamos defaults seguros.
        if is_current_policy:
            defaults = _normalise_values(data.get("default_q_values", DEFAULT_Q_VALUES), saved_actions)
        else:
            defaults = list(DEFAULT_Q_VALUES)

        agent = cls(
            alpha=data.get("alpha", 0.12),
            gamma=data.get("gamma", 0.85),
            epsilon=data.get("epsilon", 0.0 if not training else 0.20) if epsilon is None else epsilon,
            epsilon_min=data.get("epsilon_min", 0.01),
            epsilon_decay=data.get("epsilon_decay", 0.997),
            seed=seed,
            training=training,
            default_q_values=defaults,
            min_yield_advantage=data.get("min_yield_advantage", 1.0),
        )

        # Em avaliação queremos sempre greedy.
        if not training:
            agent.epsilon = 0.0

        # Só carregamos Q-values se a tabela já tiver sido treinada com a
        # política atual. Q-tables antigas são aceites, mas ficam como política
        # segura por defeito e devem ser treinadas novamente.
        if is_current_policy:
            for state_str, values in data.get("q", {}).items():
                state = tuple(int(x) for x in state_str.split(","))
                if len(state) != 8:
                    continue
                agent.q[state] = _normalise_values(values, saved_actions)

        return agent

    # ------------------------------------------------------------------
    # Helpers / auditoria
    # ------------------------------------------------------------------
    def stats(self) -> dict:
        return {
            "q_states": len(self.q),
            "q_epsilon": self.epsilon,
            "q_training": self.training,
            "q_decisions": self.decision_count,
            "q_updates": self.update_count,
            "q_wait_actions": self.action_counts.get(ConflictAction.WAIT.value, 0),
            "q_yield_actions": self.action_counts.get(ConflictAction.YIELD.value, 0),
            "q_replan_actions": self.action_counts.get(ConflictAction.REPLAN.value, 0),
            "q_policy": EXPECTED_POLICY,
            "q_min_yield_advantage": self.min_yield_advantage,
        }

    def _allowed_action_indices(self, state: State) -> list[int]:
        """Máscara de segurança para evitar yields destrutivos.

        O agente só deve considerar YIELD quando faz sentido: não demasiado
        perto do goal e não num congestionamento extremo no primeiro bloqueio.
        Caso contrário, WAIT deixa o Engine aplicar o fallback determinístico
        caso o impasse persista.
        """
        dist_bucket = state[4]
        blocked_bucket = state[5]
        congestion_bucket = state[6]

        # Perto do goal, sair do caminho costuma ser pior do que esperar.
        if dist_bucket <= 1:
            return [ACTION_TO_INDEX[ConflictAction.WAIT]]

        # Em congestionamento local alto, yield no primeiro/segundo bloqueio
        # tende a empurrar o robô para outro conflito. Esperar é mais seguro.
        if congestion_bucket >= 2 and blocked_bucket <= 1:
            return [ACTION_TO_INDEX[ConflictAction.WAIT]]

        return [ACTION_TO_INDEX[ConflictAction.WAIT], ACTION_TO_INDEX[ConflictAction.YIELD]]

    def _select_greedy_action(self, state: State, allowed: list[int]) -> int:
        values = self.q[state]

        wait_idx = ACTION_TO_INDEX[ConflictAction.WAIT]
        yield_idx = ACTION_TO_INDEX[ConflictAction.YIELD]

        if yield_idx in allowed:
            # Guardrail principal: YIELD só vence se for claramente melhor.
            # Isto impede que diferenças pequenas/ruído estatístico degradem o
            # comportamento face ao baseline determinístico.
            if values[yield_idx] >= values[wait_idx] + self.min_yield_advantage:
                return yield_idx

        return wait_idx

    def _argmax(self, values: list[float]) -> int:
        """Mantido por compatibilidade interna; usa desempate conservador."""
        best_v = max(values)
        for i, v in enumerate(values):
            if v == best_v:
                return i
        return 0
