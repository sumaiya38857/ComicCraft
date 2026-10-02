"""JSON API routes (see /docs)."""
from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeout
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_comic_or_404, get_service
from app.schemas import Comic, ComicRequest, ImageTestRequest, JobStatus
from app.services.comic_service import ComicService
from app.services.gemini_client import GenerationError

router = APIRouter(tags=["api"])
Service = Annotated[ComicService, Depends(get_service)]


@router.get("/health")
def health(request: Request):
    s = request.app.state.settings
    return {"status": "ok", "llm_backend": s.llm_backend, "image_backend": s.image_backend}


@router.post("/api/v1/comics", status_code=status.HTTP_202_ACCEPTED)
def create_comic(req: ComicRequest, service: Service):
    """Start generation asynchronously. Poll `status_url` until state is `done`."""
    job, _ = service.submit(req)
    return {"job_id": job.job_id, "comic_id": job.comic_id, "status_url": f"/api/v1/jobs/{job.job_id}"}


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str, service: Service):
    job = service.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/api/v1/comics/{comic_id}", response_model=Comic)
def get_comic(comic_id: str, service: Service):
    return get_comic_or_404(service, comic_id)


@router.post("/generate-comic/json")
def generate_comic_json(req: ComicRequest, service: Service):
    """Spec-compatible synchronous endpoint: blocks until done, returns layout + PDF path.
    Prefer POST /api/v1/comics for long-running generation."""
    job, fut = service.submit(req)
    try:
        comic: Comic = fut.result(timeout=1800)
    except FutureTimeout:
        raise HTTPException(504, f"Still generating; poll /api/v1/jobs/{job.job_id}")
    except GenerationError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")
    pdf = service.export_pdf(comic)
    return {
        "comic_id": comic.id,
        "title": comic.title,
        "layout": [p.model_dump(exclude={"image_path"}) for p in comic.panels],
        "pdf_url": f"/media/exports/{pdf.name}",
    }


@router.post("/test-image")
def test_image(body: ImageTestRequest, request: Request, service: Service):
    """Developer utility: generate one image from a raw prompt. Enabled only when DEBUG=true."""
    if not request.app.state.settings.debug:
        raise HTTPException(404, "Not found")
    try:
        _, url = service.test_image(body.prompt, body.art_style)
    except GenerationError as e:
        raise HTTPException(502, str(e))
    return {"image_url": url}
