"""Infraestrutura de métricas de simulação (recolha passiva via eventos)."""
from .events import Event, EventType
from .simulation_metrics import SimulationMetrics

__all__ = ["Event", "EventType", "SimulationMetrics"]