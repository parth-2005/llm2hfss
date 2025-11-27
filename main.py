"""NeuroRF entry point (minimal, dependency-free smoke test).

Run `python main.py` to verify the scaffold is functional.
"""

from src.agent.agent import Agent


def main():
    print("NeuroRF scaffold: agentic COT -> HFSS demo (mock)")
    agent = Agent(provider="gemini", model="gemini-2.0-flash-lite")
    # Example user request; Agent will attempt LLM JSON parsing but will
    # gracefully fall back to parser-only behavior if Gemini is not configured.
    user_req = "I need a Bluetooth antenna."
    result = agent.run_design(user_req)
    print("Agent result:")
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
