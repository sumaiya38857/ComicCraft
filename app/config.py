"""Application settings, loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Secrets ---
    gemini_api_key: str = ""
    hf_api_key: str = ""

    # --- Backends ---
    # "mock" backends let you run the whole app without API keys or a GPU.
    llm_backend: Literal["gemini", "mock"] = "gemini"
    image_backend: Literal["diffusers", "hf_api", "gemini", "pollinations", "mock"] = "diffusers"

    # --- Text models (check https://ai.google.dev/gemini-api/docs/models for current names) ---
    outline_model: str = "gemini-2.5-flash"
    story_model: str = "gemini-2.5-pro"
    llm_max_retries: int = 2

    # --- Image models ---
    sd_model_id: str = "stable-diffusion-v1-5/stable-diffusion-v1-5"
    hf_image_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
    gemini_image_model: str = "gemini-2.5-flash-image"
    pollinations_model: str = "flux"
    image_width: int = 512
    image_height: int = 512
    num_inference_steps: int = 25
    guidance_scale: float = 7.5
    preload_image_model: bool = False

    # --- Comic ---
    panel_count: int = Field(default=5, ge=3, le=8)

    # --- Runtime ---
    debug: bool = False
    media_dir: Path = PROJECT_DIR / "media"
    pdf_font_path: Path | None = None  # optional TTF for full Unicode in PDFs

    @property
    def panels_dir(self) -> Path:
        return self.media_dir / "panels"

    @property
    def exports_dir(self) -> Path:
        return self.media_dir / "exports"

    @property
    def comics_dir(self) -> Path:
        return self.media_dir / "comics"

    def ensure_dirs(self) -> None:
        for d in (self.panels_dir, self.exports_dir, self.comics_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
