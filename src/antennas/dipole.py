"""Simple dipole antenna model."""

from typing import Dict, List, Union
from .base_antenna import BaseAntenna
from utils import physics
from typing import Any


class Dipole(BaseAntenna):
    """A more explicit half-wave dipole design with correction factors.

    Formulas used:
    - wavelength = c / f
    - physical_length ~= (wavelength / 2) * k  (k is end-effect correction ~0.95)

    The class exposes helpers to create a dipole from a frequency or from
    an LLM-produced spec.
    """

    END_EFFECT_CORRECTION = 0.95

    def __init__(self, frequency_hz: float, correction: float = None):
        self.frequency_hz = float(frequency_hz)
        self.correction = float(correction) if correction is not None else self.END_EFFECT_CORRECTION

    @classmethod
    def from_spec(cls, spec: Union[Dict, float]) -> Union['Dipole', List['Dipole']]:
        """Create Dipole(s) from a spec dict or a single frequency value.

        Accepts:
        - float (frequency in Hz)
        - dict with key 'frequencies_hz' -> list of floats
        """
        if isinstance(spec, (int, float)):
            return cls(float(spec))
        if isinstance(spec, dict):
            freqs = spec.get("frequencies_hz") or []
            if not freqs and spec.get("frequency_hz"):
                freqs = [spec.get("frequency_hz")]
            if len(freqs) == 1:
                return cls(freqs[0])
            return [cls(f) for f in freqs]
        raise TypeError("Unsupported spec for Dipole.from_spec")

    def design_params(self) -> Dict[str, float]:
        wavelength = physics.c / self.frequency_hz
        length = wavelength / 2.0 * self.correction
        # approximate dipole radius/diameter for feeding considerations
        radius = wavelength * 0.005
        return {
            "frequency_hz": self.frequency_hz,
            "wavelength_m": wavelength,
            "length_m": length,
            "radius_m": radius,
            "correction": self.correction,
        }

    def simulate(self) -> Dict[str, float]:
        params = self.design_params()
        # Symbolic simulation results; a real HFSS run will replace these
        return {
            "resonant_freq_hz": params["frequency_hz"],
            "input_impedance_ohm": 73.0,
            "estimated_gain_dbi": 2.15,
        }

    # HFSS integration hooks -------------------------------------------------
    def build_in_hfss(self, session: Any) -> Dict[str, object]:
        params = self.design_params()
        # Delegate the geometry creation to the session wrapper
        desc = session.add_dipole(params)
        return {"antenna": "dipole", "descriptor": desc}

    def assign_excitations(self, session: Any) -> Dict[str, object]:
        # For a dipole we typically assign a single port at the feed gap
        params = {"type": "lumped_port", "impedance_ohm": 50}
        # session.assign_port accepts a target descriptor and params
        built = getattr(session, "log", []) and session.log[-1] or {}
        port = session.assign_port(built, params)
        return {"ports": [port]}

    def postprocess(self, session: Any) -> Dict[str, float]:
        # In mock mode, return quick symbolic results; real mode would
        # export or query the solution. We attempt to use an exported
        # report if present, otherwise fall back to the lightweight simulate().
        if not getattr(session, "mock", True):
            # A real implementation would parse exported files or use the API
            try:
                session.export_report("S11", "S11.csv")
            except Exception:
                pass
        # Fall back to the quick local estimate
        return self.simulate()
