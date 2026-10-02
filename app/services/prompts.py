"""All prompt templates live here so they can be tuned without touching logic."""
from __future__ import annotations

import json

from app.schemas import ArtStyle, ComicRequest, OutlineResponse, Tone

STYLE_SUFFIX: dict[ArtStyle, str] = {
    ArtStyle.anime: "anime style, cel shading, clean line art, vibrant colors",
    ArtStyle.pixel_art: "pixel art, 16-bit retro game style, limited palette",
    ArtStyle.comic_book: "comic book style, bold ink outlines, halftone shading, vivid flat colors",
    ArtStyle.realistic: "realistic digital painting, cinematic lighting, highly detailed",
}

TONE_GUIDANCE: dict[Tone, str] = {
    Tone.light_hearted: "warm, cheerful and gentle; small stakes, happy resolution",
    Tone.dramatic: "high stakes, tension and emotional turning points; a strong climax",
    Tone.poetic: "lyrical, imagery-rich language; reflective and atmospheric",
    Tone.funny: "playful and humorous; slapstick moments, witty dialogue, comic timing",
}

NEGATIVE_PROMPT = (
    "blurry, low quality, deformed, disfigured, extra limbs, bad anatomy, "
    "text, letters, speech bubble, watermark, signature, nsfw"
)


def outline_prompt(req: ComicRequest, panel_count: int) -> str:
    return f"""You are a comic book writer planning a {panel_count}-panel comic.

Story idea: {req.story_prompt}
Main character: {req.character_name}
Setting: {req.setting.value}
Tone: {req.tone.value} ({TONE_GUIDANCE[req.tone]})
Art style: {req.art_style.value}

Return JSON with:
- "title": a catchy comic title.
- "character_description": a fixed visual description of {req.character_name} (species/appearance,
  clothing, colours) in under 20 words. It will be reused for every image, so be concrete.
- "panels": exactly {panel_count} items numbered 1..{panel_count}, each with
  "panel_number", "title" (short), "scene_description" (1-2 sentences),
  "image_prompt" (under 40 words; describe only what is visible: subject, action, setting,
  camera angle, lighting. Do NOT include text, speech bubbles or the character's name).

The panels must form a complete arc: setup, rising action, climax, resolution."""


def story_prompt(req: ComicRequest, outline: OutlineResponse) -> str:
    outline_json = json.dumps(
        [p.model_dump() for p in outline.panels], ensure_ascii=False, indent=2
    )
    return f"""You are writing the text for the comic "{outline.title}".

Main character: {req.character_name} ({outline.character_description})
Setting: {req.setting.value}
Tone: {req.tone.value} ({TONE_GUIDANCE[req.tone]})

Panel outline:
{outline_json}

For EVERY panel, return an item with the same "panel_number" and:
- "caption": one short ambient line (environment, sounds, time).
- "narration": 2-3 sentences describing {req.character_name}'s actions and feelings.
- "dialogue": 0-3 lines as {{"speaker": ..., "line": ...}}. Keep lines short and punchy.

Keep the tone consistent. Return JSON {{"panels": [...]}}."""


def build_image_prompt(image_prompt: str, character_description: str, style: ArtStyle) -> str:
    # Panel content first: CLIP truncates at ~77 tokens, so the most specific part leads.
    return f"{image_prompt.strip().rstrip('.')}. {character_description.strip().rstrip('.')}. {STYLE_SUFFIX[style]}"
