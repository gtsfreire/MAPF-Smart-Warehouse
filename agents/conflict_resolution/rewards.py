"""
Função de recompensa do Q-learning.

Esta versão acompanha a política conservadora WAIT/YIELD:
  - REPLAN deixou de ser ação aprendida; o Engine faz replanning como fallback;
  - WAIT não deve ser demasiado penalizado, porque muitas vezes é a ação mais
    segura em MAPF;
  - YIELD só deve ser recompensado quando gera progresso ou desbloqueia sem
    colisão; se afastar o robô do objetivo, é penalizado.
"""
from __future__ import annotations

from .actions import ConflictAction
from .context import ConflictContext


def _manhattan(ctx: ConflictContext) -> int:
    return abs(ctx.current_position[0] - ctx.goal[0]) + abs(
        ctx.current_position[1] - ctx.goal[1]
    )


def default_reward(
    prev_ctx: ConflictContext,
    action: ConflictAction,
    new_ctx: ConflictContext,
    *,
    collided: bool = False,
    reached_goal: bool = False,
) -> float:
    """
    Recompensa simples e estável.

    Objetivo: aprender quando vale a pena ceder passagem. O baseline
    determinístico já sabe esperar e replanear em deadlock; portanto a reward
    não deve empurrar o agente para yield/replan agressivo.
    """
    if collided:
        return -150.0
    if reached_goal:
        return 80.0

    prev_dist = _manhattan(prev_ctx)
    new_dist = _manhattan(new_ctx)
    delta = prev_dist - new_dist

    reward = -0.10  # custo temporal leve por decisão

    if action is ConflictAction.WAIT:
        # WAIT é seguro. Penaliza pouco no início e mais se o bloqueio persistir.
        reward -= 0.25
        if new_ctx.blocked_ticks >= 2:
            reward -= 1.0
        if new_ctx.blocked_ticks >= 4:
            reward -= 3.0

    elif action is ConflictAction.YIELD:
        # YIELD só é bom se realmente produzir progresso. Se afastar do goal,
        # costuma criar mais congestionamento e replans futuros.
        if delta > 0:
            reward += 3.0
        elif delta == 0:
            reward -= 0.75
        else:
            reward -= 5.0

        if new_ctx.blocked_ticks > prev_ctx.blocked_ticks:
            reward -= 2.0

    elif action is ConflictAction.REPLAN:
        # Mantido por compatibilidade. A política v3 não escolhe REPLAN.
        reward -= 8.0

    # Pequena componente geral de progresso, independente da ação.
    if delta > 0:
        reward += 1.0
    elif delta < 0:
        reward -= 1.5

    return reward
