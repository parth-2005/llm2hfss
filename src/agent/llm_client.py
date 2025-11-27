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

        # Do not import the provider here; do lazy import on generate to avoid
        # imposing extra imports at object construction time.
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
                # Non-fatal if the package doesn't use configure
                pass

            model = self.kwargs.get("model", "gemini-1.5")
            # Attempt to call a generic generate method; API shapes vary.
            # Prefer explicit attribute checks so we can provide a clear error
            # when the installed `google-generativeai` package has a different API.
            try:
                # Try several known API entrypoints from different versions
                # of the `google-generativeai` package. We prefer text-producing
                # call patterns and attempt them in order.

                # 1) genai.generate_text(model=..., prompt=..., max_output_tokens=...)
                if hasattr(genai, "generate_text"):
                    resp = genai.generate_text(model=model, prompt=prompt, max_output_tokens=max_tokens)
                    return getattr(resp, "output", getattr(resp, "text", str(resp)))

                # 2) genai.generate(...) or genai.generate(model=..., prompt=...)
                if hasattr(genai, "generate"):
                    try:
                        resp = genai.generate(model=model, prompt=prompt, max_output_tokens=max_tokens)
                    except TypeError:
                        resp = genai.generate(prompt=prompt)
                    return getattr(resp, "output", getattr(resp, "text", str(resp)))

                # 3) genai.text.generate(model=..., prompt=...)
                if hasattr(genai, "text") and hasattr(genai.text, "generate"):
                    resp = genai.text.generate(model=model, prompt=prompt)
                    return getattr(resp, "text", str(resp))

                # 4) genai.models.generate(...) (newer shape)
                if hasattr(genai, "models") and hasattr(genai.models, "generate"):
                    try:
                        resp = genai.models.generate(model=model, prompt=prompt, max_output_tokens=max_tokens)
                        # resp may be a structured object; try common attributes
                        return getattr(resp, "output", getattr(resp, "text", str(resp)))
                    except Exception:
                        # fallback to converting to str
                        return str(resp)

                # 4b) genai.get_model(...).generate_content(...) (older/newer SDK shapes)
                # Some installed versions expose a `GenerativeModel` object with
                # a `generate_content` method. Try to obtain the model and call it.
                if hasattr(genai, "get_model"):
                    try:
                        model_obj = genai.get_model(model)
                        if hasattr(model_obj, "generate_content"):
                            resp = model_obj.generate_content(prompt=prompt, max_output_tokens=max_tokens)
                            # Attempt to extract textual output from common response shapes
                            out = None
                            if hasattr(resp, "output") and getattr(resp, "output"):
                                first = resp.output[0]
                                out = getattr(first, "content", None) or getattr(first, "text", None) or str(first)
                            if out is None:
                                out = getattr(resp, "text", None) or str(resp)
                            return out
                    except Exception:
                        # ignore and continue to other fallbacks
                        pass

                # 5) genai.chat.* style
                if hasattr(genai, "chat") and hasattr(genai.chat, "create"):
                    try:
                        chat_resp = genai.chat.create(model=model, messages=[{"role": "user", "content": prompt}], max_output_tokens=max_tokens)
                        # Try to extract textual content from common paths
                        if hasattr(chat_resp, "content"):
                            return chat_resp.content
                        if hasattr(chat_resp, "output"):
                            return getattr(chat_resp, "output", str(chat_resp))
                        # Last resort: string conversion
                        return str(chat_resp)
                    except Exception:
                        pass

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
        """Generate and parse JSON from the model.

        If `force_mime` is True the prompt will include a strong instruction
        asking the model to respond with JSON only and to set
        `response_mime_type: application/json` in its response header.
        """
        instruction = (
            'RESPONSE_MIME_TYPE: "application/json"\n'
            'ONLY RETURN A PARSABLE JSON OBJECT AFTER A VERY SHORT CHAIN-OF-THOUGHT.\n'
            'DO NOT RETURN ANY ADDITIONAL TEXT OUTSIDE THE JSON.'
        )
        full_prompt = f"{instruction}\n\n{prompt}" if force_mime else prompt

        raw = self.generate(full_prompt, temperature=temperature, max_tokens=max_tokens)

        # Extract JSON substring and parse
        jtext = self._extract_json(raw)
        try:
            return json.loads(jtext)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM output: {e}\nRaw output:\n{raw}")
