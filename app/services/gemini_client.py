"""Thin wrapper around the google-genai SDK with structured (JSON-schema) output and retries."""
from __future__ import annotations

import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class GenerationError(RuntimeError):
    """Raised with a user-friendly message when an AI step fails."""


class GeminiClient:
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise GenerationError(
                "GEMINI_API_KEY is not set. Add it to .env, or set LLM_BACKEND=mock to try the app without it."
            )
        from google import genai  # imported lazily so mock mode needs no SDK

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._retries = settings.llm_max_retries

    def generate_json(self, model: str, prompt: str, schema: type[T], temperature: float = 0.9) -> T:
        from google.genai import errors, types

        last_err: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=max(0.2, temperature - 0.3 * attempt),
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                if isinstance(resp.parsed, schema):
                    return resp.parsed
                if not resp.text:
                    raise GenerationError(
                        "The AI returned no content (possibly blocked by safety filters). Try rephrasing your prompt."
                    )
                return schema.model_validate_json(resp.text)
            except (ValidationError, ValueError) as e:
                last_err = e
                log.warning("Gemini %s returned invalid JSON (attempt %d): %s", model, attempt + 1, e)
            except errors.APIError as e:
                last_err = e
                code = getattr(e, "code", None)
                log.warning("Gemini API error %s (attempt %d): %s", code, attempt + 1, e)
                if code in (400, 401, 403, 404):
                    raise GenerationError(f"Gemini request failed ({code}): {e.message or e}") from e
                time.sleep(2**attempt)  # 429 / 5xx: back off and retry
        raise GenerationError(f"Gemini failed after {self._retries + 1} attempts: {last_err}")
