"""ComicCraft FastAPI application factory.

Run:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_routes, routes
from app.config import APP_DIR, Settings, get_settings
from app.services.comic_service import ComicService
from app.services.gemini_flash import GeminiOutlineGenerator, MockOutlineGenerator
from app.services.gemini_pro import GeminiStoryWriter, MockStoryWriter
from app.services.image_generator import DiffusersImageGenerator, create_image_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("comiccraft")


def build_service(settings: Settings) -> ComicService:
    if settings.llm_backend == "mock":
        outline_gen, story_writer = MockOutlineGenerator(), MockStoryWriter()
    else:
        from app.services.gemini_client import GeminiClient

        client = GeminiClient(settings)
        outline_gen = GeminiOutlineGenerator(settings, client)
        story_writer = GeminiStoryWriter(settings, client)
    image_gen = create_image_generator(settings)
    if settings.preload_image_model and isinstance(image_gen, DiffusersImageGenerator):
        image_gen.load()
    return ComicService(settings, outline_gen, story_writer, image_gen)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("Starting ComicCraft (llm=%s, images=%s)", settings.llm_backend, settings.image_backend)
        app.state.settings = settings
        app.state.comic_service = build_service(settings)
        yield
        app.state.comic_service.shutdown()

    app = FastAPI(
        title="ComicCraft",
        description="AI comic story creator using Gemini and Stable Diffusion",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    app.include_router(routes.router)
    app.include_router(api_routes.router)
    return app


app = create_app()
