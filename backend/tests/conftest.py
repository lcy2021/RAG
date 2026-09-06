# ruff: noqa: E402, I001
import os

os.environ["RAGLAB_DATABASE_ENABLED"] = "false"

from configs.settings import get_settings

get_settings.cache_clear()

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
