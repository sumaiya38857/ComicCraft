"""Panel illustration (Stable Diffusion): generate_image().

Three interchangeable backends behind one interface:
  * DiffusersImageGenerator – local Stable Diffusion via Hugging Face Diffusers (GPU recommended)
  * HFInferenceImageGenerator – hosted generation through the Hugging Face Inference API
  * MockImageGenerator – Pillow placeholder images for offline dev and tests
"""
from __future__ import annotations

import hashlib
import io
import logging
import textwrap
import threading
import time
from pathlib import Path
from urllib.parse import quote
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.services.gemini_client import GenerationError
from app.services.prompts import NEGATIVE_PROMPT

log = logging.getLogger(__name__)


class ImageGenerator(Protocol):
    def generate(self, prompt: str, out_path: Path, seed: int) -> Path: ...


class DiffusersImageGenerator:
    def __init__(self, settings: Settings):
        self._s = settings
        self._pipe = None
        self._device = "cpu"
        self._lock = threading.Lock()  # one image at a time: protects GPU memory

    def load(self) -> None:
        if self._pipe is not None:
            return
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError as e:
            raise GenerationError(
                "Diffusers/PyTorch are not installed. Run `pip install -r requirements-ml.txt`, "
                "or set IMAGE_BACKEND=hf_api or mock."
            ) from e

        if torch.cuda.is_available():
            self._device, dtype = "cuda", torch.float16
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            self._device, dtype = "mps", torch.float32
        else:
            self._device, dtype = "cpu", torch.float32
        log.info("Loading %s on %s ...", self._s.sd_model_id, self._device)
        pipe = AutoPipelineForText2Image.from_pretrained(
            self._s.sd_model_id, torch_dtype=dtype, token=self._s.hf_api_key or None
        )
        pipe = pipe.to(self._device)
        pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        self._pipe = pipe

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        import torch

        with self._lock:
            self.load()
            generator = torch.Generator(device="cpu").manual_seed(seed)
            result = self._pipe(
                prompt=prompt,
                negative_prompt=NEGATIVE_PROMPT,
                width=self._s.image_width,
                height=self._s.image_height,
                num_inference_steps=self._s.num_inference_steps,
                guidance_scale=self._s.guidance_scale,
                generator=generator,
            )
        image = result.images[0]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path)
        return out_path


class HFInferenceImageGenerator:
    def __init__(self, settings: Settings):
        if not settings.hf_api_key:
            raise GenerationError("HF_API_KEY is required for IMAGE_BACKEND=hf_api.")
        from huggingface_hub import InferenceClient

        self._client = InferenceClient(token=settings.hf_api_key)
        self._s = settings

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        try:
            image = self._client.text_to_image(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                model=self._s.hf_image_model,
                width=self._s.image_width,
                height=self._s.image_height,
            )
        except Exception as e:  # network / quota / model-loading errors
            raise GenerationError(f"Hugging Face image generation failed: {e}") from e
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path)
        return out_path


class GeminiImageGenerator:
    """Image generation with a Gemini image model, reusing GEMINI_API_KEY."""

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise GenerationError("GEMINI_API_KEY is required for IMAGE_BACKEND=gemini.")
        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._s = settings

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        from google.genai import errors, types

        try:
            resp = self._client.models.generate_content(
                model=self._s.gemini_image_model,
                contents=f"Draw a single square comic panel illustration, no text or speech bubbles: {prompt}",
                config=types.GenerateContentConfig(response_modalities=["IMAGE"], seed=seed % 2**31),
            )
        except errors.APIError as e:
            raise GenerationError(f"Gemini image generation failed ({getattr(e, 'code', '?')}): {e.message or e}") from e
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else None) or []:
                if part.inline_data and part.inline_data.data:
                    image = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                    image = image.resize((self._s.image_width, self._s.image_height))
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(out_path)
                    return out_path
        raise GenerationError("Gemini returned no image (possibly blocked by safety filters). Try rephrasing.")


