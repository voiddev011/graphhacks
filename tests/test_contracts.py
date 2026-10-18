import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.domain import Conflict, Rejected, bundle, canonical, current_inputs, ready, satisfied, valid_bundle
from tests.fixtures import seed
from app.service import Service, new_id


def change(s, key="interface_framework", value="Streamlit", speaker="user", text=None):
    text = text or f"Set {key} to {value}."
    msg = s.message(text, speaker)
    return s.command("decision", {"key": key, "value": value, "message": msg, "passage": text})


def handoff(s, tid="interface"):
    return s.command("handoff", {"objective": "Build safely", "bundle": bundle(s.store.read(), tid)})["handoff"]


def claim(s, hid):
    return s.command("claim", {"handoff": hid, "owner": "helper"})


def complete(s, hid, c, operation_id=None):
    text = "I built and manually checked the synthetic interface."
    msg = s.message(text)
    p = {"handoff": hid, "claim": c["claim"], "execution_version": c["execution_version"],
         "message": msg, "passage": text, "outcome": text}
    return s.command("complete", p, operation_id), p


def review(s, action):
    text = "I explicitly confirm this resolution."
    msg = s.message(text)
    state = s.store.read()
    task = state["tasks"]["interface"]
    return s.command("review", {"task": "interface", "action": action, "message": msg, "passage": text,
                                 "task_version": task["version"], "decisions": current_inputs(state, task),
                                 "confirmed": True, "replacement": "interface_v2", "rewire": ["deploy"]})


def test_C02_current_history_source_and_assistant_rejection(service):
    seed(service)
    before = service.store.read()
    old = before["decisions"]["interface_framework"]
    change(service)
    s = service.store.read()
    new = s["decisions"]["interface_framework"]
    assert s["versions"][new]["supersedes"] == old
    assert s["versions"][old]["value"] == "React"
    assert s["versions"][new]["source"]["passage"] == "Set interface_framework to Streamlit."
    with pytest.raises(Rejected):
        change(service, value="React", speaker="assistant")
    with pytest.raises(Rejected):
        change(service, value="React", text="Maybe set interface_framework to React.")


@pytest.mark.parametrize("resolution", ["confirm", "reopen", "replace"])
def test_C04_C06_decision_impact_and_resolutions(service, resolution):
    seed(service)
    # Complete storage so the deployment blocker is exactly the interface.
    hs = handoff(service, "storage")
    complete(service, hs, claim(service, hs))
    h = handoff(service)
    receipt, _ = complete(service, h, claim(service, h))
    old = copy.deepcopy(service.store.read()["results"][receipt["result"]])
    assert "deploy" in ready(service.store.read())
    change(service)
    s = service.store.read()
    assert s["results"][old["id"]]["review_state"] == "requires_review"
    assert "deploy" not in ready(s)
    assert s["results"][old["id"]]["based_on"] == old["based_on"]
    review(service, resolution)
    s = service.store.read()
    assert ("deploy" in ready(s)) == (resolution == "confirm")
    assert s["results"][old["id"]]["based_on"] == old["based_on"]
    if resolution == "replace":
        assert "interface_v2" in s["tasks"]["deploy"]["prerequisites"]
    if resolution == "confirm":
        change(service, value="React")
        assert not satisfied(service.store.read(), "interface")


def test_C05_C07_fresh_service_and_unrelated_changes(service):
    seed(service)
    h = handoff(service)
    b = copy.deepcopy(service.store.read()["handoffs"][h]["bundle"])
    service.message("Unrelated chat")
    change(service, "response_style", "short")
    independent = handoff(service, "readme")
    complete(service, independent, claim(service, independent))
    assert valid_bundle(service.store.read(), b)
    fresh = Service(service.store)
    c = claim(fresh, h)
    assert valid_bundle(fresh.store.read(), b, c["execution_version"])


