"""Explicit integration gates. Skips are NOT successful integration results."""
import json
import os
import subprocess
import sys
import uuid

import pytest

from app.domain import Conflict, Rejected
from tests.fixtures import seed
from app.repository import FalkorStore
from app.service import Service, new_id


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("CONTINUITY_DB_TESTS") != "1", reason="Enable CONTINUITY_DB_TESTS=1 with real FalkorDB")
def test_C01_C03_new_process_scope_and_graph_traversal():
    tenant = "test_" + uuid.uuid4().hex
    stores = [FalkorStore(tenant, "apollo"), FalkorStore(tenant, "other"),
              FalkorStore("test_" + uuid.uuid4().hex, "apollo")]
    try:
        s = Service(stores[0])
        seed(s)
        for foreign in stores[1:]:
            assert not foreign.read()["decisions"]
            with pytest.raises(Rejected):
                foreign.task_context("interface")
        snapshot, connected = stores[0].task_context("interface")
        assert connected["decisions"]["interface_framework"]["value"] == "React"
        code = ("import sys; sys.path.insert(0,'.'); from app.repository import FalkorStore; "
                f"s=FalkorStore({tenant!r},'apollo').read(); "
                "print(s['versions'][s['decisions']['interface_framework']]['value'])")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=True)
        assert result.stdout.strip() == "React"
    finally:
        # Two projects share the first graph; delete each unique test graph once.
        for store in {st.graph_name: st for st in stores}.values():
            store.graph.delete()


@pytest.mark.live
@pytest.mark.skipif(os.getenv("CONTINUITY_LIVE_TESTS") != "1", reason="Enable live Gemini deliberately; requires key/model and consumes quota")
def test_live_planner_and_helper_structured_output():
    from dotenv import load_dotenv
    from app.models import Gemini, Help, Plan
    from app.repository import MemoryStore
    from app.workflow import build
    load_dotenv()
    s = Service(MemoryStore())
    seed(s)
    model = Gemini()
    graph = build(s, model)
    rid = new_id()
    plan = graph.invoke({"request_id": rid, "role": "planner", "text": "Help me resume."})["receipt"]
    hrid = new_id()
    helper = graph.invoke({"request_id": hrid, "role": "helper", "text": "Draft practical steps.", "handoff": plan["handoff"], "owner": "helper"})["receipt"]
    assert helper["accepted"] and not helper["completed"]
    assert s.store.read()["requests"][rid]["calls"] == 1
    assert s.store.read()["requests"][hrid]["calls"] == 1
    print({"model": os.environ["GOOGLE_MODEL"], "usage": model.usage})
