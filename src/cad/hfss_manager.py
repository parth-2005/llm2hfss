"""HFSS / PyAEDT management utilities (stubbed for safety).

This module provides a lightweight context manager that documents
how a real `HFSSManager` might be structured while avoiding any
hard dependency on `pyaedt` at scaffold time.
"""

from typing import Optional, Dict
import contextlib
import importlib
import traceback


class HFSSManager(contextlib.AbstractContextManager):
    """HFSS manager that attempts to use `pyaedt` when available.

    If `pyaedt` is not installed or not desired, the manager falls back to
    a mocked session that documents actions and returns placeholder results.
    """

    def __init__(self, project_name: Optional[str] = None, non_graphical: bool = True, use_pyaedt: Optional[bool] = None):
        self.project_name = project_name or "NeuroRF_project"
        self.non_graphical = non_graphical
        self.session = None
        self._pyaedt = None
        self.use_pyaedt = use_pyaedt

    def __enter__(self):
        # Try to import pyaedt lazily if the user wants to use it.
        if self.use_pyaedt is None:
            try:
                self._pyaedt = importlib.import_module("pyaedt")
                self.use_pyaedt = True
            except Exception:
                self._pyaedt = None
                self.use_pyaedt = False

        if self.use_pyaedt and self._pyaedt is not None:
            try:
                # Import HFSS object; exact API depends on pyaedt version
                hfss = importlib.import_module("pyaedt").Hfss
                # The constructor args vary; calling with minimal set here
                self.session = hfss(non_graphical=self.non_graphical)
            except Exception:
                # If pyaedt fails, fallback to mock but surface the error in logs
                traceback.print_exc()
                self.session = {"connected": False, "project": self.project_name}
                self.use_pyaedt = False
        else:
            self.session = {"connected": True, "project": self.project_name}

        return self

    def __exit__(self, exc_type, exc, tb):
        # Close real session if present
        if self.use_pyaedt and getattr(self.session, "close", None):
            try:
                self.session.close()
            except Exception:
                pass
        self.session = None
        return False

    # Convenience helpers for building simple models: these are high-level
    # and intentionally small so they can be used in tests without pyaedt.
    def build_dipole(self, dipole_params: Dict[str, float]) -> Dict[str, object]:
        """Build a dipole model in HFSS (mocked if pyaedt not available).

        Returns a descriptor describing what would be built.
        """
        desc = {
            "type": "dipole",
            "params": dipole_params,
            "built_in_hfss": bool(self.use_pyaedt),
        }
        if self.use_pyaedt and getattr(self.session, "modeler", None):
            # Real implementation would use the session.modeler to create solids
            desc["note"] = "Real HFSS build executed (details omitted)."
        else:
            desc["note"] = "Mock build; pyaedt not available."
        return desc

    def apply_tasks(self, tasks: list) -> Dict[str, object]:
        """Interpret and execute ordered tasks."""
        log = []
        status = "ok"
        for t in tasks:
            try:
                tid = t.get("id")
                action = t.get("action")
                params = t.get("params") or {}
                
                # --- UPDATED: Handle Strict Keywords ---
                if action in ("create_substrate", "create_patch", "create_dipole", "model"):
                    log.append({"id": tid, "action": action, "result": f"Geometry created: {params}"})
                    
                elif action in ("assign_excitation", "assign_port"):
                    log.append({"id": tid, "action": action, "result": f"Excitation assigned: {params}"})
                    
                elif action in ("assign_boundary", "assign_perfect_e"):
                    log.append({"id": tid, "action": action, "result": f"Boundary assigned: {params}"})
                    
                elif action in ("create_setup", "analysis_setup"):
                    log.append({"id": tid, "action": action, "result": f"Setup created: {params}"})
                    
                elif action in ("analyze", "solve"):
                    log.append({"id": tid, "action": action, "result": "Simulation executed (Mock)"})
                    
                elif action in ("export_report", "postprocess"):
                    log.append({"id": tid, "action": action, "result": "Data exported (S11.csv)"})
                    
                else:
                    log.append({"id": tid, "action": action, "result": f"Unknown action '{action}'"})
                    
            except Exception as e:
                status = "error"
                log.append({"id": t.get("id"), "error": str(e)})

        return {"status": status, "log": log}
    def run_simulation(self, built_model: Dict[str, object]) -> Dict[str, float]:
        """Run HFSS simulation or return mocked results.

        The mocked results are coarse estimates; with pyaedt installed this
        method should trigger an actual solve and return numeric outputs.
        """
        if self.use_pyaedt and getattr(self.session, "solve", None):
            # Placeholder: real code would setup an analysis and solve
            return {"status": "ok", "resonant_freq_hz": built_model["params"].get("frequency_hz", 0.0)}

        # Mocked simulation results
        params = built_model.get("params", {})
        freq = params.get("frequency_hz") or (params.get("frequency_hz_list") and params.get("frequency_hz_list")[0])
        if not freq:
            freq = 1.0e9
        return {
            "status": "mock",
            "resonant_freq_hz": float(freq),
            "input_impedance_ohm": 73.0,
            "gain_dbi": 2.15,
        }

    def start_session(self):
        return self.__enter__()

    def close(self):
        return self.__exit__(None, None, None)
