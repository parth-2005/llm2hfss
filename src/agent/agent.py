"""Agent orchestrator for Neuro-Symbolic COT -> HFSS workflow.

This module ties together `Parser`, `LLMClient`, antenna models and
the `HFSSManager`. It performs the following high-level steps:

- Parse the user's request to extract frequencies and simple hints.
- Build a COT prompt asking Gemini for step-by-step reasoning AND a
  final JSON specification (the LLM client will enforce JSON parsing).
- Map the resulting JSON spec into antenna classes (Dipole/Patch).
- Build the model via `HFSSManager` and run a simulated (mock or real)
  simulation, returning structured results.
"""

from typing import Dict, Any, List
from .parser import Parser
from .llm_client import LLMClient
from src.antennas.dipole import Dipole
from src.antennas.patch import PatchAntenna
from src.cad.hfss_manager import HFSSManager
import os
import dotenv

dotenv.load_dotenv()

class Agent:
    def __init__(self, provider: str = "gemini", model: str = "gemini-1.5"):
        self.parser = Parser()
        self.llm = LLMClient(provider=provider, model=model)

    def clear_state(self):
        # For this scaffold there is no persistent state; this is a placeholder
        # for the user's "clear LLM + COT + Neuro-Symbolic things" requirement.
        pass

    def run_design(self, user_request: str, request_id: str = None, use_pyaedt: bool = None) -> Dict[str, Any]:
        """Main agent entry: returns a structured result dict.

        This method will try to call the LLM and parse JSON. If the LLM
        is not available or the JSON parse fails, it falls back to a
        parser-driven flow using extracted frequencies.
        """
        self.clear_state()

        spec = self.parser.parse(user_request)
        cot_prompt = self.parser.build_cot_prompt(spec, request_id=request_id)

        # LLM -> JSON (no fallback). If the LLM is not available or the JSON
        # is malformed, propagate the exception to the caller — per design
        # we require the LLM to produce a final JSON spec including 'tasks'.
        parsed = self.llm.generate_json(cot_prompt)

        # Normalize parsed spec and enforce required fields
        antenna_type = parsed.get("antenna_type") or spec.get("antenna_type") or "dipole"
        freqs = parsed.get("frequencies_hz") or spec.get("frequencies_hz") or []
        tasks = parsed.get("tasks")

        if not isinstance(tasks, list) or len(tasks) == 0:
            raise ValueError("LLM output must include a non-empty 'tasks' array describing the ordered modelling workflow.")

        if isinstance(freqs, (int, float)):
            freqs = [float(freqs)]

        # Build antenna objects
        antennas = []
        for f in freqs or [parsed.get("frequency_hz")]:
            if not f:
                continue
            if "dipole" in antenna_type.lower():
                antennas.append(Dipole(f))
            elif "patch" in antenna_type.lower():
                antennas.append(PatchAntenna(f))
            else:
                antennas.append(Dipole(f))

        results = {"request": user_request, "spec_from_llm": parsed, "antennas": []}

        # Use HFSS manager to build and run simulations
        # Determine use_pyaedt from env if not provided
        if use_pyaedt is None:
            use_pyaedt = os.environ.get("USE_PYAEDT", "false").lower() in ("1", "true", "yes")

        with HFSSManager(non_graphical=True, use_pyaedt=use_pyaedt) as hfss:
            for ant in antennas:
                params = ant.design_params()
                # Attach antenna-specific params into the tasks' params where appropriate
                tasks_for_model = []
                for t in tasks:
                    t_copy = dict(t)
                    # Merge frequency or geometry params into model/analysis tasks
                    if t_copy.get("action") in ("create_geometry", "model"):
                        t_copy.setdefault("params", {}).update({"geometry": params})
                    if t_copy.get("action") in ("setup_analysis", "analysis_setup"):
                        t_copy.setdefault("params", {}).update({"frequency_hz_list": freqs})
                    tasks_for_model.append(t_copy)

                # Build model descriptor
                built = hfss.build_dipole(params) if isinstance(ant, Dipole) else hfss.build_dipole(params)
                # Apply tasks (mock or real)
                task_exec = hfss.apply_tasks(tasks_for_model)
                # Run final simulation (could be triggered by 'solve' task above)
                sim = hfss.run_simulation(built)
                results["antennas"].append({
                    "type": ant.__class__.__name__,
                    "params": params,
                    "built": built,
                    "task_execution": task_exec,
                    "simulation": sim,
                })

        return results
