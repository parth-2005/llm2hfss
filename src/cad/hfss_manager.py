"""HFSS manager that orchestrates a simulation workflow using the
`pyaedt_wrapper.PyAedtSession` abstraction.

The manager's responsibility is deliberately small: open/close a
session and call antenna-provided hooks in a well-defined order.
Modeling, excitations and result extraction live on antenna classes.
"""

from typing import Optional, Dict, Any
from .pyaedt_wrapper import PyAedtSession


class HFSSManager:
    """Thin orchestrator for HFSS workflows.

    Example workflow used by `run_antenna_workflow`:
    1. open session
    2. antenna.build_in_hfss(session)
    3. antenna.assign_excitations(session)
    4. session.create_setup(...)
    5. session.analyze()
    6. antenna.postprocess(session)
    """

    def __init__(self, project_name: Optional[str] = None, non_graphical: bool = True, use_pyaedt: Optional[bool] = None):
        self.project_name = project_name
        self.non_graphical = non_graphical
        self.use_pyaedt = use_pyaedt
        self._session: Optional[PyAedtSession] = None

    def __enter__(self):
        self._session = PyAedtSession(project_name=self.project_name, non_graphical=self.non_graphical, use_pyaedt=self.use_pyaedt)
        self._session.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._session:
            try:
                self._session.__exit__(exc_type, exc, tb)
            finally:
                self._session = None

    @property
    def session(self) -> PyAedtSession:
        if not self._session:
            raise RuntimeError("HFSSManager: session not started; use 'with HFSSManager(...) as m:'")
        return self._session

    def run_antenna_workflow(self, antenna, setup_name: str = "Setup1", setup_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a standard build -> excite -> solve -> extract workflow.

        The `antenna` must implement the HFSS hooks defined in
        `BaseAntenna` (build_in_hfss, assign_excitations, postprocess).
        """
        # Build geometry
        built = antenna.build_in_hfss(self.session)

        # Assign excitations (feeds, ports, boundaries)
        excit = antenna.assign_excitations(self.session)

        # Create an analysis setup (manager-level convenience)
        self.session.create_setup(setup_name, setup_params)

        # Run solver
        solve_res = self.session.analyze()

        # Ask antenna to extract results
        results = antenna.postprocess(self.session)

        return {
            "built": built,
            "excitations": excit,
            "solve": solve_res,
            "results": results,
            "log": getattr(self.session, "log", []),
        }

    # Backwards-compatible small helpers
    def start_session(self):
        return self.__enter__()

    def close(self):
        return self.__exit__(None, None, None)
