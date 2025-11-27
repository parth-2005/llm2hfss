"""Agent orchestrator for Neuro-Symbolic COT -> HFSS workflow."""

from typing import Dict, Any, List
from .parser import Parser
from .llm_client import LLMClient
from src.antennas.dipole import Dipole
from src.antennas.patch import PatchAntenna
from src.cad.hfss_manager import HFSSManager
import os
import dotenv
import json

dotenv.load_dotenv()

class Agent:
    def __init__(self, provider: str = "gemini", model: str = "gemini-2.0-flash-lite"):
        self.parser = Parser()
        self.llm = LLMClient(provider=provider, model=model)

    def run_design(self, user_request: str, request_id: str = None, use_pyaedt: bool = None) -> Dict[str, Any]:
        """Main agent entry: returns a structured result dict."""
        
        # 1. Parsing & Prompting
        spec = self.parser.parse(user_request)
        cot_prompt = self.parser.build_cot_prompt(spec, request_id=request_id)

        # 2. LLM Generation
        parsed = self.llm.generate_json(cot_prompt)

        # --- SAFETY FIX: Handle List vs Dict output ---
        if isinstance(parsed, list):
            print("⚠️ Warning: LLM returned a list. Unwrapping first item...")
            if len(parsed) > 0 and isinstance(parsed[0], dict):
                parsed = parsed[0]
            else:
                # Fallback if list is empty or weird
                parsed = {
                    "antenna_type": spec.get("antenna_type") or "dipole",
                    "frequencies_hz": spec.get("frequencies_hz") or [2.4e9],
                    "tasks": []
                }

        # 3. Validation & Normalization
        antenna_type = parsed.get("antenna_type") or spec.get("antenna_type") or "dipole"
        freqs = parsed.get("frequencies_hz") or spec.get("frequencies_hz") or []
        tasks = parsed.get("tasks")

        # Ensure we have at least defaults if LLM failed completely
        if not freqs: freqs = [2.4e9]
        
        # 4. Build Antenna Objects
        if isinstance(freqs, (int, float)):
            freqs = [float(freqs)]

        antennas = []
        for f in freqs:
            if not f: continue
            if "patch" in str(antenna_type).lower():
                antennas.append(PatchAntenna(f))
            else:
                antennas.append(Dipole(f))

        results = {"request": user_request, "spec_from_llm": parsed, "antennas": []}

        # 5. HFSS Execution
        if use_pyaedt is None:
            use_pyaedt = os.environ.get("USE_PYAEDT", "false").lower() in ("1", "true", "yes")

        with HFSSManager(non_graphical=False, use_pyaedt=use_pyaedt) as hfss:
            for ant in antennas:
                # Calculate Physics
                params = ant.design_params()
                
                # Execute Tasks (Symbolic -> CAD)
                if tasks:
                    print(f"⚙️ Executing {len(tasks)} tasks from LLM...")
                    task_exec = hfss.apply_tasks(tasks)
                else:
                    # Fallback: Just build it if no tasks provided
                    print("⚠️ No tasks in JSON. Running default build.")
                    hfss.run_antenna_workflow(ant)
                    task_exec = {"status": "default_workflow"}

                results["antennas"].append({
                    "type": ant.__class__.__name__,
                    "params": params,
                    "task_execution": task_exec
                })

        return results