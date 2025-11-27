"""Microstrip patch antenna (very simple model)."""

from typing import Dict
from .base_antenna import BaseAntenna
from utils import physics


class PatchAntenna(BaseAntenna):
    """Rudimentary rectangular patch model using a simplified formula.

    This is a symbolic implementation intended for examples and tests.
    """

    def __init__(self, frequency_hz: float, eps_r: float = 4.4):
        self.frequency_hz = float(frequency_hz)
        self.eps_r = float(eps_r)

    def design_params(self) -> Dict[str, float]:
        c = physics.c
        fr = self.frequency_hz
        # Approximate patch width (W) for dominant TM10 mode
        W = c / (2 * fr) * (2 / (1 + self.eps_r)) ** 0.5
        # Length is slightly shorter due to fringing; we keep it simple
        L = W * 0.95
        return {"frequency_hz": fr, "eps_r": self.eps_r, "width_m": W, "length_m": L}

    def simulate(self) -> Dict[str, float]:
        params = self.design_params()
        return {"resonant_freq_hz": params["frequency_hz"], "bandwidth_pct": 2.0}
