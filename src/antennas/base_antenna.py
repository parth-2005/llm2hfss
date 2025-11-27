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

    # New HFSS-related hooks -------------------------------------------------
    @abstractmethod
    def build_in_hfss(self, session) -> Dict[str, object]:
        """Build the antenna geometry into an HFSS/PyAEDT session.

        The `session` is expected to be an object provided by the
        `pyaedt_wrapper` (or a compatible mock). Implementations should
        create solids/objects and return a descriptor that identifies
        created items (IDs, names) and any metadata required for later
        steps.
        """

    @abstractmethod
    def assign_excitations(self, session) -> Dict[str, object]:
        """Assign feeds/ports/boundaries inside the HFSS session.

        Return a small descriptor of the assigned excitations.
        """

    @abstractmethod
    def postprocess(self, session) -> Dict[str, float]:
        """Extract results from the HFSS session after simulation.

        Return a dictionary of numeric results (resonant frequency,
        impedance, gain, etc.). For mock sessions this may call
        `session.export_report` or read the session.log.
        """
