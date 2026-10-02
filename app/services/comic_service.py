"""Orchestrates the generation pipeline and tracks background jobs."""
from __future__ import annotations

import logging
import random
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from app.config import Settings
from app.schemas import ArtStyle, Comic, ComicRequest, JobState, JobStatus, OutlineResponse, PanelOutline, StoryResponse, PanelStory
from app.services.exporters import save_pdf
from app.services.gemini_client import GenerationError
from app.services.gemini_flash import OutlineGenerator
from app.services.gemini_pro import StoryWriter
from app.services.image_generator import ImageGenerator
from app.services.layout_builder import build_comic_layout
from app.services.prompts import build_image_prompt

log = logging.getLogger(__name__)


class ComicRepository:
    """Stores finished comics as JSON files so previews survive restarts."""

    def __init__(self, comics_dir: Path):
        self._dir = comics_dir

    def save(self, comic: Comic) -> None:
        (self._dir / f"{comic.id}.json").write_text(comic.model_dump_json(indent=2), encoding="utf-8")

    def get(self, comic_id: str) -> Comic | None:
        try:
            uuid.UUID(comic_id)  # guards against path traversal
        except ValueError:
            return None
        path = self._dir / f"{comic_id}.json"
        return Comic.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    def create(self, comic_id: str) -> JobStatus:
        job = JobStatus(job_id=uuid.uuid4().hex, comic_id=comic_id)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy() if job else None

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update=fields)


class ComicService:
    def __init__(
        self,
        settings: Settings,
        outline_gen: OutlineGenerator,
        story_writer: StoryWriter,
        image_gen: ImageGenerator,
    ):
        self.settings = settings
        self.outline_gen = outline_gen
        self.story_writer = story_writer
        self.image_gen = image_gen
        self.jobs = JobStore()
        self.repo = ComicRepository(settings.comics_dir)
        # Single worker: generation is GPU/CPU-heavy, so jobs queue instead of competing.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comic-worker")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ---------- public API ----------
    def submit(self, req: ComicRequest) -> tuple[JobStatus, Future]:
        comic_id = str(uuid.uuid4())
        job = self.jobs.create(comic_id)
        fut = self._executor.submit(self._run_full, job.job_id, comic_id, req)
        return job, fut

    def submit_restyle(self, source: Comic, art_style: ArtStyle) -> tuple[JobStatus, Future]:
        """Scenario 2 shortcut: keep the story, redraw only the images in a new art style."""
        comic_id = str(uuid.uuid4())
        job = self.jobs.create(comic_id)
        fut = self._executor.submit(self._run_restyle, job.job_id, comic_id, source, art_style)
        return job, fut

    def export_pdf(self, comic: Comic) -> Path:
        return save_pdf(comic, self.settings.exports_dir, self.settings.pdf_font_path)

    def test_image(self, prompt: str, art_style: ArtStyle) -> tuple[Path, str]:
        name = f"test_{uuid.uuid4().hex[:10]}.png"
        full_prompt = build_image_prompt(prompt, "", art_style).replace(". .", ".")
        path = self.image_gen.generate(full_prompt, self.settings.panels_dir / "tests" / name, random.randint(0, 2**31))
        return path, f"/media/panels/tests/{name}"

    # ---------- pipeline ----------
    def _run_full(self, job_id: str, comic_id: str, req: ComicRequest) -> Comic:
        def work() -> Comic:
            self._step(job_id, "Writing the panel outline (Gemini Flash)", 5)
            outline = self.outline_gen.generate_outline(req, self.settings.panel_count)
            self._step(job_id, "Writing narration & dialogue (Gemini Pro)", 15)
            story = self.story_writer.generate_story(req, outline)
            return self._illustrate_and_save(job_id, comic_id, req, outline, story, random.randint(0, 2**31))

        return self._guard(job_id, work)

    def _run_restyle(self, job_id: str, comic_id: str, source: Comic, art_style: ArtStyle) -> Comic:
        def work() -> Comic:
            req = source.request.model_copy(update={"art_style": art_style})
            outline = OutlineResponse(
                title=source.title,
                character_description=source.character_description,
                panels=[PanelOutline(**p.model_dump(include={"panel_number", "title", "scene_description", "image_prompt"})) for p in source.panels],
            )
            story = StoryResponse(
                panels=[PanelStory(**p.model_dump(include={"panel_number", "caption", "narration", "dialogue"})) for p in source.panels]
            )
            return self._illustrate_and_save(job_id, comic_id, req, outline, story, source.seed)

        return self._guard(job_id, work)

    def _illustrate_and_save(
        self, job_id: str, comic_id: str, req: ComicRequest, outline: OutlineResponse, story: StoryResponse, seed: int
    ) -> Comic:
        images: dict[int, tuple[str, str]] = {}
        n = len(outline.panels)
        for i, p in enumerate(outline.panels):
            self._step(job_id, f"Drawing panel {i + 1} of {n} (Stable Diffusion)", 25 + int(70 * i / n))
            prompt = build_image_prompt(p.image_prompt, outline.character_description, req.art_style)
            fname = f"panel_{p.panel_number}.png"
            path = self.image_gen.generate(prompt, self.settings.panels_dir / comic_id / fname, seed + p.panel_number)
            images[p.panel_number] = (str(path), f"/media/panels/{comic_id}/{fname}")

        self._step(job_id, "Assembling the comic", 97)
        comic = Comic(
            id=comic_id,
            title=outline.title,
            request=req,
            character_description=outline.character_description,
            seed=seed,
            panels=build_comic_layout(outline, story, images),
        )
        self.repo.save(comic)
        self.jobs.update(job_id, state=JobState.done, step="Done", progress=100)
        return comic

    def _step(self, job_id: str, step: str, progress: int) -> None:
        log.info("[%s] %s", job_id[:8], step)
        self.jobs.update(job_id, state=JobState.running, step=step, progress=progress)

    def _guard(self, job_id: str, work) -> Comic:
        try:
            return work()
        except GenerationError as e:
            self.jobs.update(job_id, state=JobState.failed, step="Failed", error=str(e))
            raise
        except Exception as e:  # unexpected: log full trace, show a generic message
            log.exception("Job %s failed", job_id)
            self.jobs.update(job_id, state=JobState.failed, step="Failed", error=f"Unexpected error: {e}")
            raise
