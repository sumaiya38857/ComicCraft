"""HTML (Jinja2) routes for the browser UI."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.api.deps import get_comic_or_404, get_service, templates
from app.schemas import ArtStyle, ComicRequest, Setting, Tone
from app.services.comic_service import ComicService

router = APIRouter(tags=["web"])
Service = Annotated[ComicService, Depends(get_service)]


def _form_options() -> dict:
    return {
        "settings_opts": [s.value for s in Setting],
        "tones": [t.value for t in Tone],
        "styles": [a.value for a in ArtStyle],
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {**_form_options(), "form": {}, "errors": []})


@router.post("/generate")
def generate(
    request: Request,
    service: Service,
    story_prompt: Annotated[str, Form()],
    character_name: Annotated[str, Form()],
    setting: Annotated[str, Form()] = Setting.forest.value,
    tone: Annotated[str, Form()] = Tone.dramatic.value,
    art_style: Annotated[str, Form()] = ArtStyle.comic_book.value,
):
    form = dict(story_prompt=story_prompt.strip(), character_name=character_name.strip(),
                setting=setting, tone=tone, art_style=art_style)
    try:
        req = ComicRequest(**form)
    except ValidationError as e:
        errors = [f"{'/'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        return templates.TemplateResponse(
            request, "index.html", {**_form_options(), "form": form, "errors": errors}, status_code=422
        )
    job, _ = service.submit(req)
    return RedirectResponse(f"/jobs/{job.job_id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_progress(request: Request, job_id: str, service: Service):
    job = service.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return templates.TemplateResponse(request, "progress.html", {"job": job})


@router.get("/comics/{comic_id}", response_class=HTMLResponse)
def comic_preview(request: Request, comic_id: str, service: Service):
    comic = get_comic_or_404(service, comic_id)
    return templates.TemplateResponse(
        request, "comic_preview.html", {**_form_options(), "comic": comic, "layout": comic.panels}
    )


@router.post("/comics/{comic_id}/regenerate")
def regenerate(
    comic_id: str,
    service: Service,
    tone: Annotated[Tone, Form()],
    art_style: Annotated[ArtStyle, Form()],
):
    """Scenario 2. Tone changed -> full pipeline. Only style changed -> redraw images, keep the story."""
    comic = get_comic_or_404(service, comic_id)
    if tone == comic.request.tone:
        job, _ = service.submit_restyle(comic, art_style)
    else:
        job, _ = service.submit(comic.request.model_copy(update={"tone": tone, "art_style": art_style}))
    return RedirectResponse(f"/jobs/{job.job_id}", status_code=303)


@router.get("/comics/{comic_id}/pdf")
def download_pdf(comic_id: str, service: Service):
    comic = get_comic_or_404(service, comic_id)
    path = service.export_pdf(comic)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/export-success", response_class=HTMLResponse)
def export_success(request: Request, comic_id: str | None = None):
    return templates.TemplateResponse(request, "export_success.html", {"comic_id": comic_id})
