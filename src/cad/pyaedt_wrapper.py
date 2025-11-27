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
                    project=self.project_name, 
                    non_graphical=self.non_graphical,
                    new_desktop=False, 
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
        if self.mock: return {"name": "dipole_mock", "status": "mocked"}

        try:
            L_arm = params.get("length_m", 0.05) / 2.0
            gap = L_arm * 0.05
            radius = params.get("radius_m", 0.001)
            
            l_mm = f"{L_arm * 1000:.4f}mm"
            g_mm = f"{gap * 1000:.4f}mm"
            r_mm = f"{radius * 1000:.4f}mm"

            self.app.modeler.create_cylinder(orientation="Z", origin=[0, 0, f"{g_mm}/2"], radius=r_mm, height=l_mm, name="Dipole_Top", matname="copper")
            self.app.modeler.create_cylinder(orientation="Z", origin=[0, 0, f"-{g_mm}/2 - {l_mm}"], radius=r_mm, height=l_mm, name="Dipole_Bottom", matname="copper")
            
            # Port Sheet
            port_sheet = self.app.modeler.create_rectangle(
                orientation="Y", origin=[f"-{r_mm}", 0, f"-{g_mm}/2"], sizes=[f"2*{r_mm}", g_mm], name="Port_Sheet"
            )
            self._safe_assign_port(port_sheet.name)
            
            return {"name": "Dipole", "status": "drawn"}
        except Exception as e:
            print(f"Error drawing dipole: {e}")
            return {"status": "error"}

    def add_patch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draws a Microstrip Patch Antenna."""
        if self.mock: return {"name": "patch_mock", "status": "mocked"}

        try:
            W = params.get("width_m", 0.03) * 1000
            L = params.get("length_m", 0.03) * 1000
            h = 1.6 # Substrate height mm
            
            # Substrate
            self.app.modeler.create_box(
                origin=[f"-{W}mm", f"-{L}mm", "0mm"],
                sizes=[f"{2*W}mm", f"{2*L}mm", f"{h}mm"],
                name="Substrate", material="FR4_epoxy"
            )
            
            # Ground
            gnd = self.app.modeler.create_rectangle(
                orientation="Z", origin=[f"-{W}mm", f"-{L}mm", "0mm"], sizes=[f"{2*W}mm", f"{2*L}mm"], name="Ground"
            )
            # Check if boundary exists before creating
            if "PerfE_Gnd" not in self.app.boundaries:
                self.app.assign_perfect_e(gnd, name="PerfE_Gnd")

            # Patch
            patch = self.app.modeler.create_rectangle(
                orientation="Z", origin=[f"-{W/2}mm", f"-{L/2}mm", f"{h}mm"], sizes=[f"{W}mm", f"{L}mm"], name="Patch"
            )
            # Check if boundary exists before creating
            if "PerfE_Patch" not in self.app.boundaries:
                self.app.assign_perfect_e(patch, name="PerfE_Patch")
            
            # Feed Port
            feed = self.app.modeler.create_rectangle(
                orientation="Y", origin=["0mm", f"-{L/2}mm", "0mm"], sizes=["2mm", f"{h}mm"], name="Feed_Port"
            )
            self._safe_assign_port(feed.name)

            return {"name": "Patch", "status": "drawn"}
        except Exception as e:
            print(f"Error drawing patch: {e}")
            return {"status": "error"}

    def _safe_assign_port(self, sheet_name):
        """Helper to handle API differences in port creation."""
        try:
            # Modern PyAEDT
            if hasattr(self.app, "create_lumped_port"):
                self.app.create_lumped_port(sheet_name, axisdir="Z", impedance=50)
            # Older PyAEDT
            elif hasattr(self.app, "create_lumped_port_to_sheet"):
                self.app.create_lumped_port_to_sheet(sheet_name, axisdir="Z", impedance=50)
            else:
                print("⚠️ Warning: Could not find port creation method.")
        except Exception as e:
            print(f"⚠️ Port assignment warning: {e}")

    def assign_port(self, target, params):
        return {"status": "done"}

    def create_setup(self, name: str = "Setup1", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.mock: return {"setup": name}
        try:
            # Ensure name consistency
            if name in self.app.setup_names:
                 setup = self.app.get_setup(name)
            else:
                 setup = self.app.create_setup(name)
            
            freqs = params.get("frequency_hz_list", [1e9])
            center_ghz = freqs[0] / 1e9
            setup.props["Frequency"] = f"{center_ghz}GHz"
            
            # Create sweep
            # Using add_sweep if create_frequency_sweep isn't working as expected or for updates
            # But create_frequency_sweep is standard. Let's ensure the setup name is correct.
            self.app.create_frequency_sweep(
                setupname=name, unit="GHz",
                freqstart=center_ghz*0.8, freqstop=center_ghz*1.2, num_of_freq_points=11,
                sweepname="Sweep" # Explicitly naming the sweep
            )
            return {"setup": name, "status": "created"}
        except Exception as e:
            print(f"Error creating setup: {e}")
            return {"status": "error"}

    def analyze(self) -> Dict[str, Any]:
        if self.mock: return {"status": "mock_solved"}
        try:
            # Ensure we analyze the setup we just created
            self.app.analyze_setup("Setup1")
            return {"status": "solved"}
        except Exception as e:
            print(f"Error analyzing: {e}")
            return {"status": "error"}

    def export_report(self, report_name: str, target_path: str) -> Dict[str, Any]:
        if self.mock: return {"status": "mock_exported"}
        try:
            # Use standard report creation
            # Note: "Setup1 : Sweep" must match what create_setup made. 
            # If the sweep name is different, this fails.
            setup_sweep_name = "Setup1 : Sweep" 
            
            # Check if report already exists to avoid duplication error or handle updates
            if report_name not in self.app.post.plots:
                 self.app.post.create_report(
                    expressions="dB(S(1,1))", 
                    setup_sweep_name=setup_sweep_name, 
                    domain="Sweep",
                    plot_name=report_name
                )
            
            self.app.post.export_report_to_csv(project_dir=target_path, plot_name=report_name)
            return {"status": "exported"}
        except Exception as e:
            print(f"Export warning: {e}")
            return {"status": "error"}