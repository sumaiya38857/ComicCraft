"""Pydantic models shared by the API, services and Gemini structured output."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Setting(str, Enum):
    school = "school"
    forest = "forest"
    space = "space"
    city = "city"


class Tone(str, Enum):
    light_hearted = "light-hearted"
    dramatic = "dramatic"
    poetic = "poetic"
    funny = "funny"


class ArtStyle(str, Enum):
    anime = "anime"
    pixel_art = "pixel art"
    comic_book = "comic book"
    realistic = "realistic"


class ComicRequest(BaseModel):
    """User input (form or JSON). Equivalent of the spec's PromptRequest."""

    story_prompt: str = Field(min_length=5, max_length=500)
    character_name: str = Field(min_length=1, max_length=40)
    setting: Setting = Setting.forest
    tone: Tone = Tone.dramatic
    art_style: ArtStyle = ArtStyle.comic_book


# ---------- Gemini Flash: outline ----------
class PanelOutline(BaseModel):
    panel_number: int
    title: str
    scene_description: str
    image_prompt: str


class OutlineResponse(BaseModel):
    title: str
    character_description: str = Field(
        description="Short, fixed visual description of the main character reused in every image prompt"
    )
    panels: list[PanelOutline]


# ---------- Gemini Pro: story ----------
class DialogueLine(BaseModel):
    speaker: str
    line: str


class PanelStory(BaseModel):
    panel_number: int
    caption: str
    narration: str
    dialogue: list[DialogueLine] = []


class StoryResponse(BaseModel):
    panels: list[PanelStory]


# ---------- Final comic ----------
class Panel(BaseModel):
    panel_number: int
    title: str
    scene_description: str
    image_prompt: str
    image_url: str | None = None
    image_path: str | None = None
    caption: str = ""
    narration: str = ""
    dialogue: list[DialogueLine] = []


class Comic(BaseModel):
    id: str
    title: str
    request: ComicRequest
    character_description: str
    seed: int
    panels: list[Panel]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------- Jobs ----------
class JobState(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobStatus(BaseModel):
    job_id: str
    comic_id: str
    state: JobState = JobState.queued
    step: str = "Queued"
    progress: int = 0
    error: str | None = None


class ImageTestRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=300)
    art_style: ArtStyle = ArtStyle.comic_book
