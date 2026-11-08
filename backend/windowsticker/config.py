"""Runtime configuration, read from the environment (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Vultr Serverless Inference
    vultr_inference_api_key: SecretStr | None = None
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"

    # Vultr platform API
    vultr_api_key: SecretStr | None = None
    vultr_api_base_url: str = "https://api.vultr.com/v2"

    # Control plane
    database_url: str = Field(
        default="postgresql+asyncpg://windowsticker:windowsticker@localhost:5432/windowsticker",
        alias="WSK_DATABASE_URL",
    )
    artifact_dir: Path = Field(default=Path("./artifacts"), alias="WSK_ARTIFACT_DIR")

    # Sandbox host
    sandbox_image: str = Field(default="python", alias="WSK_SANDBOX_IMAGE")
    agent_image: str = Field(default="windowsticker/agent-base:1", alias="WSK_AGENT_IMAGE")
    warden_listen: str = Field(default="127.0.0.1:8899", alias="WSK_WARDEN_LISTEN")

    # Write access (starting tests, labelling runs). Reads are public.
    admin_token: SecretStr | None = Field(default=None, alias="WSK_ADMIN_TOKEN")
    # Narrower tokens: CI gets the submit token only, reviewers the label token only.
    submit_token: SecretStr | None = Field(default=None, alias="WSK_SUBMIT_TOKEN")
    label_token: SecretStr | None = Field(default=None, alias="WSK_LABEL_TOKEN")
    max_runs_per_test: int = Field(default=240, alias="WSK_MAX_RUNS_PER_TEST")
    # Public live demos per UTC day (each is 6 runs, about $0.05). 0 turns the demo off.
    demo_daily_limit: int = Field(default=30, alias="WSK_DEMO_DAILY_LIMIT")
    # The model that writes plain-English explanations of incidents ("" turns them off).
    analyst_model: str = Field(default="deepseek-v4.1-flash-1017", alias="WSK_ANALYST_MODEL")

    # Price of the sandbox host, for all-in cost on stickers (VX1 2c/8g/120 GB, measured plan).
    host_hourly_usd: float = Field(default=0.076, alias="WSK_HOST_HOURLY_USD")
    host_plan: str = Field(default="vx1-g-2c-8g-120s", alias="WSK_HOST_PLAN")
    host_region: str = Field(default="ewr", alias="WSK_HOST_REGION")

    # Run budgets (defaults; a test can tighten them)
    max_steps: int = 10
    run_wall_clock_s: float = 240.0
    run_token_budget: int = 60_000
    sandbox_cpus: int = 1
    sandbox_memory_mib: int = 1024

    def require_inference_key(self) -> str:
        if self.vultr_inference_api_key is None:
            raise RuntimeError(
                "VULTR_INFERENCE_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        return self.vultr_inference_api_key.get_secret_value()

    def require_vultr_api_key(self) -> str:
        if self.vultr_api_key is None:
            raise RuntimeError(
                "VULTR_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        return self.vultr_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
