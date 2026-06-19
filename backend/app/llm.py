"""Dunne AI-abstractie. Nu OpenRouter; later wisselbaar (bijv. lokaal Qwen).

`generate()` is de enige seam. Een andere provider = een andere implementatie
hiervan; de rest van de app verandert niet. Zonder API-key geeft generate()
None terug zodat de app gewoon draait (de caller toont dan een placeholder).
"""

from __future__ import annotations

import httpx

from .config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self._key = settings.openrouter_api_key.strip()
        self._model = settings.openrouter_model
        self._base = settings.openrouter_base_url.rstrip("/")
        self._referer = settings.openrouter_referer
        self._title = settings.openrouter_title

    @property
    def configured(self) -> bool:
        return bool(self._key)

    async def generate(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 300,
        temperature: float = 0.4,
    ) -> str | None:
        if not self._key:
            return None

        headers = {
            "Authorization": f"Bearer {self._key}",
            "HTTP-Referer": self._referer,
            "X-Title": self._title,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
