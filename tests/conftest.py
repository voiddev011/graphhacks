import os
import uuid

import pytest

from app.repository import FalkorStore, MemoryStore
from app.service import Service


@pytest.fixture(params=["memory", "falkor"])
def service(request):
    if request.param == "memory":
        yield Service(MemoryStore())
        return
    if os.getenv("CONTINUITY_DB_TESTS") != "1":
        pytest.skip("Real database checks require CONTINUITY_DB_TESTS=1 and FalkorDB")
    # Dedicated random tenant graph. Cleanup never touches the user's demo graph.
    store = FalkorStore("test_" + uuid.uuid4().hex, "apollo")
    try:
        yield Service(store)
    finally:
        store.graph.delete()
