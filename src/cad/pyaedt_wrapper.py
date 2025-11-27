"""Wrapper around PyAEDT / HFSS to centralize session actions."""

from typing import Optional, Dict, Any, List
import importlib
import traceback

class PyAedtSession:
    """Context manager for a pyaedt HFSS session."""

    def __init__(self, project_name: Optional[str] = None, non_graphical: bool = False, use_pyaedt: Optional[bool] = None):
        self.project_name = project_name or "NeuroRF_Project"
        self.non_graphical = non_graphical
        self.use_pyaedt = use_pyaedt
        self.app = None
        self.mock = True
        self.log: List[Dict[str, Any]] = []

        # Lazy import check
        if self.use_pyaedt is None:
            try:
                self._pyaedt = importlib.import_module("ansys.aedt.core")
                self.use_pyaedt = True
            except Exception:
                self._pyaedt = None
                self.use_pyaedt = False
        elif self.use_pyaedt:
             try:
                self._pyaedt = importlib.import_module("ansys.aedt.core")
             except ImportError:
                 print("PyAEDT not found despite use_pyaedt=True")
                 self.use_pyaedt = False

    def __enter__(self):
        if self.use_pyaedt and self._pyaedt is not None:
            try:
                print(f"🔌 Connecting to HFSS (Project: {self.project_name})...")
                self.app = self._pyaedt.Hfss(
                    projectname=self.project_name,
                    non_graphical=self.non_graphical,
                    new_desktop_session=False,
                    close_on_exit=False
                )
                self.mock = False
                print("✅ HFSS Connected.")
            except Exception as e:
                print(f"❌ Connection Failed: {e}")
                self.app = None
                self.mock = True
        else:
            print("⚠️ Using Mock Session (No Hardware Connection)")
            self.app = None
            self.mock = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.mock and self.app:
            try:
                self.app.save_project()
            except Exception:
                pass
        return False

    # ---- Geometry & Operations ------------------------------------------------
    def add_dipole(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draws a Dipole Antenna."""
        if self.mock:
            return {"name": "dipole_mock", "status": "mocked"}

        try:
            # 1. Parse Dimensions
            L_arm = params.get("length_m", 0.05) / 2.0
            gap = L_arm * 0.05
            radius = params.get("radius_m", 0.001)
            
            # Convert to mm string for HFSS
            l_mm = f"{L_arm * 1000:.4f}mm"
            g_mm = f"{gap * 1000:.4f}mm"
            r_mm = f"{radius * 1000:.4f}mm"

            # 2. Draw Geometry
            self.app.modeler.create_cylinder(
                orientation="Z", origin=[0, 0, f"{g_mm}/2"], 
                radius=r_mm, height=l_mm, 
                name="Dipole_Top", matname="copper"
            )
            self.app.modeler.create_cylinder(
                orientation="Z", origin=[0, 0, f"-{g_mm}/2 - {l_mm}"], 
                radius=r_mm, height=l_mm, 
                name="Dipole_Bottom", matname="copper"
            )
            
            # 3. Create Port
            # Draw a sheet between the arms
            port_sheet = self.app.modeler.create_rectangle(
                position=[f"-{r_mm}", 0, f"-{g_mm}/2"],
                dimension_list=[f"2*{r_mm}", g_mm],
                name="Port_Sheet", axis="Y"
            )
            self.app.create_lumped_port_to_sheet(port_sheet.name, axisdir="Z", impedance=73)
            
            return {"name": "Dipole", "status": "drawn"}
        except Exception as e:
            print(f"Error drawing dipole: {e}")
            return {"status": "error"}

    def add_patch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draws a Microstrip Patch Antenna."""
        if self.mock:
            return {"name": "patch_mock", "status": "mocked"}

        try:
            # 1. Parse Dimensions
            W = params.get("width_m", 0.03) * 1000
            L = params.get("length_m", 0.03) * 1000
            h = 1.6 # Substrate height mm
            
            # 2. Draw Substrate
            self.app.modeler.create_box(
                position=[f"-{W}mm", f"-{L}mm", "0mm"],
                dimensions_list=[f"{2*W}mm", f"{2*L}mm", f"{h}mm"],
                name="Substrate", matname="FR4_epoxy"
            )
            
            # 3. Draw Ground
            gnd = self.app.modeler.create_rectangle(
                position=[f"-{W}mm", f"-{L}mm", "0mm"],
                dimension_list=[f"{2*W}mm", f"{2*L}mm"],
                name="Ground", axis="Z"
            )
            self.app.assign_perfect_e(gnd, name="PerfE_Gnd")

            # 4. Draw Patch
            patch = self.app.modeler.create_rectangle(
                position=[f"-{W/2}mm", f"-{L/2}mm", f"{h}mm"],
                dimension_list=[f"{W}mm", f"{L}mm"],
                name="Patch", axis="Z"
            )
            self.app.assign_perfect_e(patch, name="PerfE_Patch")
            
            # 5. Assign Port (Simplified Edge Port)
            # Create a sheet from ground to patch edge
            feed = self.app.modeler.create_rectangle(
                position=["0mm", f"-{L/2}mm", "0mm"],
                dimension_list=["2mm", f"{h}mm"], # 2mm wide feed
                name="Feed_Port", axis="Y"
            )
            self.app.create_lumped_port_to_sheet(feed.name, axisdir="Z", impedance=50)

            return {"name": "Patch", "status": "drawn"}
        except Exception as e:
            print(f"Error drawing patch: {e}")
            return {"status": "error"}

    def assign_port(self, target_descriptor: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder as ports are handled in add_dipole/patch for simplicity now."""
        return {"status": "included_in_build"}

    def create_setup(self, name: str = "Setup1", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.mock: return {"setup": name}
        try:
            setup = self.app.create_setup(name)
            # Default to center frequency if not provided list
            freqs = params.get("frequency_hz_list", [1e9])
            center_ghz = freqs[0] / 1e9
            setup.props["Frequency"] = f"{center_ghz}GHz"
            
            # Sweep
            self.app.create_frequency_sweep(
                setupname=name,
                unit="GHz",
                freqstart=center_ghz*0.5,
                freqstop=center_ghz*1.5,
                num_of_freq_points=51
            )
            return {"setup": name, "status": "created"}
        except Exception:
            return {"status": "error"}

    def analyze(self) -> Dict[str, Any]:
        if self.mock: return {"status": "mock_solved"}
        try:
            self.app.analyze_setup("Setup1")
            return {"status": "solved"}
        except Exception:
            return {"status": "error"}

    def export_report(self, report_name: str, target_path: str) -> Dict[str, Any]:
        if self.mock: return {"status": "mock_exported"}
        try:
            self.app.post.create_report("dB(S(1,1))")
            return {"status": "exported"}
        except Exception:
            return {"status": "error"}