@pytest.mark.parametrize("mutation", ["decision", "procedure", "prerequisite"])
def test_C08_change_during_generation_barrier(service, mutation):
    seed(service)
    if mutation == "prerequisite":
        hs = handoff(service, "interface")
        complete(service, hs, claim(service, hs))
        service.command("task", {"id": "dependent", "title": "Dependent", "prerequisites": ["interface"]})
        hid = handoff(service, "dependent")
    else:
        hid = handoff(service)
    c = claim(service, hid)
    entered, proceed = threading.Event(), threading.Event()

    def generation_then_commit():
        entered.set()
        assert proceed.wait(10)
        return complete(service, hid, c)[0]

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(generation_then_commit)
        assert entered.wait(10)
        if mutation == "procedure":
            steps = ["Check the revised procedure."]
            text = "I approve " + canonical(steps)
            msg = service.message(text)
            service.command("procedure", {"name": "build", "steps": steps, "message": msg, "passage": text, "approved": True})
        else:
            change(service)
        proceed.set()
        receipt = future.result()
    s = service.store.read()
    assert receipt["stale"] and not receipt["accepted"]
    assert s["attempts"][receipt["attempt"]]["stale"]
    assert s["tasks"][s["handoffs"][hid]["bundle"]["task"]]["result"] is None


def test_C09_C10_replay_and_payload_conflict(service):
    seed(service)
    h = handoff(service)
    c = claim(service, h)
    oid = new_id()
    receipt, payload = complete(service, h, c, oid)
    before = service.store.read()
    assert service.command("complete", payload, oid) == receipt
    assert service.store.read() == before
    with pytest.raises(Conflict):
        service.command("complete", {**payload, "outcome": "changed"}, oid)
    assert service.store.read() == before


def test_C11_two_clients_claim_and_release(service):
    seed(service)
    h = handoff(service)
    barrier = threading.Barrier(2)

    def contend(owner):
        barrier.wait(10)
        try:
            return service.command("claim", {"handoff": h, "owner": owner})
        except Rejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(contend, ["first", "second"]))
    winners = [c for c in claims if c]
    assert len(winners) == 1
    winner = winners[0]
    text = "I confirm release."
    msg = service.message(text)
    service.command("release", {"task": "interface", "claim": winner["claim"], "confirmed": True, "message": msg, "passage": text})
    receipt, _ = complete(service, h, winner)
    assert not receipt["accepted"]
    assert service.store.read()["tasks"]["interface"]["claim"] is None


def test_C12_C13_evidence_and_procedure_do_not_mean_execution(service):
    seed(service)
    assert all(t["status"] == "pending" for t in service.store.read()["tasks"].values())
    with pytest.raises(Rejected):
        service.command("task", {"id": "bad", "title": "bad", "prerequisites": ["foreign_task"]})
    h = handoff(service)
    c = claim(service, h)
    receipt = service.command("draft", {"handoff": h, "claim": c["claim"], "execution_version": c["execution_version"], "draft": "Proposed steps only."})
    assert not receipt["completed"]
    assert service.store.read()["tasks"]["interface"]["result"] is None
    with pytest.raises(Rejected):
        service.command("complete", {"handoff": h, "claim": c["claim"], "execution_version": c["execution_version"], "outcome": "Done", "message": "unknown", "passage": "Done"})


def test_C14_persisted_budget_and_request_input_hash(service):
    rid = new_id()
    service.begin(rid, "planner", "Resume")
    with pytest.raises(Conflict):
        service.begin(rid, "planner", "Different input")
    class Failure:
        def generate(self, role, context):
            raise RuntimeError("Simulated provider failure")
    for _ in range(3):
        with pytest.raises(RuntimeError):
            service.generate(rid, Failure(), "planner", {})
    with pytest.raises(Rejected, match="budget"):
        service.generate(rid, Failure(), "planner", {})
    assert service.store.read()["requests"][rid]["calls"] == 3


def test_workflow_one_call_replay_zero_and_stale_draft(service):
    from tests.fakes import DemoModel
    from app.workflow import build
    seed(service)
    graph = build(service, DemoModel())
    rid = new_id()
    inputs = {"request_id": rid, "role": "planner", "text": "Resume"}
    receipt = graph.invoke(inputs)["receipt"]
    assert graph.invoke(inputs)["receipt"] == receipt
    assert service.store.read()["requests"][rid]["calls"] == 1
    class MutatingModel(DemoModel):
        def generate(self, role, context):
            change(service)
            return super().generate(role, context)
    hid = receipt["handoff"]
    hrid = new_id()
    output = build(service, MutatingModel()).invoke({"request_id": hrid, "role": "helper", "text": "Help", "handoff": hid, "owner": "helper"})
    assert output["receipt"]["stale"]
    assert service.store.read()["requests"][hrid]["calls"] == 1
