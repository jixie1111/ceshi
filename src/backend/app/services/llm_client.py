from __future__ import annotations

import json
from typing import Any, Dict, List

from ..core.config import get_settings


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = None
        if self.settings.openai_api_key:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.settings.openai_api_key, base_url=self.settings.openai_base_url)
            except Exception:
                self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    def json_chat(self, system: str, user: str, temperature: float = 0.1) -> Dict[str, Any] | None:
        if not self.client:
            return None
        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
        return None

    def answer_chat(self, system: str, user: str, temperature: float = 0.2) -> str | None:
        if not self.client:
            return None
        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
