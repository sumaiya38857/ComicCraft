import io
from types import SimpleNamespace

import httpx
from PIL import Image

from app.services import image_generator as ig


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_pollinations_saves_image_and_retries_429(settings, tmp_path, monkeypatch):
    calls = []

    def fake_get(url, params, timeout, follow_redirects):
        calls.append((url, params))
        code = 429 if len(calls) == 1 else 200
        return httpx.Response(code, content=_png_bytes(), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    out = ig.PollinationsImageGenerator(settings).generate("a fox, comic style", tmp_path / "p.png", 7)
    assert out.exists() and len(calls) == 2
    assert "a%20fox%2C%20comic%20style" in calls[0][0] and calls[0][1]["seed"] == 7


def test_gemini_image_extracts_inline_data(settings, tmp_path, monkeypatch):
    settings.gemini_api_key = "x"
    gen = ig.GeminiImageGenerator(settings)
    part = SimpleNamespace(inline_data=SimpleNamespace(data=_png_bytes()))
    resp = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    monkeypatch.setattr(gen._client.models, "generate_content", lambda **kw: resp)
    out = gen.generate("a fox", tmp_path / "g.png", 3)
    assert Image.open(out).size == (settings.image_width, settings.image_height)
