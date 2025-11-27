"""Lightweight LLM client adapter.

This adapter attempts to use Google's Generative API (Gemini) when
available. If the environment does not have the required package,
the adapter raises an informative error instructing how to configure
the environment.

Usage:
    from src.agent.llm_client import LLMClient
    client = LLMClient(provider='gemini')
    resp = client.generate(prompt)

Set `GOOGLE_API_KEY` or the typical Google application credentials
when using Gemini.
"""

from typing import Optional, Any
import os
import json
import re


class LLMClient:
    """Lightweight LLM adapter with .env support and JSON enforcement.

    Behavior:
    - Loads `GOOGLE_API_KEY` from environment (dotenv supported).
    - Lazy-imports `google.generativeai` when used.
    - `generate_json()` will attempt to force a JSON-only response by
      adding an instruction header and then parsing the returned text.
    """

    JSON_EXTRACT_RE = re.compile(r"(\{.*\})", re.S)

    def __init__(self, provider: str = "gemini", **kwargs):
        # Load environment variables using the shared env helper.
        try:
            from src.utils.env import load_envs

            # Do not override existing env vars by default
            load_envs(override=False)
        except Exception:
            # If the helper fails (e.g., import issues), fall back silently
            pass

        # Read key early and fail fast: this project requires an LLM key.
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY not found in environment. Copy .env.example to .env or set DOTENV_PATH, or export the variable."
            )
        self.provider = provider.lower()
        self.kwargs = kwargs
        self._genai = None

    def generate(self, prompt: str, temperature: float = 0.0, max_tokens: int = 512) -> str:
        """Generate raw text from the selected provider.

        This does not enforce JSON. Use `generate_json()` to require JSON output.
        """
        if self.provider == "gemini":
            # Ensure API key is present (checked at init) and import provider lazily
            try:
                import google.generativeai as genai  # type: ignore
            except Exception:
                raise RuntimeError(
                    "Gemini client not available. Install `google-generativeai` and ensure it is importable."
                )

            # Configure the client if possible
            try:
                if hasattr(genai, "configure"):
                    genai.configure(api_key=self.api_key)
            except Exception:
                pass

            model_name = self.kwargs.get("model", "gemini-2.0-flash-lite")
            
            # --- MODERN SDK PATH (v0.8.5+) ---
            # This is the correct way to instantiate a model in the current SDK.
            if hasattr(genai, "GenerativeModel"):
                try:
                    generation_config = {
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    }
                    model = genai.GenerativeModel(model_name, generation_config=generation_config)
                    response = model.generate_content(prompt)
                    return response.text
                except Exception as e:
                    # Fallthrough only if this specific modern call fails
                    print(f"Modern GenerativeModel call failed: {e}")

            # --- LEGACY FALLBACKS ---
            try:
                # 1) genai.generate_text (Old PaLM API)
                if hasattr(genai, "generate_text"):
                    resp = genai.generate_text(model=model_name, prompt=prompt, max_output_tokens=max_tokens)
                    return getattr(resp, "output", getattr(resp, "text", str(resp)))

                # 2) genai.chat.* style
                if hasattr(genai, "chat") and hasattr(genai.chat, "create"):
                    chat_resp = genai.chat.create(model=model_name, messages=[{"role": "user", "content": prompt}], max_output_tokens=max_tokens)
                    if hasattr(chat_resp, "content"):
                        return chat_resp.content
                    if hasattr(chat_resp, "output"):
                        return getattr(chat_resp, "output", str(chat_resp))
                    return str(chat_resp)

                # If none matched, report an informative error
                raise RuntimeError(
                    "Installed `google-generativeai` package does not expose a supported generate API. "
                    "Ensure you have the official package and a compatible version."
                )
            except Exception as e:
                raise RuntimeError(f"Failed to call Gemini API: {e}")

        raise NotImplementedError(f"Provider {self.provider} is not implemented")

    def _extract_json(self, text: str) -> str:
        # Try to find the first balanced JSON object in the text
        m = self.JSON_EXTRACT_RE.search(text)
        if m:
            return m.group(1)
        # Fallback: try to find from first '{' to last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        raise ValueError("No JSON object found in LLM output")

    def generate_json(self, prompt: str, temperature: float = 0.0, max_tokens: int = 1024, force_mime: bool = True) -> Any:
        """Generate and parse JSON from the model."""
        
        # Note: If using the modern SDK with Gemini 1.5/2.0, we can theoretically use 
        # response_mime_type='application/json' in generation_config, but we stick 
        # to prompt engineering here for maximum compatibility across model versions.
        instruction = (
            'RESPONSE_MIME_TYPE: "application/json"\n'
            'ONLY RETURN A PARSABLE JSON OBJECT AFTER A VERY SHORT CHAIN-OF-THOUGHT.\n'
            'DO NOT RETURN ANY ADDITIONAL TEXT OUTSIDE THE JSON.'
        )
        full_prompt = f"{instruction}\n\n{prompt}" if force_mime else prompt

        raw = self.generate(full_prompt, temperature=temperature, max_tokens=max_tokens)

        # Extract JSON substring and parse
        try:
            jtext = self._extract_json(raw)
            return json.loads(jtext)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM output: {e}\nRaw output:\n{raw}")