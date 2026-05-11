"""
GroqClient — Shared async Groq LLM client for all RapidAid agents.

Models used:
  - llama-3.3-70b-versatile  → Primary reasoning model (triage, hospital, dispatch)
  - llama-3.1-8b-instant     → Fast model for lightweight tasks (negotiation, route summary)
  - mixtral-8x7b-32768       → Fallback with large context window

All agents import this module instead of instantiating their own clients.
Falls back gracefully if GROQ_API_KEY is not set.
"""
import asyncio
import json
import logging
import re
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Model constants ────────────────────────────────────────────────────────────
GROQ_PRIMARY_MODEL   = "llama-3.3-70b-versatile"    # best reasoning, used for triage
GROQ_FAST_MODEL      = "llama-3.1-8b-instant"       # ultra-low latency
GROQ_FALLBACK_MODEL  = "mixtral-8x7b-32768"         # large context


class GroqLLMClient:
    """
    Async wrapper around the Groq Python SDK.
    All methods are coroutines and safe to call from FastAPI async routes.
    """

    def __init__(self):
        self._client = None
        self._available = False

        if not settings.GROQ_API_KEY:
            logger.info("GroqLLMClient: GROQ_API_KEY not set — LLM features disabled")
            return

        try:
            from groq import Groq  # type: ignore
            self._client = Groq(api_key=settings.GROQ_API_KEY)
            self._available = True
            logger.info("GroqLLMClient: Initialized. Primary model: %s", GROQ_PRIMARY_MODEL)
        except ImportError:
            logger.warning("GroqLLMClient: 'groq' package not installed — run: pip install groq")
        except Exception as exc:
            logger.error("GroqLLMClient: Initialization failed: %s", exc)

    @property
    def is_available(self) -> bool:
        return self._available

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str = GROQ_PRIMARY_MODEL,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = True,
    ) -> Optional[str]:
        """
        Send a chat completion request to Groq.

        Returns the assistant's response text, or None on failure.
        Runs the synchronous Groq SDK call in a thread pool so it doesn't
        block the FastAPI event loop.
        """
        if not self._available or not self._client:
            return None

        def _call():
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            return self._client.chat.completions.create(**kwargs)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _call)
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("GroqLLMClient.chat() failed: %s", exc)
            return None

    def extract_json(self, text: str) -> Optional[dict]:
        """
        Safely extract a JSON object from LLM text output.
        Handles markdown code fences and partial wrapping.
        """
        if not text:
            return None
        # Strip code fences
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find first { ... } block
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        logger.warning("GroqLLMClient.extract_json: Could not parse response: %s", text[:200])
        return None


# ── Global singleton ───────────────────────────────────────────────────────────
groq_client = GroqLLMClient()
