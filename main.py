"""NeuroRF entry point."""
from src.agent.agent import Agent

def main():
    print("--- NeuroRF: Neuro-Symbolic Antenna Designer ---")
    
    # Initialize Agent
    agent = Agent(provider="gemini", model="gemini-2.0-flash-lite")
    
    # Get User Request
    user_req = input("\nDescribe your antenna (e.g. '2.4GHz Patch'): ")
    if not user_req: user_req = "2.4GHz Patch"

    # Run Design Flow
    print(f"🤖 Processing request: '{user_req}'...")
    result = agent.run_design(user_req, use_pyaedt=True) # Force Real HFSS
    
    print("\n✅ Design Complete. Summary:")
    import json
    # Print just the physics params for clarity
    for ant in result.get("antennas", []):
        print(f"Type: {ant['type']}")
        print(f"Params: {json.dumps(ant['params'], indent=2)}")

if __name__ == "__main__":
    main()