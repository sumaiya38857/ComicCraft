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


def test_cloudflare_flux_base64(settings, tmp_path, monkeypatch):
    import base64
    settings.cloudflare_account_id, settings.cloudflare_api_token = "acc", "tok"
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, auth=headers["Authorization"])
        return httpx.Response(200, json={"result": {"image": base64.b64encode(_png_bytes()).decode()}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = ig.CloudflareImageGenerator(settings).generate("a fox", tmp_path / "c.png", 5)
    assert out.exists() and "/accounts/acc/ai/run/@cf/black-forest-labs/flux-1-schnell" in seen["url"]
    assert seen["auth"] == "Bearer tok" and seen["json"]["seed"] == 5


def test_cloudflare_error_message(settings, tmp_path, monkeypatch):
    import pytest
    from app.services.gemini_client import GenerationError
    settings.cloudflare_account_id, settings.cloudflare_api_token = "acc", "bad"
    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Response(
        401, json={"errors": [{"message": "Authentication error"}]}, request=httpx.Request("POST", url)))
    with pytest.raises(GenerationError, match="401.*Authentication error"):
        ig.CloudflareImageGenerator(settings).generate("a fox", tmp_path / "c.png", 5)
