"""
Ações possíveis na resolução de um conflito.

Estas ações representam as decisões que um resolver (atualmente no-op,
futuramente um QAgent) pode tomar perante um conflito detetado pelo Engine.

Nesta fase NÃO são consumidas pelo Engine — servem apenas como contrato
estável para a futura integração com Q-learning.
"""

from __future__ import annotations

from enum import Enum


class ConflictAction(str, Enum):
    WAIT    = "wait"     # robô fica parado este tick
    YIELD   = "yield"    # robô cede passagem (passo lateral)
    REPLAN  = "replan"   # robô recalcula caminho