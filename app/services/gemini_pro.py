"""Narration and dialogue generation (Gemini Pro): generate_story()."""
from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.schemas import ComicRequest, DialogueLine, OutlineResponse, PanelStory, StoryResponse
from app.services.gemini_client import GeminiClient
from app.services.prompts import story_prompt


class StoryWriter(Protocol):
    def generate_story(self, req: ComicRequest, outline: OutlineResponse) -> StoryResponse: ...


class GeminiStoryWriter:
    def __init__(self, settings: Settings, client: GeminiClient):
        self._model = settings.story_model
        self._client = client

    def generate_story(self, req: ComicRequest, outline: OutlineResponse) -> StoryResponse:
        return self._client.generate_json(self._model, story_prompt(req, outline), StoryResponse)


class MockStoryWriter:
    def generate_story(self, req: ComicRequest, outline: OutlineResponse) -> StoryResponse:
        name = req.character_name
        return StoryResponse(
            panels=[
                PanelStory(
                    panel_number=p.panel_number,
                    caption=f"Panel {p.panel_number} — the {req.setting.value} hums quietly.",
                    narration=f"{name} steps forward, heart racing. {p.scene_description}",
                    dialogue=[DialogueLine(speaker=name, line=f"This is only the beginning!")]
                    if p.panel_number == 1
                    else [],
                )
                for p in outline.panels
            ]
        )


def generate_story(writer: StoryWriter, req: ComicRequest, outline: OutlineResponse) -> StoryResponse:
    """Spec-compatible functional entry point."""
    return writer.generate_story(req, outline)
