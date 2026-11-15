from pathlib import Path

import pytest

from ragent.factory import Container, build_offline_container

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
POISONED = ROOT / "evals" / "poisoned"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on the developer's RAGENT_* variables."""
    import os

    for name in list(os.environ):
        if name.startswith("RAGENT_"):
            monkeypatch.delenv(name)


@pytest.fixture
def offline() -> Container:
    return build_offline_container(SAMPLE)