class PollinationsImageGenerator:
    """Free hosted generation via pollinations.ai (no API key; rate-limited, best effort)."""

    URL = "https://image.pollinations.ai/prompt/{prompt}"

    def __init__(self, settings: Settings):
        self._s = settings

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        import httpx

        params = {
            "width": self._s.image_width,
            "height": self._s.image_height,
            "seed": seed % 2**31,
            "model": self._s.pollinations_model,
            "nologo": "true",
            "negative_prompt": NEGATIVE_PROMPT,
        }
        url = self.URL.format(prompt=quote(prompt[:900], safe=""))
        last: Exception | None = None
        for attempt in range(4):
            try:
                r = httpx.get(url, params=params, timeout=180, follow_redirects=True)
                if r.status_code == 429:  # rate limited: wait and retry
                    time.sleep(10 * (attempt + 1))
                    continue
                r.raise_for_status()
                image = Image.open(io.BytesIO(r.content)).convert("RGB")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(out_path)
                return out_path
            except (httpx.HTTPError, OSError) as e:
                last = e
                time.sleep(3 * (attempt + 1))
        raise GenerationError(f"Pollinations image generation failed: {last or 'rate limited'}")


class CloudflareImageGenerator:
    """Cloudflare Workers AI (free daily allowance). Needs CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN."""

    URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"

    def __init__(self, settings: Settings):
        if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
            raise GenerationError(
                "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required for IMAGE_BACKEND=cloudflare."
            )
        self._s = settings

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        import base64

        import httpx

        s = self._s
        url = self.URL.format(account=s.cloudflare_account_id, model=s.cloudflare_image_model)
        body = {"prompt": prompt[:2000], "seed": seed % 2**31, "steps": 4}
        if "flux" not in s.cloudflare_image_model:  # SD-style models
            body.update(negative_prompt=NEGATIVE_PROMPT, width=s.image_width, height=s.image_height, num_steps=body.pop("steps"))
        try:
            r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {s.cloudflare_api_token}"}, timeout=120)
        except httpx.HTTPError as e:
            raise GenerationError(f"Cloudflare image generation failed: {e}") from e
        if r.status_code >= 400:
            try:
                msg = "; ".join(e.get("message", "") for e in r.json().get("errors", [])) or r.text[:300]
            except ValueError:
                msg = r.text[:300]
            raise GenerationError(f"Cloudflare image generation failed ({r.status_code}): {msg}")
        if r.headers.get("content-type", "").startswith("image/"):
            data = r.content  # SDXL models return raw PNG bytes
        else:
            data = base64.b64decode(r.json()["result"]["image"])  # FLUX returns base64 JSON
        image = Image.open(io.BytesIO(data)).convert("RGB")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path)
        return out_path


class MockImageGenerator:
    def __init__(self, settings: Settings):
        self._size = (settings.image_width, settings.image_height)

    def generate(self, prompt: str, out_path: Path, seed: int) -> Path:
        digest = hashlib.sha256(f"{prompt}{seed}".encode()).digest()
        top, bottom = digest[:3], digest[3:6]
        w, h = self._size
        img = Image.new("RGB", self._size)
        draw = ImageDraw.Draw(img)
        for y in range(h):  # vertical gradient
            t = y / max(h - 1, 1)
            draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        try:
            font = ImageFont.load_default(size=18)
        except TypeError:  # Pillow < 10.1
            font = ImageFont.load_default()
        text = "\n".join(textwrap.wrap(prompt, width=40)[:10])
        draw.rectangle([16, 16, w - 16, h - 16], outline="white", width=4)
        draw.multiline_text((32, 32), text, fill="white", font=font, spacing=6)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        return out_path


def create_image_generator(settings: Settings) -> ImageGenerator:
    if settings.image_backend == "mock":
        return MockImageGenerator(settings)
    if settings.image_backend == "hf_api":
        return HFInferenceImageGenerator(settings)
    if settings.image_backend == "gemini":
        return GeminiImageGenerator(settings)
    if settings.image_backend == "cloudflare":
        return CloudflareImageGenerator(settings)
    if settings.image_backend == "pollinations":
        return PollinationsImageGenerator(settings)
    return DiffusersImageGenerator(settings)


def generate_image(gen: ImageGenerator, prompt: str, out_path: Path, seed: int = 42) -> Path:
    """Spec-compatible functional entry point. Returns the saved image path."""
    return gen.generate(prompt, out_path, seed)
