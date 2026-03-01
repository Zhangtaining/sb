"""Guidance service configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuidanceConfig:
    camera_ids: list[str] = field(default_factory=list)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://gym:gympass@localhost:5432/gymdb"

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024

    # Rate limit: max 1 LLM call per track per N seconds
    rate_limit_seconds: int = 30

    consumer_group: str = "guidance-workers"
    consumer_name: str = "guidance-0"
    block_ms: int = 500


def build_config(settings) -> GuidanceConfig:
    return GuidanceConfig(
        camera_ids=settings.camera_id_list,
        redis_url=settings.redis_url,
        database_url=settings.database_url,
        anthropic_api_key=settings.anthropic_api_key,
        llm_model=settings.llm_model,
        llm_max_tokens=settings.llm_max_tokens,
        rate_limit_seconds=settings.guidance_rate_limit_seconds,
        consumer_name=os.environ.get("GUIDANCE_CONSUMER_NAME", "guidance-0"),
    )
