"""Abstract base class for antennas."""

from abc import ABC, abstractmethod
from typing import Dict


class BaseAntenna(ABC):
    """Abstract antenna interface for design and simulation.

    Concrete implementations should provide `design_params` and
    a lightweight `simulate` method that returns a dict with
    numeric results. These are symbolic placeholders for now.
    """

    @abstractmethod
    def design_params(self) -> Dict[str, float]:
        """Return design parameters (dimensions, resonant frequency, etc.)."""

    @abstractmethod
    def simulate(self) -> Dict[str, float]:
        """Return a minimal simulation result (e.g., resonant_freq, impedance)."""
