from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.ai.local_intent_model import local_intent_model
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None


class OpenAIClient:
    def __init__(self) -> None:
        self._clients: dict[tuple[str, str, str], OpenAI] = {}
        self._provider_cooldowns: dict[tuple[str, str, str], float] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._candidate_configs())

    def extract_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        payload, _ = self.extract_json_with_trace(system_prompt, user_prompt)
        return payload

    def extract_json_with_trace(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        candidates = self._candidate_configs()
        if not candidates:
            return None, {"enabled": False, "used_provider": None, "attempts": [], "status": "disabled"}

        for config in self._candidate_configs():
            try:
                raw = self._extract_raw_text(config, system_prompt, user_prompt)
            except Exception as exc:
                attempts.append(
                    {
                        "provider": config.provider,
                        "model": config.model,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                self._mark_provider_failed(config, exc)
                continue

            parsed = self._parse_json_payload(raw)
            if parsed is not None:
                attempts.append(
                    {
                        "provider": config.provider,
                        "model": config.model,
                        "status": "ok",
                        "parsed": True,
                    }
                )
                return (
                    parsed,
                    {
                        "enabled": True,
                        "used_provider": config.provider,
                        "used_model": config.model,
                        "attempts": attempts,
                        "status": "ok",
                    },
                )

            attempts.append(
                {
                    "provider": config.provider,
                    "model": config.model,
                    "status": "invalid_json",
                }
            )

        return (
            None,
            {
                "enabled": True,
                "used_provider": None,
                "used_model": None,
                "attempts": attempts,
                "status": "fallback",
            },
        )

    def _candidate_configs(self) -> list[ProviderConfig]:
        provider = settings.llm_provider
        configs: list[ProviderConfig] = []
        now = time.monotonic()

        openai_model = settings.llm_model or settings.openai_model
        deepseek_model = settings.llm_model or settings.deepseek_model
        local_model = settings.llm_model or "local-intent-v1"

        if provider in {"auto", "openai"} and settings.openai_api_key:
            config = ProviderConfig(
                provider="openai",
                api_key=settings.openai_api_key,
                model=openai_model,
                base_url=settings.openai_base_url,
            )
            if self._provider_cooldowns.get(self._cache_key(config), 0) <= now:
                configs.append(config)

        if provider in {"auto", "deepseek"} and settings.deepseek_api_key:
            config = ProviderConfig(
                provider="deepseek",
                api_key=settings.deepseek_api_key,
                model=deepseek_model,
                base_url=settings.deepseek_base_url,
            )
            if self._provider_cooldowns.get(self._cache_key(config), 0) <= now:
                configs.append(config)

        if provider in {"auto", "local"}:
            configs.append(
                ProviderConfig(
                    provider="local",
                    api_key="local",
                    model=local_model,
                    base_url=None,
                )
            )

        return configs

    def _get_client(self, config: ProviderConfig) -> OpenAI:
        cache_key = self._cache_key(config)
        if cache_key not in self._clients:
            client_kwargs: dict[str, Any] = {
                "api_key": config.api_key,
                "max_retries": 0,
                "timeout": 12.0,
            }
            if config.base_url:
                client_kwargs["base_url"] = config.base_url
            self._clients[cache_key] = OpenAI(**client_kwargs)
        return self._clients[cache_key]

    def _cache_key(self, config: ProviderConfig) -> tuple[str, str, str]:
        return (config.provider, config.api_key, config.base_url or "")

    def _mark_provider_failed(self, config: ProviderConfig, exc: Exception) -> None:
        message = str(exc).lower()
        cooldown_seconds = 60
        if any(token in message for token in ["insufficient_quota", "quota", "rate limit", "rate_limit", "authentication", "invalid api key"]):
            cooldown_seconds = 300
        elif any(token in message for token in ["timeout", "timed out", "connection", "temporarily unavailable"]):
            cooldown_seconds = 90

        self._provider_cooldowns[self._cache_key(config)] = time.monotonic() + cooldown_seconds
        logger.warning(
            "LLM provider %s temporarily disabled for %ss after error: %s",
            config.provider,
            cooldown_seconds,
            exc,
        )

    def _extract_raw_text(self, config: ProviderConfig, system_prompt: str, user_prompt: str) -> str | None:
        if config.provider == "local":
            payload, _ = local_intent_model.extract_json_with_trace(user_prompt)
            return json.dumps(payload, ensure_ascii=False) if payload else None

        client = self._get_client(config)

        if config.provider == "openai" and hasattr(client, "responses") and not config.base_url:
            response = client.responses.create(
                model=config.model,
                instructions=system_prompt,
                input=user_prompt,
                max_output_tokens=settings.llm_max_output_tokens,
            )
            return response.output_text.strip() if getattr(response, "output_text", None) else None

        completion = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=settings.llm_max_output_tokens,
            response_format={"type": "json_object"},
        )
        message = completion.choices[0].message.content
        return message.strip() if isinstance(message, str) else None

    def _parse_json_payload(self, raw: str | None) -> dict[str, Any] | None:
        if not raw:
            return None

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        candidates = [cleaned, self._extract_first_json_object(cleaned)]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _extract_first_json_object(self, value: str) -> str | None:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        return match.group(0) if match else None


openai_client = OpenAIClient()
