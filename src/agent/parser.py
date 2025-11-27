"""Mock LLM parser for NeuroRF.

This module provides a tiny `Parser` class that imitates an LLM's
intent extraction without requiring external services.
"""

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

        The prompt requests step-by-step reasoning and asks the model to
        output final structured JSON containing antenna type and frequencies.
        """

        lines = [
            "You are an expert antenna engineer. Provide a very short chain-of-thought (one or two sentences),",
            "then output a final JSON object only. The JSON MUST contain the following keys:",
            "  - 'antenna_type' (string),",
            "  - 'frequencies_hz' (array of numbers),",
            "  - 'tasks' (an ordered array of task objects),",
            "    where each task object is { 'id': <int>, 'name': <string>, 'action': <string>, 'params': <object> }",
            "  - optional 'notes' string.",
            "",
            "The 'tasks' array should enumerate the full modelling workflow required for this problem. Typical tasks include:",
            "  1) model: create geometry with parameters",
            "  2) excitation: apply feed/excitation (port, type, amplitude, phase),",
            "  3) boundary_conditions: apply BCs (radiation, symmetry, perfect conductor),",
            "  4) analysis_setup: set frequency sweep / solver settings / convergence criteria,",
            "  5) solve: run analysis,",
            "  6) postprocess: extract S-parameters, fields, gain, and export results (publish).",
            "",
            f"User request: {spec.get('raw')}",
            "",
            "For each task provide an 'action' string the CAD manager can interpret and a 'params' object with relevant numeric parameters.",
            "Return ONLY the JSON (no markdown, no code fences).",
        ]
        if request_id:
            lines.insert(0, f"Request-ID: {request_id}")
        return "\n".join(lines)
