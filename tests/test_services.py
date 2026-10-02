import pytest

from app.schemas import (
    ArtStyle, Comic, ComicRequest, DialogueLine, OutlineResponse, PanelOutline, PanelStory, StoryResponse,
)
from app.services.exporters import save_pdf
from app.services.gemini_client import GenerationError
from app.services.gemini_flash import MockOutlineGenerator, normalize_outline
from app.services.image_generator import MockImageGenerator
from app.services.layout_builder import build_comic_layout
from app.services.prompts import STYLE_SUFFIX, build_image_prompt

REQ = ComicRequest(story_prompt="A brave fox exploring an enchanted forest", character_name="Rusty")


def _outline(n=3):
    return OutlineResponse(
        title="T", character_description="an orange fox",
        panels=[PanelOutline(panel_number=i, title=f"P{i}", scene_description="s", image_prompt="p") for i in range(1, n + 1)],
    )


def test_layout_joins_by_panel_number_not_position():
    story = StoryResponse(panels=[
        PanelStory(panel_number=3, caption="c3", narration="n3"),
        PanelStory(panel_number=1, caption="c1", narration="n1", dialogue=[DialogueLine(speaker="R", line="hi")]),
    ])
    layout = build_comic_layout(_outline(), story, {1: ("/x/1.png", "/media/1.png")})
    assert [p.panel_number for p in layout] == [1, 2, 3]
    assert layout[0].caption == "c1" and layout[0].dialogue[0].line == "hi"
    assert layout[1].narration == ""  # missing story -> empty, not misaligned
    assert layout[2].caption == "c3"
    assert layout[0].image_url == "/media/1.png" and layout[1].image_url is None


def test_normalize_outline_renumbers_and_trims():
    o = _outline(6)
    o.panels.reverse()
    out = normalize_outline(o, 5)
    assert [p.panel_number for p in out.panels] == [1, 2, 3, 4, 5]


def test_normalize_outline_rejects_too_few():
    with pytest.raises(GenerationError):
        normalize_outline(_outline(2), 5)


def test_image_prompt_includes_character_and_style():
    p = build_image_prompt("fox jumps a stream.", "orange fox, green cloak", ArtStyle.anime)
    assert p.startswith("fox jumps a stream.") and "green cloak" in p and STYLE_SUFFIX[ArtStyle.anime] in p


def test_pdf_export_handles_unicode(settings, tmp_path):
    outline = MockOutlineGenerator().generate_outline(REQ, 3)
    img = MockImageGenerator(settings).generate("test", tmp_path / "a.png", 1)
    story = StoryResponse(panels=[PanelStory(panel_number=1, caption="“Smart quotes” — and emoji 🦊", narration="ok")])
    comic = Comic(id="12345678-aaaa", title="Fox’s Tale", request=REQ, character_description="fox", seed=1,
                  panels=build_comic_layout(outline, story, {1: (str(img), "/m")}))
    pdf = save_pdf(comic, tmp_path / "exports")
    assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")
    assert pdf.name.startswith("comic_12345678_")


def test_request_validation():
    with pytest.raises(ValueError):
        ComicRequest(story_prompt="hi", character_name="R")
    with pytest.raises(ValueError):
        ComicRequest(story_prompt="valid prompt", character_name="R", tone="sad")
