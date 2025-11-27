"""Microstrip patch antenna model."""
from typing import Dict, Any
from .base_antenna import BaseAntenna
from utils import physics

class PatchAntenna(BaseAntenna):
    def __init__(self, frequency_hz: float, eps_r: float = 4.4):
        self.frequency_hz = float(frequency_hz)
        self.eps_r = float(eps_r)

    def design_params(self) -> Dict[str, float]:
        c = physics.c
        fr = self.frequency_hz
        # Width (W)
        W = c / (2 * fr) * (2 / (1 + self.eps_r)) ** 0.5
        # Length (L) - simplified approximation
        L = W * 0.95 
        return {"frequency_hz": fr, "eps_r": self.eps_r, "width_m": W, "length_m": L}

    def simulate(self) -> Dict[str, float]:
        params = self.design_params()
        return {"resonant_freq_hz": params["frequency_hz"], "bandwidth_pct": 2.0}

    # HFSS integration hooks
    def build_in_hfss(self, session: Any) -> Dict[str, object]:
        params = self.design_params()
        # This calls the method we restored in pyaedt_wrapper.py
        desc = session.add_patch(params)
        return {"antenna": "patch", "descriptor": desc}

    def assign_excitations(self, session: Any) -> Dict[str, object]:
        # Excitations are currently handled inside add_patch for atomic correctness
        return {"status": "done_in_build"}

    def postprocess(self, session: Any) -> Dict[str, float]:
        if not getattr(session, "mock", True):
            try:
                session.export_report("S11", "patch_S11.csv")
            except Exception:
                pass
        return self.simulate()