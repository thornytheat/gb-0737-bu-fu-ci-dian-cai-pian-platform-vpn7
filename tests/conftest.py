from pathlib import Path
from shutil import copytree

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import build_application
from app.pipeline import plan_batch
from app.source import inputs


@pytest.fixture(scope="session")
def dirty_files():
    return inputs(ROOT / "sample_data", "dirty")


@pytest.fixture(scope="session")
def dirty(dirty_files):
    return plan_batch(dirty_files, 5)


@pytest.fixture(scope="session")
def clean():
    return plan_batch(inputs(ROOT / "sample_data", "clean"), 5)


@pytest.fixture
def settings(tmp_path: Path):
    sources = tmp_path / "samples"
    copytree(ROOT / "sample_data", sources)
    return Settings(sources, tmp_path / "fabric.sqlite3")


@pytest.fixture
def client(settings):
    with TestClient(build_application(settings)) as session:
        yield session
