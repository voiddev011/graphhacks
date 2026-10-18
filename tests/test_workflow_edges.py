import copy

import pytest

from app.domain import Conflict, Rejected, bundle
from tests.fixtures import seed
from app.repository import projection
from app.service import new_id


def test_accepted_envelope_replays_without_regeneration(service):
    seed(service)
    rid = new_id()
    service.begin(rid, "planner", "Resume")
    p = {"objective": "Build interface", "bundle": bundle(service.store.read(), "interface")}
    envelope = service.accept_envelope(rid, "handoff", p)
    receipt = service.command(envelope["kind"], envelope["payload"], envelope["operation_id"])
    before = service.store.read()
    assert service.replay(rid) == receipt
    assert service.store.read() == before
    with pytest.raises(Conflict):
        service.accept_envelope(rid, "handoff", {**p, "objective": "Different"})


def test_old_claim_cannot_clear_new_owner(service):
    seed(service)
    def handoff():
        return service.command("handoff", {"objective": "Build", "bundle": bundle(service.store.read(), "interface")})["handoff"]
    old_h = handoff()
    old = service.command("claim", {"handoff": old_h, "owner": "old"})
    message = service.message("I confirm release.")
    service.command("release", {"task": "interface", "claim": old["claim"], "confirmed": True, "message": message, "passage": "I confirm release."})
    new_h = handoff()
    new = service.command("claim", {"handoff": new_h, "owner": "new"})
    text = "I finished the old draft."
    msg = service.message(text)
    receipt = service.command("complete", {"handoff": old_h, "claim": old["claim"],
                       "execution_version": old["execution_version"], "message": msg, "passage": text, "outcome": text})
    assert receipt["stale"]
    assert service.store.read()["tasks"]["interface"]["claim"] == new["claim"]


def test_model_cannot_select_foreign_or_ineligible_task(service):
    from app.workflow import build
    seed(service)
    class InvalidModel:
        def generate(self, role, context):
            return {"task_id": "deploy", "objective": "Skip blocked prerequisites"}
    with pytest.raises(Rejected, match="ineligible"):
        build(service, InvalidModel()).invoke({"role": "planner", "text": "Resume", "request_id": new_id()})
    assert not service.store.read()["handoffs"]


def test_malformed_output_does_not_commit(service):
    from app.workflow import build
    seed(service)
    class MalformedModel:
        def generate(self, role, context):
            return {"arbitrary_cypher": "CREATE ..."}
    with pytest.raises(ValueError):
        build(service, MalformedModel()).invoke({"role": "planner", "text": "Resume", "request_id": new_id()})
    assert not service.store.read()["handoffs"]


def test_simulated_write_failure_can_replay_saved_envelope(service, monkeypatch):
    from tests.fakes import DemoModel
    from app.workflow import build
    seed(service)
    original = service.store.execute
    def fail_handoff(kind, payload, oid):
        if kind == "handoff":
            raise ConnectionError("Simulated interrupted database write")
        return original(kind, payload, oid)
    monkeypatch.setattr(service.store, "execute", fail_handoff)
    rid = new_id()
    inputs = {"role": "planner", "text": "Resume", "request_id": rid}
    with pytest.raises(ConnectionError):
        build(service, DemoModel()).invoke(inputs)
    assert not service.store.read()["handoffs"]
    assert service.store.read()["requests"][rid]["envelope"]
    monkeypatch.setattr(service.store, "execute", original)
    receipt = build(service, DemoModel()).invoke(inputs)["receipt"]
    assert receipt["handoff"] in service.store.read()["handoffs"]
    assert service.store.read()["requests"][rid]["calls"] == 1


def test_cli_helper_arguments_and_completion_parser():
    from app.cli import parser
    parsed = parser().parse_args(["help", "handoff_123"])
    assert parsed.handoff == "handoff_123"
    assert parsed.text == "Help me resume this project."
    parsed = parser().parse_args(["complete", "handoff_123", "I checked it.", "--request-id", "done_1"])
    assert parsed.outcome == "I checked it."


def test_oversized_context_consumes_no_provider_attempt(service):
    rid = new_id()
    service.begin(rid, "planner", "Resume")
    with pytest.raises(Rejected, match="ceiling"):
        service.generate(rid, object(), "planner", {"large": "x" * 25000})
    assert service.store.read()["requests"][rid]["calls"] == 0


def test_noop_decision_and_message_do_not_bump_business_watermark(service):
    seed(service)
    s = service.store.read()
    before = s["revision"]
    msg = service.message("Set interface_framework to React.")
    assert service.store.read()["revision"] == before
    receipt = service.command("decision", {"key": "interface_framework", "value": "React", "message": msg, "passage": "Set interface_framework to React."})
    assert receipt["unchanged"]
    assert service.store.read()["revision"] == before


def test_projection_has_connected_sources_and_no_dangling_nodes(service):
    seed(service)
    nodes, edges = projection(service.store.read(), "apollo")
    ids = {n["id"] for n in nodes}
    assert len(ids) == len(nodes)
    assert all(e["a"] in ids and e["b"] in ids for e in edges)
    assert {"CURRENT", "FROM_MESSAGE", "DEPENDS_ON", "REQUIRES_DECISION"} <= {e["kind"] for e in edges}


def test_installed_google_sdk_zero_retries_is_one_attempt():
    from google.genai._api_client import retry_args
    from google.genai.types import HttpRetryOptions
    assert retry_args(HttpRetryOptions(attempts=0))["stop"].max_attempt_number == 1


def test_concurrent_services_cannot_share_one_provider_reservation(service):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from app.service import Service
    rid = new_id()
    service.begin(rid, "planner", "Resume")
    barrier = threading.Barrier(5)
    class CountingModel:
        def generate(self, role, context):
            return True
    def attempt(_):
        other = Service(service.store)
        barrier.wait(10)
        try:
            return other.generate(rid, CountingModel(), "planner", {})
        except Rejected:
            return False
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(attempt, range(5)))
    assert sum(results) == 3
    assert service.store.read()["requests"][rid]["calls"] == 3


def test_review_cannot_silently_confirm_newer_decision(service):
    from app.domain import current_inputs
    seed(service)
    h = service.command("handoff", {"objective": "Build", "bundle": bundle(service.store.read(), "interface")})["handoff"]
    c = service.command("claim", {"handoff": h, "owner": "helper"})
    text = "I built and checked the interface."
    msg = service.message(text)
    service.command("complete", {"handoff": h, "claim": c["claim"], "execution_version": c["execution_version"],
                                 "message": msg, "passage": text, "outcome": text})
    state = service.store.read()
    task = state["tasks"]["interface"]
    confirmation = "I confirm the existing result remains compatible."
    msg = service.message(confirmation)
    payload = {"task": "interface", "action": "confirm", "confirmed": True, "message": msg, "passage": confirmation,
               "task_version": task["version"], "decisions": current_inputs(state, task)}
    change = "Set interface_framework to Streamlit."
    msg = service.message(change)
    service.command("decision", {"key": "interface_framework", "value": "Streamlit", "message": msg, "passage": change})
    with pytest.raises(Rejected, match="Review inputs changed"):
        service.command("review", payload)
    assert not service.store.read()["reviews"]
