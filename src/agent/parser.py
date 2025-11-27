"""Mock LLM parser for NeuroRF.

This module provides a tiny `Parser` class that imitates an LLM's
intent extraction without requiring external services.
"""

import json
from typing import Dict, List, Optional
import re


class Parser:
    """Parser that extracts intents and numeric specs from free text.

    - Extracts frequency tokens (supports Hz, kHz, MHz, GHz).
    - Produces a structured spec suitable for the antenna classes.
    - Provides a helper to produce a chain-of-thought (COT) prompt
      to send to an LLM like Gemini (the actual LLM call is handled
      by `src.agent.llm_client`).
    """

    FREQ_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ghz|mhz|khz|hz)\b", re.IGNORECASE)

    def parse(self, prompt: str) -> Dict[str, object]:
        """Parse user text and return a structured spec.

        Examples:
        - "Make an antenna for 2.4GHz and 5 GHz"
        -> {'intent': 'design_antenna', 'frequencies_hz': [2.4e9, 5e9]}

        The parser errs on the side of producing a structured output
        that downstream modules can consume even if no LLM is used.
        """

        text = (prompt or "").strip()
        freqs = self._extract_frequencies(text)
        intent = "design_antenna" if freqs else "design_antenna"
        # If user mentions 'dipole' or 'patch' try to capture preference
        antenna_type = None
        if "dipole" in text.lower():
            antenna_type = "dipole"
        if "patch" in text.lower() or "microstrip" in text.lower():
            antenna_type = "patch"

        return {
            "intent": intent,
            "raw": text,
            "antenna_type": antenna_type,
            "frequencies_hz": freqs,
        }

    def _extract_frequencies(self, text: str) -> List[float]:
        freqs: List[float] = []
        for m in self.FREQ_RE.finditer(text):
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit == "ghz":
                freqs.append(val * 1e9)
            elif unit == "mhz":
                freqs.append(val * 1e6)
            elif unit == "khz":
                freqs.append(val * 1e3)
            else:
                freqs.append(val)
        return freqs

    def build_cot_prompt(self, spec: Dict[str, object], request_id: Optional[str] = None) -> str:
        """Create a Chain-of-Thought (COT) prompt to send to Gemini.
        
        UPGRADE: Enforces strict action keywords so the Python code can execute them.
        """
        
        # Define the allowed vocabulary for the "Hands" (Python)
        allowed_actions = [
            "create_substrate",   # Draw the dielectric
            "create_patch",       # Draw the metal radiator
            "create_dipole",      # Draw wires
            "assign_excitation",  # Add lumped port / wave port
            "assign_boundary",    # Radiation / PEC / FiniteCond
            "create_setup",       # Frequency sweep configuration
            "analyze",            # Run simulation
            "export_report"       # S11, Gain plot
        ]

        lines = [
            "ROLE: You are a Senior RF Engineer and Simulation Architect.",
            "TASK: Analyze the user request and generate a structured simulation plan.",
            "",
            "### STEP 1: PHYSICS REASONING (Chain of Thought)",
            "Briefly calculate key parameters:",
            "- Target Frequency (f0)",
            "- Wavelength (lambda = c/f0)",
            "- Estimated Dimensions (e.g., L ~ 0.49*lambda for patch)",
            "",
            "### STEP 2: SIMULATION PLAN (JSON)",
            "Output a JSON object with these keys:",
            "  - 'antenna_type': String ('patch' or 'dipole')",
            "  - 'frequencies_hz': [float]",
            "  - 'tasks': A list of execution steps. Each step MUST look like:",
            "    {",
            "      'id': <int>,",
            "      'action': <STRICT_KEYWORD>,",
            "      'params': { <parameter_name>: <numeric_value_or_string> }",
            "    }",
            "",
            "### CONSTRAINTS",
            f"1. The 'action' field MUST be one of: {json.dumps(allowed_actions)}.",
            "2. All dimensions must be in 'mm'. All frequencies in 'Hz'.",
            "3. Do not invent new actions. Map complex ideas to these primitives.",
            "",
            f"USER REQUEST: \"{spec.get('raw')}\"",
            "",
            "RESPONSE (JSON ONLY):"
        ]
        
        if request_id:
            lines.insert(0, f"Request-ID: {request_id}")
            
        return "\n".join(lines)