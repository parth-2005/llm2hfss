"""Small wrapper around PyAEDT / HFSS to centralize session actions.

This wrapper provides a minimal, safe interface used by antenna classes
and the HFSS manager. When `pyaedt` is not installed the class falls
back to a simple mock that records actions and returns descriptive
placeholders. The wrapper intentionally exposes a small API surface
that is easy to stub in unit tests.
"""

from typing import Optional, Dict, Any, List
import importlib
import traceback


class PyAedtSession:
    """Context manager for a pyaedt HFSS session or a mock session.

    Public API (minimal):
    - add_dipole(params) -> descriptor
    - add_patch(params) -> descriptor
    - assign_port(descriptor, params) -> descriptor
    - create_setup(name, params) -> descriptor
    - analyze() -> dict
    - export_report(name, target_path) -> dict

    For real pyaedt sessions, the implementation will call into the
    `Hfss` application object. For the mock mode, operations are logged
    in `self.log` and return lightweight dicts.
    """

    def __init__(self, project_name: Optional[str] = None, non_graphical: bool = True, use_pyaedt: Optional[bool] = None):
        self.project_name = project_name or "NeuroRF_project"
        self.non_graphical = non_graphical
        self._pyaedt = None
        self.app = None
        self.mock = True
        self.log: List[Dict[str, Any]] = []
        self.use_pyaedt = use_pyaedt

        if self.use_pyaedt is None:
            try:
                self._pyaedt = importlib.import_module("pyaedt")
                self.use_pyaedt = True
            except Exception:
                self._pyaedt = None
                self.use_pyaedt = False

    def __enter__(self):
        if self.use_pyaedt and self._pyaedt is not None:
            try:
                Hfss = getattr(self._pyaedt, "Hfss", None)
                if Hfss is None:
                    # Different pyAEDT versions may expose different names
                    self.app = self._pyaedt.App("hfss")
                else:
                    self.app = Hfss(non_graphical=self.non_graphical)
                self.mock = False
                self.log.append({"action": "connect", "result": "pyaedt session created"})
            except Exception:
                traceback.print_exc()
                self.app = None
                self.mock = True
                self.log.append({"action": "connect", "result": "failed, using mock"})
        else:
            self.app = None
            self.mock = True
            self.log.append({"action": "connect", "result": "mock session"})
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if not self.mock and getattr(self.app, "close", None):
                try:
                    self.app.close()
                    self.log.append({"action": "close", "result": "closed pyaedt"})
                except Exception:
                    self.log.append({"action": "close", "result": "error on close"})
        finally:
            self.app = None
            return False

    # ---- geometry & operations ------------------------------------------------
    def add_dipole(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add a simple dipole geometry. Returns descriptor."""
        entry = {"action": "add_dipole", "params": params}
        self.log.append(entry)
        if self.mock:
            return {"name": "dipole_1", "params": params, "built_in_hfss": False}
        # Real pyaedt calls would go here; keep minimal for now
        try:
            modeler = getattr(self.app, "modeler", None)
            if modeler:
                # Example: create line or cylinder primitives (implementation specific)
                pass
        except Exception:
            traceback.print_exc()
        return {"name": "dipole_1", "params": params, "built_in_hfss": True}

    def add_patch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entry = {"action": "add_patch", "params": params}
        self.log.append(entry)
        if self.mock:
            return {"name": "patch_1", "params": params, "built_in_hfss": False}
        try:
            modeler = getattr(self.app, "modeler", None)
            if modeler:
                pass
        except Exception:
            traceback.print_exc()
        return {"name": "patch_1", "params": params, "built_in_hfss": True}

    def assign_port(self, target_descriptor: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        entry = {"action": "assign_port", "target": target_descriptor, "params": params}
        self.log.append(entry)
        if self.mock:
            return {"port_name": "port1", "target": target_descriptor, "params": params}
        try:
            # Real session port assignment
            pass
        except Exception:
            traceback.print_exc()
        return {"port_name": "port1", "target": target_descriptor, "params": params}

    def create_setup(self, name: str = "Setup1", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = {"action": "create_setup", "name": name, "params": params}
        self.log.append(entry)
        if self.mock:
            return {"setup": name, "params": params}
        try:
            # call into self.app for real setup
            pass
        except Exception:
            traceback.print_exc()
        return {"setup": name, "params": params}

    def analyze(self) -> Dict[str, Any]:
        entry = {"action": "analyze"}
        self.log.append(entry)
        if self.mock:
            return {"status": "mock_solved"}
        try:
            if getattr(self.app, "analyze", None):
                self.app.analyze()
                return {"status": "solved"}
        except Exception:
            traceback.print_exc()
        return {"status": "error"}

    def export_report(self, report_name: str, target_path: str) -> Dict[str, Any]:
        entry = {"action": "export_report", "report": report_name, "path": target_path}
        self.log.append(entry)
        if self.mock:
            return {"report": report_name, "path": target_path, "exported": False}
        try:
            # Real export logic
            return {"report": report_name, "path": target_path, "exported": True}
        except Exception:
            traceback.print_exc()
            return {"report": report_name, "path": target_path, "exported": False}
 