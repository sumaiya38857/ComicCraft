from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import APP_DIR
from app.schemas import Comic
from app.services.comic_service import ComicService

templates = Jinja2Templates(directory=APP_DIR / "templates")


def get_service(request: Request) -> ComicService:
    return request.app.state.comic_service


def get_comic_or_404(service: ComicService, comic_id: str) -> Comic:
    comic = service.repo.get(comic_id)
    if comic is None:
        raise HTTPException(status_code=404, detail="Comic not found")
    return comic
