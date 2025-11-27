# NeuroRF

Minimal scaffold for the NeuroRF project combining LLM "neuro" logic with symbolic antenna models and a CAD manager.

Quickstart

- Create a virtualenv and install dependencies from `requirements.txt` (optional).
- Run the smoke test:

```powershell
python .\main.py
```

Project layout

- `main.py` — Entry point (smoke test).
- `src/agent` — LLM-related parsing logic (mocked).
- `src/antennas` — Antenna ABC and concrete implementations.
- `src/cad` — CAD/HFSS manager stubs.
- `utils` — Materials and physics constants.

Gemini (LLM) integration

This scaffold includes a small LLM client adapter at `src/agent/llm_client.py` that
will attempt to use Google's Generative API (Gemini) if the `google-generativeai`
package is installed and `GOOGLE_API_KEY` is configured.

To enable Gemini support:

1. Install the optional library (if you plan to run real LLM calls):

```powershell
pip install google-generativeai
```

2. Set an API key in the environment (PowerShell example):

```powershell
$env:GOOGLE_API_KEY = 'YOUR_KEY_HERE'
```

3. Use the `LLMClient` in `src/agent/llm_client.py` and feed prompts created
	by `Parser.build_cot_prompt()` to request chain-of-thought reasoning and
	a final parseable JSON.

Using a `.env` file

Place an `.env` file in the project root (copy `.env.example`) with your
`GOOGLE_API_KEY`. The project uses `python-dotenv` if available to load
environment variables automatically.

Example `.env`:

```
GOOGLE_API_KEY=your_google_api_key_here
USE_PYAEDT=false
```

Forcing JSON output and strict LLM-only mode

The LLM adapter includes `generate_json()` which prepends a strict
instruction to the prompt requesting `response_mime_type: "application/json"`
and to only return a parsable JSON object. The `Agent` orchestrator uses
this to obtain machine-parseable specs from Gemini.

Important: this project is now configured to be LLM-first. The `Agent`
will call Gemini (via `LLMClient.generate_json()`) and requires a valid
JSON response containing `antenna_type`, `frequencies_hz`, and a non-empty
`tasks` array. If the LLM is not available, or the JSON is missing or
malformed, the `Agent` will raise an error — there is no longer a parser-only
or mocked fallback for producing the modelling tasks. This makes the
behaviour stricter and safer for production workflows where the LLM's
structured output is required.

HFSS / PyAEDT

`src/cad/hfss_manager.py` contains `HFSSManager`. It will try to import `pyaedt`
at runtime and use it if available. Otherwise it returns mocked build and
simulation outputs so you can develop and test without ANSYS HFSS installed.
