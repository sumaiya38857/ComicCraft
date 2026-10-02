"""Combine outline, story and images into the final panel layout: build_comic_layout()."""
from __future__ import annotations

from app.schemas import OutlineResponse, Panel, StoryResponse


def build_comic_layout(
    outline: OutlineResponse,
    story: StoryResponse,
    images: dict[int, tuple[str, str]],
) -> list[Panel]:
    """Join everything by panel_number (never by list position).

    `images` maps panel_number -> (filesystem path, public URL).
    Panels missing story text or an image are still returned, with empty fields.
    """
    stories = {s.panel_number: s for s in story.panels}
    layout: list[Panel] = []
    for p in sorted(outline.panels, key=lambda x: x.panel_number):
        s = stories.get(p.panel_number)
        path, url = images.get(p.panel_number, (None, None))
        layout.append(
            Panel(
                panel_number=p.panel_number,
                title=p.title,
                scene_description=p.scene_description,
                image_prompt=p.image_prompt,
                image_path=path,
                image_url=url,
                caption=s.caption if s else "",
                narration=s.narration if s else "",
                dialogue=s.dialogue if s else [],
            )
        )
    return layout
