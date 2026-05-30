import os

import pytest

os.environ.setdefault("DEEPSEEK_API_KEY", "test-deepseek-key")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
