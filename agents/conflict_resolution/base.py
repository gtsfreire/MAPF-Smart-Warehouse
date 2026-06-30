"""
Interface abstrata para resolvers de conflito.

A arquitetura prevista é:

    A*  ->  Engine  ->  (conflito)  ->  ConflictResolver  ->  {WAIT, YIELD, REPLAN, PROCEED}  ->  Engine

Nesta fase, o Engine não invoca nenhum resolver: a resolução determinística
existente mantém-se intacta. Esta interface fica preparada para que um
QAgent (ou qualquer outra política) possa ser ligada no futuro através
de uma única chamada.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .actions import ConflictAction
from .context import ConflictContext


class ConflictResolver(ABC):
    """
    Política de decisão para conflitos.

    Implementações devem ser puras: receber um ConflictContext e devolver
    uma ConflictAction. Não devem mutar o Engine nem os robôs diretamente.
    """

    @abstractmethod
    def decide(self, ctx: ConflictContext) -> ConflictAction:
        ...

    def reset(self) -> None:
        """Hook opcional: reset entre episódios (útil para Q-learning)."""
        return None

    def observe(self, ctx: ConflictContext, action: ConflictAction, reward: float = 0.0) -> None:
        """
        Hook opcional para feedback de aprendizagem.

        No-op por defeito. Implementações de aprendizagem usarão isto para
        atualizar a sua Q-table / política.
        """
        return None