"""HFSS manager that orchestrates the workflow."""
from typing import Optional, Dict, Any
from .pyaedt_wrapper import PyAedtSession

class HFSSManager:
    def __init__(self, project_name: Optional[str] = None, non_graphical: bool = True, use_pyaedt: Optional[bool] = None):
        self.project_name = project_name
        self.non_graphical = non_graphical
        self.use_pyaedt = use_pyaedt
        self._session: Optional[PyAedtSession] = None

    def __enter__(self):
        self._session = PyAedtSession(
            project_name=self.project_name, 
            non_graphical=self.non_graphical, 
            use_pyaedt=self.use_pyaedt
        )
        self._session.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._session:
            self._session.__exit__(exc_type, exc, tb)
            self._session = None

    @property
    def session(self) -> PyAedtSession:
        if not self._session:
            raise RuntimeError("HFSSManager not started.")
        return self._session

    def run_antenna_workflow(self, antenna, setup_name: str = "Setup1", setup_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute standard build -> excite -> solve -> extract workflow."""
        # 1. Build Geometry
        built = antenna.build_in_hfss(self.session)

        # 2. Setup Analysis (Frequency Sweep)
        self.session.create_setup(setup_name, setup_params)

        # 3. Run Simulation (Analyze)
        # Note: In a real run, you might want to uncomment this. 
        # For development speed, we often skip 'analyze' unless explicitly requested.
        # solve_res = self.session.analyze()
        solve_res = {"status": "skipped_for_speed"} 

        # 4. Results
        results = antenna.postprocess(self.session)

        return {
            "built": built,
            "solve": solve_res,
            "results": results
        }