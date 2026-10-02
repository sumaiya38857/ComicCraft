"""Panel outline generation (Gemini Flash): generate_outline()."""
from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.schemas import ComicRequest, OutlineResponse, PanelOutline
from app.services.gemini_client import GeminiClient, GenerationError
from app.services.prompts import outline_prompt


class OutlineGenerator(Protocol):
    def generate_outline(self, req: ComicRequest, panel_count: int) -> OutlineResponse: ...


def normalize_outline(outline: OutlineResponse, panel_count: int) -> OutlineResponse:
    """Enforce exactly `panel_count` panels numbered 1..N."""
    if len(outline.panels) < panel_count:
        raise GenerationError(
            f"Outline had {len(outline.panels)} panels, expected {panel_count}."
        )
    panels = sorted(outline.panels, key=lambda p: p.panel_number)[:panel_count]
    for i, p in enumerate(panels, start=1):
        p.panel_number = i
    outline.panels = panels
    return outline


class GeminiOutlineGenerator:
    def __init__(self, settings: Settings, client: GeminiClient):
        self._model = settings.outline_model
        self._client = client

    def generate_outline(self, req: ComicRequest, panel_count: int) -> OutlineResponse:
        prompt = outline_prompt(req, panel_count)
        try:
            outline = self._client.generate_json(self._model, prompt, OutlineResponse)
            return normalize_outline(outline, panel_count)
        except GenerationError:
            # One more attempt with a stricter reminder before failing the job.
            outline = self._client.generate_json(
                self._model,
                prompt + f"\n\nIMPORTANT: return exactly {panel_count} panels.",
                OutlineResponse,
                temperature=0.5,
            )
            return normalize_outline(outline, panel_count)


class MockOutlineGenerator:
    """Deterministic outline for offline development and tests."""

    BEATS = [
        ("The Beginning", "introduces themselves in"),
        ("A Strange Discovery", "discovers something unusual in"),
        ("Into the Unknown", "ventures deeper into"),
        ("The Challenge", "faces their greatest challenge in"),
        ("Triumph", "returns victorious from"),
        ("A New Friend", "meets an unexpected friend in"),
        ("The Storm", "is caught in a storm in"),
        ("Homeward", "heads home from"),
    ]

    def generate_outline(self, req: ComicRequest, panel_count: int) -> OutlineResponse:
        name, place = req.character_name, req.setting.value
        panels = [
            PanelOutline(
                panel_number=i + 1,
                title=title,
                scene_description=f"{name} {verb} the {place}. ({req.story_prompt})",
                image_prompt=f"wide shot, a hero who {verb} a {place}, {req.tone.value} mood",
            )
            for i, (title, verb) in enumerate(self.BEATS[:panel_count])
        ]
        return OutlineResponse(
            title=f"{name} and the {place.title()} Adventure",
            character_description=f"{name}, a brave adventurer with a red scarf",
            panels=panels,
        )


def generate_outline(gen: OutlineGenerator, req: ComicRequest, panel_count: int = 5) -> OutlineResponse:
    """Spec-compatible functional entry point."""
    return gen.generate_outline(req, panel_count)
