# ComicCraft: Windows Setup Guide

This guide takes a brand-new Windows 10/11 PC to a running ComicCraft app, step by step. Plan on about 30 minutes, most of it for downloads and creating accounts.

---

## Contents

1. [What you will install](#1-what-you-will-install)
2. [Install Python](#2-install-python)
3. [Install Git](#3-install-git)
4. [Install a code editor (optional)](#4-install-a-code-editor-optional)
5. [Download the project](#5-download-the-project)
6. [Create a virtual environment and install packages](#6-create-a-virtual-environment-and-install-packages)
7. [Get your API keys](#7-get-your-api-keys)
8. [Create the `.env` settings file](#8-create-the-env-settings-file)
9. [Run the app](#9-run-the-app)
10. [Use the app](#10-use-the-app)
11. [Run the tests](#11-run-the-tests)
12. [Everyday commands](#12-everyday-commands)
13. [Pushing changes to GitHub](#13-pushing-changes-to-github)
14. [Optional: local Stable Diffusion on an NVIDIA GPU](#14-optional-local-stable-diffusion-on-an-nvidia-gpu)
15. [Settings reference](#15-settings-reference)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. What you will install

| Tool | Why | Cost |
|---|---|---|
| Python 3.12 | Runs the app | Free |
| Git | Downloads the code and pushes changes | Free |
| VS Code (optional) | Editing files | Free |
| Google Gemini API key | Writes the story | Free tier |
| Cloudflare Workers AI token | Draws the pictures | Free daily allowance |

> **Tip:** Use **PowerShell** for every command in this guide. Press `Win`, type **PowerShell** and press Enter.

---

## 2. Install Python

1. Go to https://www.python.org/downloads/windows/
2. Download the latest **Python 3.12** "Windows installer (64-bit)". Python 3.12 works with every optional package; 3.10–3.13 are fine too.
3. Run the installer. **On the first screen, tick "Add python.exe to PATH".** This is the most common thing people miss.
4. Click **Install Now**, and when it offers, click **Disable path length limit**.
5. Close any open PowerShell windows, open a new one, and check:

   ```powershell
   python --version
   pip --version
   ```

   You should see `Python 3.12.x` and a pip version.

> If `python` opens the Microsoft Store instead, go to **Settings → Apps → Advanced app settings → App execution aliases** and turn **off** both "python.exe" and "python3.exe". Then open a new PowerShell window.

---

## 3. Install Git

1. Go to https://git-scm.com/download/win. The download starts automatically.
2. Run the installer and keep all the default options.
3. Open a **new** PowerShell window and check:

   ```powershell
   git --version
   ```

4. Tell Git who you are. This name appears on your commits.

   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

---

## 4. Install a code editor (optional)

Download VS Code from https://code.visualstudio.com/ and install it with the defaults. Once it's installed, you can open the project with `code .` from inside the project folder.

---

## 5. Download the project

Choose where to keep it, for example your Desktop:

```powershell
cd $HOME\Desktop
git clone https://github.com/sumaiya38857/ComicCraft.git
cd ComicCraft
```

> If the repository is private, Git asks you to sign in. A browser window opens; sign in with the GitHub account that has access.

---

## 6. Create a virtual environment and install packages

A virtual environment keeps ComicCraft's packages separate from the rest of your PC.

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

**If you see "running scripts is disabled on this system"**, run this once, answer `Y`, and then run the activate command again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

When the environment is active, your prompt starts with `(env)`. Now install the packages:

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

This takes 1–3 minutes.

---

## 7. Get your API keys

ComicCraft needs one key to **write the story** and one to **draw the pictures**.

> **Keep keys secret.** Never paste them into chats, emails, screenshots or GitHub. They go **only** in your `.env` file, which Git is set up to ignore. If a key leaks, delete it on the provider's website and make a new one.

### 7.1 Google Gemini API key (story text) — required

1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Accept the terms if asked.
3. Click **Create API key**. If it asks for a project, pick **Create API key in new project**.
4. Copy the key (it starts with `AIza...`).
5. You'll paste it into `.env` as `GEMINI_API_KEY` in step 8.

The free tier is enough for testing. If you later see `429` errors, you've hit the free-tier rate limit; wait a minute, or enable billing in Google AI Studio.

### 7.2 Cloudflare Workers AI (pictures) — recommended, free

1. Sign up at https://dash.cloudflare.com/sign-up and verify your email. No card is needed.
2. In the dashboard's left menu, open **AI → Workers AI**.
3. Click **Use REST API**.
4. Copy your **Account ID** from that page. This is `CLOUDFLARE_ACCOUNT_ID`.
5. Click **Create a Workers AI API Token**, check the settings, then click **Create API Token**.
6. Copy the token right away; it's shown only once. This is `CLOUDFLARE_API_TOKEN`.

The free plan includes a daily allowance that covers many comics.

### 7.3 Other image options (optional)

| Option | How to get access | Notes |
|---|---|---|
| **Hugging Face** (`hf_api`) | https://huggingface.co/settings/tokens → **Create new token** → choose the **Inference** preset → Create | Free accounts get only small monthly credits. A `402` error means they're used up. |
| **Gemini images** (`gemini`) | Uses the same `GEMINI_API_KEY` | Google may require billing to be enabled for image models |
| **Local Stable Diffusion** (`diffusers`) | No key; see [section 14](#14-optional-local-stable-diffusion-on-an-nvidia-gpu) | Needs an NVIDIA GPU to be practical |
| **Mock** (`mock`) | Nothing | Placeholder pictures, for testing the UI |

---

## 8. Create the `.env` settings file

From the project folder:

```powershell
copy .env.example .env
notepad .env
```

Fill in and change these lines:

```ini
GEMINI_API_KEY=AIza...your_key...
LLM_BACKEND=gemini

IMAGE_BACKEND=cloudflare
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_token
```

Save and close Notepad.

> **Test without any keys first.** Set `LLM_BACKEND=mock` and `IMAGE_BACKEND=mock`. You'll get a placeholder comic, which proves the installation works.

> Make sure Notepad saved the file as `.env`, not `.env.txt`. In File Explorer, use **View → Show → File name extensions** to check.

---

## 9. Run the app

With the virtual environment active (you see `(env)`):

```powershell
uvicorn app.main:app --reload
```

When it's ready you'll see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Open in your browser:

- **App:** http://127.0.0.1:8000
- **API docs (for developers):** http://127.0.0.1:8000/docs
- **Health check:** http://127.0.0.1:8000/health shows which backends are active

To stop the server, press **Ctrl + C** in PowerShell.

`--reload` restarts the server automatically when you edit code. After you edit `.env`, though, stop the server with Ctrl+C and start it again.

---

## 10. Use the app

1. Enter a **Story prompt**, for example *"A brave fox exploring an enchanted forest"*.
2. Enter the **main character name**, for example *Rusty*.
3. Choose **Setting**, **Story tone** and **Art style**.
4. Click **Generate my comic**. A progress page shows each step. Generation usually takes 30 seconds to 2 minutes.
5. On the preview page:
   - Click **Download your comic as PDF**. The PDF downloads and the success page opens.
   - Or use **Regenerate**. If you change only the art style, the pictures are redrawn and the story stays the same. If you change the tone, the whole comic is rewritten.

Generated files are saved in the `media\` folder (panel images, PDFs and comic data).

---

## 11. Run the tests

The tests use the mock backends, so they need no keys and no internet.

```powershell
pytest
```

Expected output: `17 passed`.

---

## 12. Everyday commands

Each time you open a new PowerShell window:

```powershell
cd $HOME\Desktop\ComicCraft
.\env\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

To get the latest code from GitHub:

```powershell
git pull
pip install -r requirements-dev.txt
```

---

## 13. Pushing changes to GitHub

```powershell
git status                       # check: .env must NOT be listed
git add .
git commit -m "Describe your change"
git push
```

**Signing in:** Git for Windows opens a browser window to sign in to GitHub. If it asks for a password in the terminal instead, use a **personal access token**, not your GitHub password:

- **Classic token:** go to https://github.com/settings/tokens/new, tick **repo**, generate it, and paste it when asked for a password.
- **Fine-grained token:** set Repository access to **Only select repositories → ComicCraft**, and Permissions → **Contents: Read and write**.

**"Permission denied to <username>" (403):**
- *The wrong account is signed in.* Open **Control Panel → Credential Manager → Windows Credentials**, remove the entries starting with `git:https://github.com`, and push again.
- *The right account but still 403.* The token can't write to the repo. Create a new one as described above.
- *Pushing to someone else's repository.* The owner must add you under **Settings → Collaborators**.

---

## 14. Optional: local Stable Diffusion on an NVIDIA GPU

Only do this if your PC has an NVIDIA graphics card. On a CPU alone, each panel takes several minutes.

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-ml.txt
```

Then in `.env`, set:

```ini
IMAGE_BACKEND=diffusers
SD_MODEL_ID=stable-diffusion-v1-5/stable-diffusion-v1-5
```

The first run downloads the model, about 4 GB. Check that the GPU is detected:

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

It should print `True`.

---

## 15. Settings reference

All settings live in `.env`. Restart the server after changing any of them.

| Setting | Values / default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini key |
| `LLM_BACKEND` | `gemini` \| `mock` | Story text source |
| `OUTLINE_MODEL` | `gemini-2.5-flash` | Model for the panel outline |
| `STORY_MODEL` | `gemini-2.5-pro` | Model for narration and dialogue |
| `IMAGE_BACKEND` | `cloudflare` \| `hf_api` \| `gemini` \| `diffusers` \| `pollinations` \| `mock` | Picture source |
| `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` | — | Cloudflare credentials |
| `CLOUDFLARE_IMAGE_MODEL` | `@cf/black-forest-labs/flux-1-schnell` | Cloudflare image model |
| `HF_API_KEY` / `HF_IMAGE_MODEL` | — | Hugging Face token and model |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` | Gemini image model |
| `SD_MODEL_ID` | `stable-diffusion-v1-5/stable-diffusion-v1-5` | Local Stable Diffusion model |
| `NUM_INFERENCE_STEPS` | `25` | Local Stable Diffusion quality vs. speed |
| `PANEL_COUNT` | `5` (3–8) | Panels per comic |
| `DEBUG` | `false` | `true` enables the `/test-image` route |
| `PDF_FONT_PATH` | empty | Optional `.ttf` font for full Unicode text in PDFs |

> Gemini model names change over time. If you get a `404 model not found` error, check the current names at https://ai.google.dev/gemini-api/docs/models and update `OUTLINE_MODEL` and `STORY_MODEL`.

---

## 16. Troubleshooting

| Error / symptom | Cause | Fix |
|---|---|---|
| `'python' is not recognized` | Python isn't on PATH | Reinstall Python and tick **Add python.exe to PATH**, then open a new PowerShell |
| `running scripts is disabled on this system` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `No module named uvicorn` / `fastapi` | The virtual environment isn't active | `.\env\Scripts\Activate.ps1`, then `pip install -r requirements-dev.txt` |
| pip is "Building wheel" for a long time, or fails | Old pip, or no prebuilt package for your Python | `python -m pip install --upgrade pip` and retry; use Python 3.12 |
| `GEMINI_API_KEY is not set` | `.env` is missing or empty | Do [step 8](#8-create-the-env-settings-file); check the file isn't named `.env.txt` |
| `CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required` | Cloudflare values are empty | Fill them in [step 8](#8-create-the-env-settings-file), or set `IMAGE_BACKEND=mock` |
| `Cloudflare ... (401/403) Authentication error` | Wrong token or account ID | Create a new Workers AI token; copy the Account ID again |
| `402 Payment Required` (Hugging Face / Pollinations) | Free credits are used up | Switch to `IMAGE_BACKEND=cloudflare` |
| `Gemini request failed (429)` | Free-tier rate limit | Wait a minute, or enable billing in AI Studio |
| `Gemini request failed (404)` | Outdated model name | Update `OUTLINE_MODEL` / `STORY_MODEL` |
| The story is generic ("a hero who discovers…") | `LLM_BACKEND=mock` | Set `LLM_BACKEND=gemini` and restart |
| `[Errno 10048] address already in use` | Port 8000 is busy | `uvicorn app.main:app --reload --port 8001` |
| Characters look different in each panel | FLUX doesn't accept a seed | Normal for now; the panels share the same character description |
| `git push` gives a 403 | Wrong account or token | See [section 13](#13-pushing-changes-to-github) |
