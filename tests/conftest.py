import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        llm_backend="mock",
        image_backend="mock",
        media_dir=tmp_path / "media",
        image_width=128,
        image_height=128,
        debug=True,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c
