# ComicCraft

An AI comic story creator. Gemini Flash plans the panels, Gemini Pro writes the narration and dialogue, and Stable Diffusion draws each panel. The result shows up in the browser and can be downloaded as a PDF.

## Quick start (no API keys, no GPU)

```bash
python3 -m venv env && source env/bin/activate      # Windows: env\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
# in .env set: LLM_BACKEND=mock  IMAGE_BACKEND=mock
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 for the app, or http://127.0.0.1:8000/docs for the API.

## Real generation

1. Put `GEMINI_API_KEY` in `.env` and set `LLM_BACKEND=gemini`. Check that `OUTLINE_MODEL` and `STORY_MODEL` match current names at https://ai.google.dev/gemini-api/docs/models.
2. Pick an image backend:
   - `IMAGE_BACKEND=diffusers` runs Stable Diffusion locally. Install it with `pip install -r requirements-ml.txt`. The first run downloads the model (about 4 GB). Expect 1–3 minutes per panel on CPU and a few seconds per panel on an NVIDIA GPU.
   - `IMAGE_BACKEND=hf_api` uses the Hugging Face hosted API. It needs `HF_API_KEY` and installs no PyTorch. This is the best choice on a laptop without a GPU.
   - `IMAGE_BACKEND=gemini` draws the panels with a Gemini image model using your `GEMINI_API_KEY`. Google may require billing to be enabled for image models.
   - `IMAGE_BACKEND=cloudflare` uses Cloudflare Workers AI (FLUX.1 schnell). The free plan has a daily allowance and needs no card. Set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.
   - `IMAGE_BACKEND=pollinations` uses the free pollinations.ai service. It may now require a paid plan.
   - `IMAGE_BACKEND=mock` draws placeholder images, which is useful while working on the UI.

> **Intel Macs:** PyTorch's last macOS x86_64 release is 2.2.2, and it needs NumPy < 2. `requirements-ml.txt` pins both for you.

## Tests

```bash
pytest
```

The tests use the mock backends, so they need no keys and no network.

## Architecture

```
Browser ── POST /generate ──► FastAPI ──► ComicService (one background worker)
   ▲  checks /api/v1/jobs/{id}              ├─ gemini_flash.generate_outline()  JSON-schema output
   │                                        ├─ gemini_pro.generate_story()      JSON-schema output
   └── /comics/{id} preview                 ├─ image_generator.generate_image() diffusers | hf_api | mock
       /comics/{id}/pdf download            ├─ layout_builder.build_comic_layout()  (joins by panel_number)
                                            └─ exporters.save_pdf()  (fpdf2, built when downloaded)
```

| Route | Purpose |
|---|---|
| `GET /` | Input form |
| `POST /generate` | Start a job from the form, then go to the progress page |
| `GET /jobs/{job_id}` | Progress page |
| `GET /comics/{id}` | Comic preview |
| `POST /comics/{id}/regenerate` | Scenario 2. A tone change rewrites everything; a style-only change redraws the images and keeps the story. |
| `GET /comics/{id}/pdf` | Download the PDF; the page then moves to `/export-success` |
| `POST /api/v1/comics` | Async JSON API (returns 202 + `status_url`) |
| `GET /api/v1/jobs/{id}`, `GET /api/v1/comics/{id}` | Job status and comic JSON |
| `POST /generate-comic/json` | Synchronous JSON endpoint from the spec (returns layout + `pdf_url`) |
| `POST /test-image` | Developer-only image test (only when `DEBUG=true`) |

Generated files go in `media/` (panels, exports, and comic JSON). Comics are saved as JSON files, so previews survive a server restart.

## Project layout

```
app/
  main.py  config.py  schemas.py
  api/        routes.py (HTML)  api_routes.py (JSON)  deps.py
  services/   comic_service.py  gemini_client.py  gemini_flash.py  gemini_pro.py
              image_generator.py  layout_builder.py  exporters.py  prompts.py
  templates/  _base, index, progress, comic_preview, export_success
  static/     css/style.css  js/progress.js
tests/
```

## Next steps

- Retry a single panel from the preview page
- Consistent characters across panels with IP-Adapter
- Unicode font for PDFs (`PDF_FONT_PATH`)
- Redis job store and a separate GPU worker for multi-user deployment
- Dockerfile and cloud deployment
